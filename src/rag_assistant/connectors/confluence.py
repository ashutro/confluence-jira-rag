"""Confluence REST API Connector for CloudScale Payments RAG Assistant."""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import requests
from requests.auth import HTTPBasicAuth

from rag_assistant.config import Settings, get_project_root
from rag_assistant.connectors.html_cleaner import clean_confluence_html

logger = logging.getLogger(__name__)


@dataclass
class ConfluenceDocument:
    """Standardized document representation of a Confluence page."""

    id: str
    title: str
    space_key: str
    space_id: Optional[str]
    url: str
    version: int
    author: str
    created_at: str
    last_updated: str
    labels: List[str]
    body_storage: str
    body_markdown: str
    body_text: str
    summary: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert document to JSON-serializable dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ConfluenceDocument:
        return cls(
            id=str(data["id"]),
            title=data["title"],
            space_key=data.get("space_key", ""),
            space_id=data.get("space_id"),
            url=data.get("url", ""),
            version=int(data.get("version", 1)),
            author=data.get("author", "unknown"),
            created_at=data.get("created_at", ""),
            last_updated=data.get("last_updated", ""),
            labels=data.get("labels", []),
            body_storage=data.get("body_storage", ""),
            body_markdown=data.get("body_markdown", ""),
            body_text=data.get("body_text", ""),
            summary=data.get("summary", ""),
            metadata=data.get("metadata", {}),
        )


