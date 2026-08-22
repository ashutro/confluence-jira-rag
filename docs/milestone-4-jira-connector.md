# Milestone 4: Jira Connector

## Goal

Build a resilient data connector to retrieve issues from Jira Cloud, parse and clean Atlassian Document Format (ADF) and rich text descriptions/comments into clean Markdown and plain text, and export standardized JSON documents to `data/raw/jira/issues.json`.

```text
+-----------------------+
|    Jira Cloud API     |
|   (v3 /rest/api/3)    |
+-----------------------+
            |
            | HTTP Basic Auth (Email + API Token)
            v
+-----------------------------------------------------------+
| JiraConnector (Python)                                    |
|   - requests.Session with connection pooling              |
|   - JQL search with automatic pagination (startAt / total)|
|   - Exponential backoff & 429 rate limit handling         |
|   - clean_adf_to_markdown (ADF -> Markdown / Plain Text)  |
+-----------------------------------------------------------+
            |
            v
+-----------------------------------------------------------+
| JSON Output File (`data/raw/jira/issues.json`)            |
+-----------------------------------------------------------+
```

---

## 1. Jira REST API Architecture

The connector interacts with Jira Cloud REST API v3:
- **Search Endpoint**: `GET /rest/api/3/search?jql={JQL_QUERY}&startAt={OFFSET}&maxResults={LIMIT}&fields={FIELDS}`
- **Single Issue Endpoint**: `GET /rest/api/3/issue/{ISSUE_KEY}`
- **Default JQL**: `project = "{PROJECT_KEY}" ORDER BY created DESC`
- **Fields Extracted**: `summary`, `description`, `issuetype`, `status`, `priority`, `reporter`, `assignee`, `components`, `labels`, `created`, `updated`, `resolutiondate`, `resolution`, `comment`, `issuelinks`.
- **Authentication**: HTTP Basic Auth with `JIRA_EMAIL` and `JIRA_API_TOKEN`.

---

## 2. Document Schema

Retrieved issues are normalized into `JiraDocument` objects:

```json
{
  "id": "10101",
  "key": "PAY-101",
  "project_key": "PAY",
  "project_name": "Core Payments Team",
  "issue_type": "Epic",
  "summary": "Next-Gen Webhook Reliability & Idempotency Pipeline",
  "description_markdown": "Redesign the merchant webhook delivery subsystem...",
  "description_text": "Redesign the merchant webhook delivery subsystem...",
  "status": "In Progress",
  "priority": "High",
  "reporter": {
    "name": "alex.morgan@example.com",
    "display_name": "Alex Morgan",
    "role": "Staff Architect"
  },
  "assignee": {
    "name": "david.kim@example.com",
    "display_name": "David Kim",
    "role": "Senior Backend Engineer"
  },
  "components": ["Webhook Dispatcher", "Reliability", "Architecture"],
  "labels": ["epic", "q3-goals", "resilience", "webhooks"],
  "created_at": "2026-07-15T10:00:00Z",
  "updated_at": "2026-08-19T14:20:00Z",
  "resolved_at": null,
  "resolution": null,
  "url": "https://cloudscale-pay.atlassian.net/browse/PAY-101",
  "comments": [
    {
      "author": "Alex Morgan",
      "created_at": "2026-07-20T11:00:00Z",
      "body_markdown": "Phase 1 architecture review approved.",
      "body_text": "Phase 1 architecture review approved."
    }
  ],
  "linked_issues": [
    {
      "relationship": "contains",
      "key": "PAY-102"
    }
  ],
  "linked_confluence_pages": [
    {
      "id": "ENG-PAGE-01",
      "title": "Architecture Overview & Service Topology"
    }
  ],
  "metadata": {}
}
```

---

## 3. Usage & CLI Execution

### Running in Live Mode (Atlassian Cloud)

Configure `.env`:
```bash
JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_EMAIL=your-email@example.com
JIRA_API_TOKEN=your-api-token-here
JIRA_PROJECT_KEY=PAY
```

Run extraction:
```bash
rag-assistant fetch-jira --project PAY --output data/raw/jira/issues.json
```

Or with a custom JQL query:
```bash
rag-assistant fetch-jira --jql 'project = "PAY" AND status = "In Progress"' --output data/raw/jira/issues.json
```

### Running in Offline Mock Mode (No credentials required)

```bash
rag-assistant fetch-jira --mock --output data/raw/jira/issues.json
```

---

## 4. Python API Example

```python
from rag_assistant import JiraConnector, MockJiraConnector, Settings

# Option A: Live Connector
settings = Settings.from_env()
connector = JiraConnector.from_settings(settings)
issues = connector.fetch_all_issues(project_key="PAY")

# Option B: Offline Mock Connector
mock_connector = MockJiraConnector()
issues = mock_connector.fetch_all_issues(project_key="PAY")

# Export to JSON
connector.save_issues_to_json(issues, "data/raw/jira/issues.json")
```

---

## 5. Atlassian Document Format Cleaner (`clean_adf_to_markdown`)

Jira API v3 returns rich text in Atlassian Document Format (ADF JSON AST). The cleaner transforms:
- Paragraphs & Headings (`level: 1..6`).
- Code blocks (`codeBlock` with syntax language attributes).
- Bullet and ordered lists (`bulletList`, `orderedList`, `listItem`).
- Tables (`table`, `tableRow`, `tableHeader`, `tableCell`).
- Panels and quotes (`panel`, `blockquote`).
- Mentions and text marks (bold, italic, inline code, strike, links).

---

## 6. Automated Testing

All unit tests are located in `tests/test_jira_connector.py` and mock external HTTP requests via `responses`:

```bash
pytest tests/test_jira_connector.py -v
```

Tests cover:
- Authentication headers and basic auth.
- ADF tree to Markdown parsing across all node types.
- Single issue retrieval with fields and comments.
- Multi-page pagination traversal using JQL.
- HTTP 429 rate limit backoff retry handling.
- HTTP 401 Unauthorized / 404 Not Found error propagation.
- Mock connector and JSON persistence.
