# Milestone 3: Confluence Connector

## Goal

Build a resilient data connector to retrieve pages from Confluence, clean the Confluence Storage Format XHTML/HTML into clean Markdown and plain text, and export standardized JSON documents to `data/raw/confluence/pages.json`.

```text
+-----------------------+
|  Confluence Cloud API |
|   (v2 /api/v2/pages)  |
+-----------------------+
            |
            | HTTP Basic Auth (Email + API Token)
            v
+-----------------------------------------------------------+
| ConfluenceConnector (Python)                              |
|   - requests.Session with connection pooling              |
|   - Automatic cursor pagination traversal                 |
|   - Exponential backoff & 429 rate limit handling         |
|   - clean_confluence_html (XHTML -> Markdown / Plain Text)|
+-----------------------------------------------------------+
            |
            v
+-----------------------------------------------------------+
| JSON Output File (`data/raw/confluence/pages.json`)       |
+-----------------------------------------------------------+
```

---

## 1. Confluence REST API Architecture

The connector uses the Confluence Cloud REST API v2:
- **Base Endpoint**: `https://{your-domain}.atlassian.net/wiki/api/v2/`
- **Space Lookup**: `GET /api/v2/spaces?keys={SPACE_KEY}`
- **Page Retrieval**: `GET /api/v2/pages?space-id={SPACE_ID}&body-format=storage&status=current&limit=25`
- **Page Labels**: `GET /api/v2/pages/{PAGE_ID}/labels`
- **Pagination**: Handled via `_links.next` cursor strings until exhausted.
- **Authentication**: HTTP Basic Auth with `CONFLUENCE_EMAIL` and `CONFLUENCE_API_TOKEN`.

---

## 2. Document Schema

Retrieved pages are normalized into `ConfluenceDocument` objects and serialized as JSON:

```json
{
  "id": "ENG-PAGE-01",
  "title": "Architecture Overview & Service Topology",
  "space_key": "ENG",
  "space_id": "1001",
  "url": "https://cloudscale-pay.atlassian.net/wiki/spaces/ENG/pages/1001/Architecture+Overview",
  "version": 4,
  "author": "alex.morgan@example.com",
  "created_at": "2026-08-15T14:30:00Z",
  "last_updated": "2026-08-15T14:30:00Z",
  "labels": ["architecture", "microservices", "topology", "redis", "kafka", "core-platform"],
  "body_storage": "<p>Raw XHTML storage format...</p>",
  "body_markdown": "# Architecture Overview & Service Topology\n\n...",
  "body_text": "Core architectural blueprint of CloudScale Payments...",
  "summary": "Core architectural blueprint of CloudScale Payments, describing microservices topology...",
  "metadata": {
    "status": "current",
    "parentId": null
  }
}
```

---

## 3. Usage & CLI Execution

### Running in Live Mode (Atlassian Cloud)

Configure `.env`:
```bash
CONFLUENCE_BASE_URL=https://your-domain.atlassian.net/wiki
CONFLUENCE_EMAIL=your-email@example.com
CONFLUENCE_API_TOKEN=your-api-token-here
CONFLUENCE_SPACE_KEY=ENG
```

Run extraction:
```bash
rag-assistant fetch-confluence --space ENG --output data/raw/confluence/pages.json
```

### Running in Offline Mock Mode (No credentials required)

```bash
rag-assistant fetch-confluence --mock --output data/raw/confluence/pages.json
```

---

## 4. Python API Example

```python
from rag_assistant import ConfluenceConnector, MockConfluenceConnector, Settings

# Option A: Live Connector
settings = Settings.from_env()
connector = ConfluenceConnector.from_settings(settings)
pages = connector.fetch_all_pages(space_key="ENG")

# Option B: Offline Mock Connector
mock_connector = MockConfluenceConnector()
pages = mock_connector.fetch_all_pages(space_key="ENG")

# Export to JSON
connector.save_pages_to_json(pages, "data/raw/confluence/pages.json")
```

---

## 5. Storage Format Cleaner (`clean_confluence_html`)

Confluence pages store markup in XHTML storage format with custom tags. `clean_confluence_html` strips boilerplate and converts:
- `<ac:structured-macro ac:name="code">` to Markdown code blocks with syntax tags.
- `<ac:structured-macro ac:name="info|warning|note">` to blockquotes.
- Tables (`<table>`) to standard GitHub Markdown tables.
- Lists (`<ul>`, `<ol>`), headers (`<h1>`-`<h6>`), links (`<a>`), bold/italic formatting.

---

## 6. Automated Testing

All unit tests are located in `tests/test_confluence_connector.py` and mock external HTTP requests via `responses`:

```bash
pytest tests/test_confluence_connector.py -v
```

Tests cover:
- Authentication headers and basic auth.
- Space ID lookup and single page retrieval.
- Multi-page pagination traversal.
- HTTP 429 rate limit backoff retry handling.
- HTTP 401 Unauthorized / 404 Not Found error propagation.
- Confluence storage XHTML to Markdown conversion.
- Mock connector and JSON persistence.
