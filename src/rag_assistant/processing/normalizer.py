"""Document normalizer transforming Confluence and Jira records into UnifiedDocument instances."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Union

from rag_assistant.connectors.confluence import ConfluenceDocument
from rag_assistant.connectors.jira import JiraDocument
from rag_assistant.core.models import UnifiedDocument


def normalize_confluence_page(
    page: Union[ConfluenceDocument, Dict[str, Any]],
) -> UnifiedDocument:
    """Transform a Confluence page into a UnifiedDocument."""
    if isinstance(page, ConfluenceDocument):
        p_id = page.id
        title = page.title
        space_key = page.space_key
        url = page.url
        author = page.author
        created_at = page.created_at
        last_updated = page.last_updated
        labels = list(page.labels)
        version = page.version
        body_md = page.body_markdown or page.body_text
        summary = page.summary
        metadata = dict(page.metadata)
    else:
        p_id = str(page.get("id", ""))
        title = page.get("title", "Untitled")
        space_key = page.get("space_key", "")
        url = page.get("url", "")
        author = page.get("author", "unknown")
        created_at = page.get("created_at", "")
        last_updated = page.get("last_updated", created_at)
        labels = list(page.get("labels", []))
        version = page.get("version", 1)
        body_md = page.get("body_markdown") or page.get("body_text", "")
        summary = page.get("summary", "")
        metadata = dict(page.get("metadata", {}))

    # Format structured text content
    tags = sorted(list(set([space_key.lower()] + [lbl.lower() for lbl in labels] + ["confluence"])))
    
    header_meta = [
        f"- **Source**: Confluence Space `{space_key}`",
        f"- **Document ID**: `{p_id}`",
        f"- **Author**: `{author}`",
        f"- **Version**: `v{version}`",
        f"- **Last Updated**: `{last_updated}`",
    ]
    if labels:
        header_meta.append(f"- **Labels**: `{', '.join(labels)}`")

    meta_block = "\n".join(header_meta)
    
    # If body_md already starts with # Title, avoid duplication
    clean_body = body_md.strip()
    if clean_body.startswith(f"# {title}"):
        text_content = clean_body
    else:
        text_content = f"# {title}\n\n{meta_block}\n\n{clean_body}"

    doc_metadata = {
        **metadata,
        "space_key": space_key,
        "version": version,
        "summary": summary,
        "labels": labels,
    }

    return UnifiedDocument(
        doc_id=f"confluence:{p_id}",
        source_type="confluence",
        source_id=p_id,
        title=title,
        url=url,
        author=author,
        created_at=created_at,
        updated_at=last_updated,
        tags=tags,
        metadata=doc_metadata,
        text_content=text_content,
    )


def normalize_jira_issue(
    issue: Union[JiraDocument, Dict[str, Any]],
) -> UnifiedDocument:
    """Transform a Jira issue into a UnifiedDocument."""
    if isinstance(issue, JiraDocument):
        key = issue.key
        summary = issue.summary
        project_key = issue.project_key
        issue_type = issue.issue_type
        status = issue.status
        priority = issue.priority
        reporter = issue.reporter.get("display_name") or issue.reporter.get("name", "unknown")
        assignee = (issue.assignee.get("display_name") or issue.assignee.get("name", "Unassigned")) if issue.assignee else "Unassigned"
        components = list(issue.components)
        labels = list(issue.labels)
        created_at = issue.created_at
        updated_at = issue.updated_at
        resolved_at = issue.resolved_at
        resolution = issue.resolution
        url = issue.url
        desc_md = issue.description_markdown or issue.description_text
        comments = list(issue.comments)
        linked_issues = list(issue.linked_issues)
        linked_pages = list(issue.linked_confluence_pages)
        metadata = dict(issue.metadata)
    else:
        key = issue.get("key", "")
        summary = issue.get("summary", "")
        project_key = issue.get("project_key", "")
        issue_type = issue.get("issue_type", "Task")
        status = issue.get("status", "Open")
        priority = issue.get("priority", "Medium")
        
        rep_obj = issue.get("reporter", {})
        reporter = rep_obj.get("display_name") or rep_obj.get("name", "unknown") if isinstance(rep_obj, dict) else str(rep_obj)
        
        ass_obj = issue.get("assignee")
        assignee = (ass_obj.get("display_name") or ass_obj.get("name", "Unassigned")) if isinstance(ass_obj, dict) else (str(ass_obj) if ass_obj else "Unassigned")
        
        components = list(issue.get("components", []))
        labels = list(issue.get("labels", []))
        created_at = issue.get("created_at", "")
        updated_at = issue.get("updated_at", created_at)
        resolved_at = issue.get("resolved_at")
        resolution = issue.get("resolution")
        url = issue.get("url", "")
        desc_md = issue.get("description_markdown") or issue.get("description", "")
        comments = list(issue.get("comments", []))
        linked_issues = list(issue.get("linked_issues", []))
        linked_pages = list(issue.get("linked_confluence_pages", []))
        metadata = dict(issue.get("metadata", {}))

    # Formulate tags
    tags = sorted(list(set(
        [project_key.lower()]
        + [c.lower() for c in components]
        + [lbl.lower() for lbl in labels]
        + [issue_type.lower(), status.lower(), "jira"]
    )))

    # Construct rich Markdown text representation
    lines = [
        f"# [{key}] {summary}",
        f"- **Project**: `{project_key}` | **Type**: `{issue_type}` | **Priority**: `{priority}`",
        f"- **Status**: `{status}` | **Resolution**: `{resolution or 'Unresolved'}`",
        f"- **Reporter**: `{reporter}` | **Assignee**: `{assignee}`",
    ]
    if components:
        lines.append(f"- **Components**: `{', '.join(components)}`")
    if labels:
        lines.append(f"- **Labels**: `{', '.join(labels)}`")
    lines.append(f"- **Created**: `{created_at}` | **Updated**: `{updated_at}`")
    if resolved_at:
        lines.append(f"- **Resolved At**: `{resolved_at}`")

    lines.append("\n## Description\n")
    lines.append(desc_md.strip() or "*No description provided.*")

    if comments:
        lines.append("\n## Comments\n")
        for idx, c in enumerate(comments, start=1):
            c_author = c.get("author", "User")
            c_time = c.get("created_at", "")
            c_body = c.get("body_markdown") or c.get("body_text") or c.get("body", "")
            time_str = f" ({c_time})" if c_time else ""
            lines.append(f"### Comment {idx} by {c_author}{time_str}")
            lines.append(f"{c_body.strip()}\n")

    if linked_issues or linked_pages:
        lines.append("\n## Relationships & Linked Documents\n")
        for link in linked_issues:
            lines.append(f"- **{link.get('relationship', 'Related')}**: [{link.get('key')}] {link.get('summary', '')} ({link.get('status', '')})")
        for page in linked_pages:
            lines.append(f"- **Confluence Page**: [{page.get('id', '')}] {page.get('title', '')}")

    text_content = "\n".join(lines).strip()

    doc_metadata = {
        **metadata,
        "project_key": project_key,
        "issue_type": issue_type,
        "status": status,
        "priority": priority,
        "reporter": reporter,
        "assignee": assignee,
        "components": components,
        "labels": labels,
        "resolution": resolution,
        "linked_issues": linked_issues,
        "linked_confluence_pages": linked_pages,
    }

    return UnifiedDocument(
        doc_id=f"jira:{key}",
        source_type="jira",
        source_id=key,
        title=f"[{key}] {summary}",
        url=url,
        author=reporter,
        created_at=created_at,
        updated_at=updated_at,
        tags=tags,
        metadata=doc_metadata,
        text_content=text_content,
    )


class DocumentNormalizer:
    """Orchestrates normalization for heterogeneous data sources into UnifiedDocument lists."""

    @staticmethod
    def normalize_confluence(
        pages: List[Union[ConfluenceDocument, Dict[str, Any]]],
    ) -> List[UnifiedDocument]:
        return [normalize_confluence_page(p) for p in pages]

    @staticmethod
    def normalize_jira(
        issues: List[Union[JiraDocument, Dict[str, Any]]],
    ) -> List[UnifiedDocument]:
        return [normalize_jira_issue(i) for i in issues]

    @classmethod
    def normalize_all(
        cls,
        confluence_pages: List[Union[ConfluenceDocument, Dict[str, Any]]],
        jira_issues: List[Union[JiraDocument, Dict[str, Any]]],
    ) -> List[UnifiedDocument]:
        docs: List[UnifiedDocument] = []
        docs.extend(cls.normalize_confluence(confluence_pages))
        docs.extend(cls.normalize_jira(jira_issues))
        return docs

    @staticmethod
    def save_documents_to_json(
        documents: List[UnifiedDocument],
        output_path: Path | str,
    ) -> Path:
        """Save normalized UnifiedDocuments to a JSON file."""
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        payload = [doc.to_dict() for doc in documents]
        with open(target, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

        return target