class ConfluenceConnector:
    """Connector to interact with Confluence Cloud REST API v2 and v1."""

    def __init__(
        self,
        base_url: str,
        email: str,
        api_token: str,
        space_key: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.api_token = api_token
        self.space_key = space_key
        self.timeout = timeout
        self.max_retries = max_retries

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
    def from_settings(cls, settings: Optional[Settings] = None) -> ConfluenceConnector:
        """Instantiate connector using application settings."""
        cfg = settings or Settings.from_env()
        cfg.validate_confluence()
        return cls(
            base_url=cfg.confluence_base_url,
            email=cfg.confluence_email,
            api_token=cfg.confluence_api_token,
            space_key=cfg.confluence_space_key,
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
                        f"Confluence rate limit reached (429). Retrying after {retry_after}s..."
                    )
                    time.sleep(retry_after)
                    continue

                # Handle Transient Server Errors (500, 502, 503, 504)
                if response.status_code in (500, 502, 503, 504) and attempt < self.max_retries:
                    wait_time = 2**attempt
                    logger.warning(
                        f"Server error {response.status_code}. Retrying attempt {attempt}/{self.max_retries} in {wait_time}s..."
                    )
                    time.sleep(wait_time)
                    continue

                if response.status_code == 401:
                    raise PermissionError(
                        "Confluence authentication failed (401). Please check CONFLUENCE_EMAIL and CONFLUENCE_API_TOKEN."
                    )
                if response.status_code == 403:
                    raise PermissionError(
                        f"Access forbidden (403) for URL: {url}. Ensure API token has access to this space/resource."
                    )
                if response.status_code == 404:
                    raise FileNotFoundError(f"Confluence resource not found (404): {url}")

                response.raise_for_status()
                return response

            except (requests.ConnectionError, requests.Timeout) as e:
                if attempt == self.max_retries:
                    raise ConnectionError(
                        f"Failed to connect to Confluence at {url} after {self.max_retries} attempts: {e}"
                    ) from e
                time.sleep(2**attempt)

        raise RuntimeError(f"Request to {url} failed after {self.max_retries} attempts.")

    def get_space_id_by_key(self, space_key: str) -> Optional[str]:
        """Fetch space ID for a given space key using Confluence v2 API."""
        endpoint = f"api/v2/spaces?keys={space_key}&limit=1"
        try:
            resp = self._request("GET", endpoint)
            data = resp.json()
            results = data.get("results", [])
            if results:
                return str(results[0]["id"])
        except Exception as e:
            logger.warning(f"Could not resolve space ID for key '{space_key}' via v2 API: {e}")
        return None

    def fetch_page_labels(self, page_id: str) -> List[str]:
        """Fetch labels associated with a given page."""
        try:
            endpoint = f"api/v2/pages/{page_id}/labels"
            resp = self._request("GET", endpoint)
            data = resp.json()
            return [item.get("name", "") for item in data.get("results", []) if item.get("name")]
        except Exception:
            return []

    def fetch_page_by_id(self, page_id: str) -> ConfluenceDocument:
        """Fetch a single Confluence page with storage body and metadata."""
        endpoint = f"api/v2/pages/{page_id}?body-format=storage"
        resp = self._request("GET", endpoint)
        page_data = resp.json()

        labels = self.fetch_page_labels(page_id)
        return self._parse_v2_page(page_data, labels_override=labels)

    def fetch_all_pages(self, space_key: Optional[str] = None) -> List[ConfluenceDocument]:
        """Fetch all pages in a given space, traversing cursor-based pagination."""
        target_space_key = space_key or self.space_key
        space_id = None
        if target_space_key:
            space_id = self.get_space_id_by_key(target_space_key)

        documents: List[ConfluenceDocument] = []
        cursor: Optional[str] = None

        while True:
            params: Dict[str, Any] = {
                "body-format": "storage",
                "limit": 25,
                "status": "current",
            }
            if space_id:
                params["space-id"] = space_id
            if cursor:
                params["cursor"] = cursor

            endpoint = "api/v2/pages"
            resp = self._request("GET", endpoint, params=params)
            data = resp.json()
            results = data.get("results", [])

            for item in results:
                page_id = item.get("id")
                labels = self.fetch_page_labels(page_id) if page_id else []
                doc = self._parse_v2_page(item, labels_override=labels, space_key_override=target_space_key)
                documents.append(doc)

            # Check next link / cursor pagination
            links = data.get("_links", {})
            next_url = links.get("next")
            if not next_url or not results:
                break

            # Extract cursor parameter from next url
            if "cursor=" in next_url:
                cursor = next_url.split("cursor=")[-1].split("&")[0]
            else:
                break

        return documents

    def _parse_v2_page(
        self,
        item: Dict[str, Any],
        labels_override: Optional[List[str]] = None,
        space_key_override: Optional[str] = None,
    ) -> ConfluenceDocument:
        """Parse raw Confluence v2 API page item into ConfluenceDocument."""
        page_id = str(item.get("id", ""))
        title = item.get("title", "Untitled")
        space_id = item.get("spaceId")
        version_info = item.get("version", {})
        version_num = version_info.get("number", 1) if isinstance(version_info, dict) else 1
        created_at = item.get("createdAt", "")
        last_updated = version_info.get("createdAt", created_at) if isinstance(version_info, dict) else created_at
        author = version_info.get("authorId", "unknown") if isinstance(version_info, dict) else "unknown"

        # Web link
        web_link = ""
        links = item.get("_links", {})
        if "webui" in links:
            web_link = urljoin(self.base_url, links["webui"])
        elif "tinyui" in links:
            web_link = urljoin(self.base_url, links["tinyui"])

        # Body extraction
        body_obj = item.get("body", {})
        storage_body = ""
        if isinstance(body_obj, dict):
            storage_body = body_obj.get("storage", {}).get("value", "")

        markdown_body, plain_body = clean_confluence_html(storage_body)

        # Generate 1-2 sentence summary from first paragraph
        summary = ""
        if plain_body:
            first_para = plain_body.split("\n\n")[0].replace("\n", " ").strip()
            summary = first_para[:250] + ("..." if len(first_para) > 250 else "")

        return ConfluenceDocument(
            id=page_id,
            title=title,
            space_key=space_key_override or self.space_key or "",
            space_id=str(space_id) if space_id else None,
            url=web_link,
            version=version_num,
            author=author,
            created_at=created_at,
            last_updated=last_updated,
            labels=labels_override or [],
            body_storage=storage_body,
            body_markdown=markdown_body,
            body_text=plain_body,
            summary=summary,
            metadata={
                "status": item.get("status", "current"),
                "parentId": item.get("parentId"),
            },
        )

    def save_pages_to_json(
        self,
        pages: List[ConfluenceDocument],
        output_path: Path | str,
    ) -> Path:
        """Save retrieved documents to a structured JSON file."""
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        payload = [page.to_dict() for page in pages]
        with open(target, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved {len(pages)} Confluence pages to {target}")
        return target


class MockConfluenceConnector:
    """Offline mock connector using local sample datasets for development and CI/CD."""

    def __init__(self, sample_data_path: Optional[Path | str] = None) -> None:
        self.sample_data_path = (
            Path(sample_data_path)
            if sample_data_path
            else get_project_root() / "data" / "sample" / "confluence" / "pages.json"
        )

    def fetch_all_pages(self, space_key: Optional[str] = None) -> List[ConfluenceDocument]:
        """Load sample pages and convert them to ConfluenceDocument instances."""
        if not self.sample_data_path.exists():
            raise FileNotFoundError(f"Sample data file not found at {self.sample_data_path}")

        with open(self.sample_data_path, "r", encoding="utf-8") as f:
            raw_items = json.load(f)

        documents: List[ConfluenceDocument] = []
        for item in raw_items:
            doc = ConfluenceDocument(
                id=item["id"],
                title=item["title"],
                space_key=item["space_key"],
                space_id="1001",
                url=item["url"],
                version=item["version"],
                author=item["author"],
                created_at=item.get("last_updated", ""),
                last_updated=item["last_updated"],
                labels=item.get("labels", []),
                body_storage=item.get("body_markdown", ""),
                body_markdown=item.get("body_markdown", ""),
                body_text=item.get("summary", ""),
                summary=item.get("summary", ""),
                metadata={"source": "sample_mock"},
            )
            documents.append(doc)

        if space_key:
            documents = [d for d in documents if d.space_key.upper() == space_key.upper()]

        return documents

    def fetch_page_by_id(self, page_id: str) -> ConfluenceDocument:
        """Fetch a single mock page by ID."""
        pages = self.fetch_all_pages()
        for p in pages:
            if p.id == page_id:
                return p
        raise FileNotFoundError(f"Mock Confluence page '{page_id}' not found.")

    def save_pages_to_json(
        self,
        pages: List[ConfluenceDocument],
        output_path: Path | str,
    ) -> Path:
        """Save retrieved mock documents to a JSON file."""
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        payload = [page.to_dict() for page in pages]
        with open(target, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

        return target
