"""HTML and Confluence Storage Format parser and cleaner."""

from __future__ import annotations

import re
from typing import Tuple
from bs4 import BeautifulSoup, NavigableString, Tag


def clean_confluence_html(raw_html: str) -> Tuple[str, str]:
    """Parse Confluence storage/view HTML and return (markdown_text, plain_text).

    Handles Confluence macros, code blocks, tables, headers, lists, and links.
    """
    if not raw_html or not raw_html.strip():
        return "", ""

    # Pre-process Confluence specific macro tags
    soup = BeautifulSoup(raw_html, "html.parser")

    # 1. Transform Confluence code macros: <ac:structured-macro ac:name="code">
    for macro in soup.find_all(["ac:structured-macro", "structured-macro"]):
        macro_name = macro.get("ac:name") or macro.get("name") or ""
        if macro_name.lower() in ("code", "noformat"):
            code_body = macro.find(["ac:plain-text-body", "plain-text-body"])
            code_text = code_body.get_text() if code_body else macro.get_text()
            # Extract language parameter if present
            lang = ""
            for param in macro.find_all(["ac:parameter", "parameter"]):
                if (param.get("ac:name") or param.get("name")) in ("language", "lang"):
                    lang = param.get_text().strip()
                    break
            new_pre = soup.new_tag("pre")
            new_code = soup.new_tag("code")
            if lang:
                new_code["class"] = f"language-{lang}"
            new_code.string = code_text
            new_pre.append(new_code)
            macro.replace_with(new_pre)
        elif macro_name.lower() in ("info", "note", "warning", "tip"):
            rich_body = macro.find(["ac:rich-text-body", "rich-text-body"])
            panel_text = rich_body.get_text() if rich_body else macro.get_text()
            blockquote = soup.new_tag("blockquote")
            blockquote.string = f"[{macro_name.upper()}]: {panel_text.strip()}"
            macro.replace_with(blockquote)
        elif macro_name.lower() == "status":
            # Status lozenge macro
            title = ""
            for param in macro.find_all(["ac:parameter", "parameter"]):
                if (param.get("ac:name") or param.get("name")) == "title":
                    title = param.get_text().strip()
            status_text = f"[{title or 'STATUS'}]"
            macro.replace_with(NavigableString(status_text))

    # 2. Extract Plain Text
    plain_text = _extract_plain_text(soup)

    # 3. Convert to Markdown
    markdown_text = _convert_tag_to_markdown(soup)

    # Clean redundant consecutive blank lines
    markdown_text = re.sub(r"\n{3,}", "\n\n", markdown_text).strip()
    plain_text = re.sub(r"\n{3,}", "\n\n", plain_text).strip()

    return markdown_text, plain_text


def _extract_plain_text(soup: BeautifulSoup) -> str:
    """Extract clean plain text from parsed soup."""
    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _convert_tag_to_markdown(node: Tag | BeautifulSoup) -> str:
    """Recursively convert BeautifulSoup node tree to Markdown string."""
    pieces: list[str] = []

    for child in node.children:
        if isinstance(child, NavigableString):
            text = str(child)
            # Avoid emitting raw empty strings with only whitespace inside block elements
            if text:
                pieces.append(text)
            continue

        if not isinstance(child, Tag):
            continue

        tag_name = child.name.lower()

        # Headings
        if tag_name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(tag_name[1])
            inner_text = _convert_tag_to_markdown(child).strip()
            if inner_text:
                pieces.append(f"\n\n{'#' * level} {inner_text}\n\n")

        # Paragraphs & Divs
        elif tag_name in ("p", "div", "section", "article"):
            inner_text = _convert_tag_to_markdown(child).strip()
            if inner_text:
                pieces.append(f"\n\n{inner_text}\n\n")

        # Code blocks: <pre><code> or <pre>
        elif tag_name == "pre":
            code_tag = child.find("code")
            code_str = code_tag.get_text() if code_tag else child.get_text()
            lang = ""
            if code_tag and code_tag.get("class"):
                class_val = code_tag.get("class")
                classes = class_val if isinstance(class_val, list) else [str(class_val)]
                for c in classes:
                    if c.startswith("language-"):
                        lang = c.replace("language-", "")
            pieces.append(f"\n\n```{lang}\n{code_str.rstrip()}\n```\n\n")

        # Inline code: <code>
        elif tag_name == "code":
            code_str = child.get_text()
            pieces.append(f"`{code_str}`")

        # Blockquote
        elif tag_name == "blockquote":
            inner_text = _convert_tag_to_markdown(child).strip()
            lines = [f"> {line}" for line in inner_text.splitlines() if line]
            pieces.append(f"\n\n{chr(10).join(lines)}\n\n")

        # Unordered list: <ul>
        elif tag_name == "ul":
            items = []
            for li in child.find_all("li", recursive=False):
                li_text = _convert_tag_to_markdown(li).strip()
                if li_text:
                    items.append(f"- {li_text}")
            if items:
                pieces.append(f"\n\n{chr(10).join(items)}\n\n")

        # Ordered list: <ol>
        elif tag_name == "ol":
            items = []
            for idx, li in enumerate(child.find_all("li", recursive=False), start=1):
                li_text = _convert_tag_to_markdown(li).strip()
                if li_text:
                    items.append(f"{idx}. {li_text}")
            if items:
                pieces.append(f"\n\n{chr(10).join(items)}\n\n")

        # List item: <li>
        elif tag_name == "li":
            pieces.append(_convert_tag_to_markdown(child))

        # Tables: <table>
        elif tag_name == "table":
            table_md = _render_markdown_table(child)
            if table_md:
                pieces.append(f"\n\n{table_md}\n\n")

        # Links: <a href="...">
        elif tag_name == "a":
            href = child.get("href", "")
            anchor_text = _convert_tag_to_markdown(child).strip() or href
            if href:
                pieces.append(f"[{anchor_text}]({href})")
            else:
                pieces.append(anchor_text)

        # Bold: <strong>, <b>
        elif tag_name in ("strong", "b"):
            inner = _convert_tag_to_markdown(child).strip()
            if inner:
                pieces.append(f"**{inner}**")

        # Italic: <em>, <i>
        elif tag_name in ("em", "i"):
            inner = _convert_tag_to_markdown(child).strip()
            if inner:
                pieces.append(f"*{inner}*")

        # Line break: <br> / <hr>
        elif tag_name == "br":
            pieces.append("\n")
        elif tag_name == "hr":
            pieces.append("\n\n---\n\n")

        # Generic inline/container
        else:
            pieces.append(_convert_tag_to_markdown(child))

    return "".join(pieces)


def _render_markdown_table(table_tag: Tag) -> str:
    """Convert HTML table into Markdown table format."""
    rows = table_tag.find_all("tr")
    if not rows:
        return ""

    table_data: list[list[str]] = []
    for row in rows:
        cells = row.find_all(["th", "td"])
        row_content = [_convert_tag_to_markdown(cell).replace("\n", " ").strip() for cell in cells]
        if any(row_content):
            table_data.append(row_content)

    if not table_data:
        return ""

    num_cols = max(len(r) for r in table_data)
    # Pad rows that have fewer cells
    for r in table_data:
        while len(r) < num_cols:
            r.append("")

    header = table_data[0]
    separator = ["---"] * num_cols

    output_lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(separator) + " |",
    ]

    for data_row in table_data[1:]:
        output_lines.append("| " + " | ".join(data_row) + " |")

    return "\n".join(output_lines)
