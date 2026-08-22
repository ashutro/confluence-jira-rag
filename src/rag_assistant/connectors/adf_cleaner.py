"""Atlassian Document Format (ADF) and Jira rich text parser and cleaner."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple, Union


def clean_adf_to_markdown(content: Union[Dict[str, Any], str, None]) -> Tuple[str, str]:
    """Parse Atlassian Document Format (ADF) JSON or plain string into (markdown, plain_text).

    Returns:
        Tuple[str, str]: (markdown_representation, plain_text_representation)
    """
    if not content:
        return "", ""

    if isinstance(content, str):
        # Plain text / legacy markdown string
        clean_str = content.strip()
        return clean_str, clean_str

    if not isinstance(content, dict):
        return "", ""

    md = _parse_adf_node(content)
    md = re.sub(r"\n{3,}", "\n\n", md).strip()

    # Extract plain text by stripping markdown symbols
    plain = _extract_plain_from_adf(content)
    plain = re.sub(r"\n{3,}", "\n\n", plain).strip()

    return md, plain


def _parse_adf_node(node: Dict[str, Any]) -> str:
    """Recursively parse an ADF node into Markdown."""
    node_type = node.get("type", "")
    content = node.get("content", [])
    attrs = node.get("attrs", {})

    if node_type == "doc":
        return "".join(_parse_adf_node(child) for child in content)

    elif node_type == "paragraph":
        inner = "".join(_parse_adf_node(child) for child in content)
        return f"\n\n{inner}\n\n" if inner.strip() else ""

    elif node_type == "heading":
        level = attrs.get("level", 1)
        inner = "".join(_parse_adf_node(child) for child in content).strip()
        return f"\n\n{'#' * level} {inner}\n\n"

    elif node_type == "text":
        text = node.get("text", "")
        marks = node.get("marks", [])
        return _apply_marks(text, marks)

    elif node_type == "codeBlock":
        lang = attrs.get("language", "")
        code_text = "".join(child.get("text", "") for child in content)
        return f"\n\n```{lang}\n{code_text.rstrip()}\n```\n\n"

    elif node_type == "blockquote":
        inner = "".join(_parse_adf_node(child) for child in content).strip()
        lines = [f"> {line}" for line in inner.splitlines() if line]
        return f"\n\n{chr(10).join(lines)}\n\n"

    elif node_type == "bulletList":
        items = []
        for li in content:
            li_text = "".join(_parse_adf_node(c) for c in li.get("content", [])).strip()
            if li_text:
                items.append(f"- {li_text}")
        return f"\n\n{chr(10).join(items)}\n\n" if items else ""

    elif node_type == "orderedList":
        items = []
        for idx, li in enumerate(content, start=1):
            li_text = "".join(_parse_adf_node(c) for c in li.get("content", [])).strip()
            if li_text:
                items.append(f"{idx}. {li_text}")
        return f"\n\n{chr(10).join(items)}\n\n" if items else ""

    elif node_type == "listItem":
        return "".join(_parse_adf_node(child) for child in content)

    elif node_type == "rule":
        return "\n\n---\n\n"

    elif node_type == "panel":
        panel_type = attrs.get("panelType", "info").upper()
        inner = "".join(_parse_adf_node(child) for child in content).strip()
        lines = [f"> [{panel_type}] {line}" for line in inner.splitlines() if line]
        return f"\n\n{chr(10).join(lines)}\n\n"

    elif node_type == "mention":
        text = attrs.get("text", "") or node.get("text", "@user")
        return f"**{text}**"

    elif node_type == "table":
        return _render_adf_table(content)

    elif node_type in ("tableRow", "tableHeader", "tableCell"):
        return "".join(_parse_adf_node(child) for child in content)

    elif node_type == "hardBreak":
        return "\n"

    # Default fallback for unknown container nodes
    return "".join(_parse_adf_node(child) for child in content)


def _apply_marks(text: str, marks: List[Dict[str, Any]]) -> str:
    """Apply markdown formatting marks to text (bold, italic, code, link, etc.)."""
    result = text
    for mark in marks:
        mtype = mark.get("type", "")
        mattrs = mark.get("attrs", {})
        if mtype == "strong":
            result = f"**{result}**"
        elif mtype == "em":
            result = f"*{result}*"
        elif mtype == "code":
            result = f"`{result}`"
        elif mtype == "strike":
            result = f"~~{result}~~"
        elif mtype == "link":
            href = mattrs.get("href", "")
            result = f"[{result}]({href})" if href else result
    return result


def _render_adf_table(rows: List[Dict[str, Any]]) -> str:
    """Render ADF table rows to Markdown table."""
    if not rows:
        return ""

    table_data: List[List[str]] = []
    for row in rows:
        row_cells = []
        for cell in row.get("content", []):
            cell_text = "".join(_parse_adf_node(c) for c in cell.get("content", [])).strip()
            cell_text = cell_text.replace("\n", " ")
            row_cells.append(cell_text)
        if any(row_cells):
            table_data.append(row_cells)

    if not table_data:
        return ""

    num_cols = max(len(r) for r in table_data)
    for r in table_data:
        while len(r) < num_cols:
            r.append("")

    header = table_data[0]
    separator = ["---"] * num_cols

    output_lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(separator) + " |",
    ]
    for row in table_data[1:]:
        output_lines.append("| " + " | ".join(row) + " |")

    return f"\n\n{chr(10).join(output_lines)}\n\n"


def _extract_plain_from_adf(node: Dict[str, Any]) -> str:
    """Recursively extract plain unformatted text from ADF tree."""
    node_type = node.get("type", "")
    content = node.get("content", [])

    if node_type == "text":
        return node.get("text", "")

    if node_type == "mention":
        return node.get("attrs", {}).get("text", "@user")

    if node_type == "hardBreak":
        return "\n"

    pieces = [_extract_plain_from_adf(child) for child in content]
    return " ".join(p for p in pieces if p.strip())
