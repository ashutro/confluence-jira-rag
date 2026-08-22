"""Jira Cloud REST API Connector for CloudScale Payments RAG Assistant."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import requests
from requests.auth import HTTPBasicAuth

from rag_assistant.config import Settings, get_project_root
from rag_assistant.connectors.adf_cleaner import clean_adf_to_markdown

logger = logging.getLogger(__name__)


@dataclass
class JiraDocument:
    """Standardized document representation of a Jira issue."""

    id: str
    key: str
    project_key: str
    project_name: str
    issue_type: str
    summary: str
    description_markdown: str
    description_text: str
    status: str
    priority: str
    reporter: Dict[str, str]
    assignee: Optional[Dict[str, str]]
    components: List[str]
    labels: List[str]
    created_at: str
    updated_at: str
    resolved_at: Optional[str]
    resolution: Optional[str]
    url: str
    comments: List[Dict[str, Any]] = field(default_factory=list)
    linked_issues: List[Dict[str, str]] = field(default_factory=list)
    linked_confluence_pages: List[Dict[str, str]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert document to JSON-serializable dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> JiraDocument:
        return cls(
            id=str(data["id"]),
            key=data["key"],
            project_key=data.get("project_key", ""),
            project_name=data.get("project_name", ""),
            issue_type=data.get("issue_type", "Task"),
            summary=data.get("summary", ""),
            description_markdown=data.get("description_markdown", data.get("description", "")),
            description_text=data.get("description_text", data.get("description", "")),
            status=data.get("status", "Open"),
            priority=data.get("priority", "Medium"),
            reporter=data.get("reporter", {}),
            assignee=data.get("assignee"),
            components=data.get("components", []),
            labels=data.get("labels", []),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            resolved_at=data.get("resolved_at"),
            resolution=data.get("resolution"),
            url=data.get("url", ""),
            comments=data.get("comments", []),
            linked_issues=data.get("linked_issues", []),
            linked_confluence_pages=data.get("linked_confluence_pages", []),
            metadata=data.get("metadata", {}),
        )


class JiraConnector:
    """Connector to interact with Jira Cloud REST API (v3 / v2)."""

    def __init__(
        self,
        base_url: str,
        email: str,
        api_token: str,
        project_key: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
        api_version: int = 3,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.api_token = api_token
        self.project_key = project_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.api_version = api_version

        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(self.email, self.api_token)
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "ConfluenceJiraRAGAssistant/0.1.0",
            }
        )

    @classmethod
    def from_settings(cls, settings: Optional[Settings] = None) -> JiraConnector:
        """Instantiate connector using application settings."""
        cfg = settings or Settings.from_env()
        cfg.validate_jira()
        return cls(
            base_url=cfg.jira_base_url,  # type: ignore[arg-type]
            email=cfg.jira_email,  # type: ignore[arg-type]
            api_token=cfg.jira_api_token,  # type: ignore[arg-type]
            project_key=cfg.jira_project_key,
        )

    def _request(self, method: str, endpoint: str, **kwargs: Any) -> requests.Response:
        """Execute HTTP request with retry logic for rate-limiting and server errors."""
        url = endpoint if endpoint.startswith("http") else f"{self.base_url}/{endpoint.lstrip('/')}"
        kwargs.setdefault("timeout", self.timeout)

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.request(method, url, **kwargs)

                # Handle Rate Limiting (429)
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 2 * attempt))
                    logger.warning(
                        f"Jira rate limit reached (429). Retrying after {retry_after}s..."
                    )
                    time.sleep(retry_after)
                    continue

                # Handle Transient Server Errors (500, 502, 503, 504)
                if response.status_code in (500, 502, 503, 504) and attempt < self.max_retries:
                    wait_time = 2**attempt
                    logger.warning(
                        f"Jira server error {response.status_code}. Retrying attempt {attempt}/{self.max_retries} in {wait_time}s..."
                    )
                    time.sleep(wait_time)
                    continue

                if response.status_code == 401:
                    raise PermissionError(
                        "Jira authentication failed (401). Please check JIRA_EMAIL and JIRA_API_TOKEN."
                    )
                if response.status_code == 403:
                    raise PermissionError(
                        f"Access forbidden (403) for Jira URL: {url}. Ensure user has permission for this project/issue."
                    )
                if response.status_code == 404:
                    raise FileNotFoundError(f"Jira resource not found (404): {url}")

                response.raise_for_status()
                return response

            except (requests.ConnectionError, requests.Timeout) as e:
                if attempt == self.max_retries:
                    raise ConnectionError(
                        f"Failed to connect to Jira at {url} after {self.max_retries} attempts: {e}"
                    ) from e
                time.sleep(2**attempt)

        raise RuntimeError(f"Request to {url} failed after {self.max_retries} attempts.")

    def fetch_issue_by_key(self, issue_key: str) -> JiraDocument:
        """Fetch a single Jira issue with full fields, comments, and links."""
        endpoint = f"rest/api/{self.api_version}/issue/{issue_key}"
        resp = self._request("GET", endpoint)
        data = resp.json()
        return self._parse_jira_issue(data)

    def search_issues(
        self,
        jql: str,
        start_at: int = 0,
        max_results: int = 50,
    ) -> Dict[str, Any]:
        """Execute a JQL search query."""
        endpoint = f"rest/api/{self.api_version}/search"
        params = {
            "jql": jql,
            "startAt": start_at,
            "maxResults": max_results,
            "fields": [
                "summary",
                "description",
                "issuetype",
                "status",
                "priority",
                "reporter",
                "assignee",
                "components",
                "labels",
                "created",
                "updated",
                "resolutiondate",
                "resolution",
                "comment",
                "issuelinks",
                "project",
            ],
        }
        resp = self._request("GET", endpoint, params=params)
        return resp.json()

    def fetch_all_issues(
        self,
        project_key: Optional[str] = None,
        jql: Optional[str] = None,
        max_total: Optional[int] = None,
    ) -> List[JiraDocument]:
        """Traverse pagination to retrieve all issues matching project or JQL query."""
        target_project = project_key or self.project_key
        if jql:
            query = jql
        elif target_project:
            query = f'project = "{target_project}" ORDER BY created DESC'
        else:
            query = "ORDER BY created DESC"

        documents: List[JiraDocument] = []
        start_at = 0
        page_size = 50

        while True:
            data = self.search_issues(query, start_at=start_at, max_results=page_size)
            issues_raw = data.get("issues", [])
            total = data.get("total", len(issues_raw))

            for item in issues_raw:
                doc = self._parse_jira_issue(item)
                documents.append(doc)
                if max_total and len(documents) >= max_total:
                    return documents[:max_total]

            start_at += len(issues_raw)
            if start_at >= total or not issues_raw:
                break

        return documents

    def _parse_jira_issue(self, item: Dict[str, Any]) -> JiraDocument:
        """Parse raw Jira API issue JSON into standardized JiraDocument."""
        issue_id = str(item.get("id", ""))
        key = item.get("key", "")
        fields = item.get("fields", {})

        # Project info
        project = fields.get("project", {})
        proj_key = project.get("key", self.project_key or "")
        proj_name = project.get("name", "")

        # Type, Status, Priority
        issue_type = fields.get("issuetype", {}).get("name", "Task")
        status = fields.get("status", {}).get("name", "Open")
        priority = fields.get("priority", {}).get("name", "Medium")

        # Summary & Description
        summary = fields.get("summary", "")
        desc_raw = fields.get("description")
        desc_md, desc_plain = clean_adf_to_markdown(desc_raw)

        # Reporter & Assignee
        rep_obj = fields.get("reporter") or {}
        reporter = {
            "name": rep_obj.get("name") or rep_obj.get("emailAddress") or "unknown",
            "display_name": rep_obj.get("displayName") or "Unknown Reporter",
            "email": rep_obj.get("emailAddress", ""),
        }

        assignee = None
        ass_obj = fields.get("assignee")
        if ass_obj:
            assignee = {
                "name": ass_obj.get("name") or ass_obj.get("emailAddress") or "unassigned",
                "display_name": ass_obj.get("displayName") or "Unassigned",
                "email": ass_obj.get("emailAddress", ""),
            }

        # Components & Labels
        components = [c.get("name", "") for c in fields.get("components", []) if c.get("name")]
        labels = fields.get("labels", [])

        # Timestamps
        created_at = fields.get("created", "")
        updated_at = fields.get("updated", "")
        resolved_at = fields.get("resolutiondate")
        resolution_obj = fields.get("resolution")
        resolution = resolution_obj.get("name") if isinstance(resolution_obj, dict) else resolution_obj

        # Comments
        comment_container = fields.get("comment", {})
        comment_list = comment_container.get("comments", []) if isinstance(comment_container, dict) else []
        parsed_comments = []
        for c in comment_list:
            c_author = c.get("author", {}).get("displayName") or c.get("author", {}).get("name", "user")
            c_created = c.get("created", "")
            c_body_raw = c.get("body")
            c_md, c_plain = clean_adf_to_markdown(c_body_raw)
            parsed_comments.append(
                {
                    "author": c_author,
                    "created_at": c_created,
                    "body_markdown": c_md,
                    "body_text": c_plain,
                }
            )

        # Linked issues
        linked_issues = []
        for link in fields.get("issuelinks", []):
            rel = link.get("type", {}).get("name", "relates to")
            inward = link.get("inwardIssue")
            outward = link.get("outwardIssue")
            target = inward or outward
            if target:
                linked_issues.append(
                    {
                        "relationship": rel,
                        "key": target.get("key", ""),
                        "summary": target.get("fields", {}).get("summary", ""),
                        "status": target.get("fields", {}).get("status", {}).get("name", ""),
                    }
                )

        # URL
        web_url = urljoin(self.base_url, f"browse/{key}") if key else ""

        return JiraDocument(
            id=issue_id,
            key=key,
            project_key=proj_key,
            project_name=proj_name,
            issue_type=issue_type,
            summary=summary,
            description_markdown=desc_md,
            description_text=desc_plain,
            status=status,
            priority=priority,
            reporter=reporter,
            assignee=assignee,
            components=components,
            labels=labels,
            created_at=created_at,
            updated_at=updated_at,
            resolved_at=resolved_at,
            resolution=resolution,
            url=web_url,
            comments=parsed_comments,
            linked_issues=linked_issues,
            linked_confluence_pages=[],
            metadata={"self": item.get("self")},
        )

    def save_issues_to_json(
        self,
        issues: List[JiraDocument],
        output_path: Path | str,
    ) -> Path:
        """Save retrieved issues to a structured JSON file."""
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        payload = [issue.to_dict() for issue in issues]
        with open(target, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved {len(issues)} Jira issues to {target}")
        return target


class MockJiraConnector:
    """Offline mock connector using local sample datasets for development and CI/CD."""

    def __init__(self, sample_data_path: Optional[Path | str] = None) -> None:
        self.sample_data_path = (
            Path(sample_data_path)
            if sample_data_path
            else get_project_root() / "data" / "sample" / "jira" / "issues.json"
        )

    def fetch_all_issues(
        self,
        project_key: Optional[str] = None,
        jql: Optional[str] = None,
        max_total: Optional[int] = None,
    ) -> List[JiraDocument]:
        """Load sample Jira issues and convert to JiraDocument instances."""
        if not self.sample_data_path.exists():
            raise FileNotFoundError(f"Sample Jira data file not found at {self.sample_data_path}")

        with open(self.sample_data_path, "r", encoding="utf-8") as f:
            raw_items = json.load(f)

        documents: List[JiraDocument] = []
        for item in raw_items:
            comments = [
                {
                    "author": c.get("author", "user"),
                    "created_at": c.get("created_at", ""),
                    "body_markdown": c.get("body", ""),
                    "body_text": c.get("body", ""),
                }
                for c in item.get("comments", [])
            ]
            doc = JiraDocument(
                id=str(item["id"]),
                key=item["key"],
                project_key=item["project_key"],
                project_name=item["project_name"],
                issue_type=item["issue_type"],
                summary=item["summary"],
                description_markdown=item["description"],
                description_text=item["description"],
                status=item["status"],
                priority=item["priority"],
                reporter=item.get("reporter", {}),
                assignee=item.get("assignee"),
                components=item.get("components", []),
                labels=item.get("labels", []),
                created_at=item["created_at"],
                updated_at=item["updated_at"],
                resolved_at=item.get("resolved_at"),
                resolution=item.get("resolution"),
                url=f"https://cloudscale-pay.atlassian.net/browse/{item['key']}",
                comments=comments,
                linked_issues=item.get("linked_issues", []),
                linked_confluence_pages=item.get("linked_confluence_pages", []),
                metadata={"source": "sample_mock"},
            )
            documents.append(doc)

        if project_key:
            documents = [d for d in documents if d.project_key.upper() == project_key.upper()]

        if max_total:
            documents = documents[:max_total]

        return documents

    def fetch_issue_by_key(self, issue_key: str) -> JiraDocument:
        """Fetch a single mock issue by key."""
        issues = self.fetch_all_issues()
        for issue in issues:
            if issue.key.upper() == issue_key.upper():
                return issue
        raise FileNotFoundError(f"Mock Jira issue '{issue_key}' not found.")

    def save_issues_to_json(
        self,
        issues: List[JiraDocument],
        output_path: Path | str,
    ) -> Path:
        """Save retrieved mock issues to a structured JSON file."""
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        payload = [issue.to_dict() for issue in issues]
        with open(target, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

        return target
