# Milestone 2: Atlassian Setup & Sample Data

## Goal

Establish a realistic, safe, and rich test dataset representing an engineering organization's Confluence knowledge base and Jira project. This provides representative data for developing chunking, embedding, retrieval, and synthesis pipelines without risking production or proprietary data.

---

## 1. Test Domain Architecture

We use a fictional high-growth fintech platform: **CloudScale Payments Platform**.

| System | Name | Key | Type | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Confluence** | `Engineering Knowledge Base` | `ENG` | Knowledge Base | Architecture specs, runbooks, onboarding guides, and compliance policies. |
| **Jira** | `Core Payments Team` | `PAY` | Software (Scrum/Kanban) | Issue tracking for bugs, incidents, feature stories, tasks, and epics. |

---

## 2. Setting Up Live Atlassian Cloud (Optional)

If you wish to connect this project to a live Atlassian Cloud instance:

### Step 2.1: Create Free Atlassian Cloud Account
1. Go to [https://www.atlassian.com/try/cloud/signup](https://www.atlassian.com/try/cloud/signup).
2. Select **Jira Software + Confluence** (Free tier allows up to 10 users).
3. Set your site name (e.g. `your-company.atlassian.net`).

### Step 2.2: Create the Confluence Space
1. In Confluence, click **Spaces** > **Create space**.
2. Space Name: `Engineering Knowledge Base`
3. Space Key: `ENG`
4. Space Type: Documentation or Standard.

### Step 2.3: Create the Jira Project
1. In Jira, click **Projects** > **Create project**.
2. Template: **Scrum** or **Kanban** (Software Development).
3. Project Name: `Core Payments Team`
4. Project Key: `PAY`

### Step 2.4: Generate API Token
1. Go to [https://id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens).
2. Click **Create API token** and give it a label (e.g., `confluence-jira-rag-dev`).
3. Copy the token and configure your `.env` file:

```bash
CONFLUENCE_BASE_URL=https://your-domain.atlassian.net/wiki
CONFLUENCE_EMAIL=your-email@example.com
CONFLUENCE_API_TOKEN=your-api-token-here

JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_EMAIL=your-email@example.com
JIRA_API_TOKEN=your-api-token-here
```

---

## 3. Sample Confluence Pages Catalogue

All pages are available locally in `data/sample/confluence/` as raw Markdown and structured JSON (`pages.json`).

| Document ID | Title | File Path | Tags / Labels |
| :--- | :--- | :--- | :--- |
| **`ENG-PAGE-01`** | [Architecture Overview & Service Topology](file:///Users/ashutosh/Documents/Codex/2026-08-22/referenced-chatgpt-conversation-this-is-an/confluence-jira-rag/data/sample/confluence/architecture-overview.md) | `data/sample/confluence/architecture-overview.md` | `architecture`, `microservices`, `topology`, `redis`, `kafka`, `core-platform` |
| **`ENG-PAGE-02`** | [Incident Response Runbook: Payment Webhook 504 Gateway Timeouts](file:///Users/ashutosh/Documents/Codex/2026-08-22/referenced-chatgpt-conversation-this-is-an/confluence-jira-rag/data/sample/confluence/incident-runbook-webhook-timeouts.md) | `data/sample/confluence/incident-runbook-webhook-timeouts.md` | `runbook`, `incident-response`, `webhooks`, `sre`, `troubleshooting`, `sev-2` |
| **`ENG-PAGE-03`** | [Developer Onboarding & Local Environment Setup](file:///Users/ashutosh/Documents/Codex/2026-08-22/referenced-chatgpt-conversation-this-is-an/confluence-jira-rag/data/sample/confluence/developer-onboarding.md) | `data/sample/confluence/developer-onboarding.md` | `onboarding`, `developer-guide`, `docker`, `local-dev`, `python`, `go` |
| **`ENG-PAGE-04`** | [API Rate Limiting & Tiered Throttling Policy](file:///Users/ashutosh/Documents/Codex/2026-08-22/referenced-chatgpt-conversation-this-is-an/confluence-jira-rag/data/sample/confluence/rate-limiting-policy.md) | `data/sample/confluence/rate-limiting-policy.md` | `rate-limiting`, `api-policy`, `throttling`, `redis`, `security`, `kong` |
| **`ENG-PAGE-05`** | [Data Retention & GDPR/PCI-DSS Compliance Policy](file:///Users/ashutosh/Documents/Codex/2026-08-22/referenced-chatgpt-conversation-this-is-an/confluence-jira-rag/data/sample/confluence/data-retention-gdpr-policy.md) | `data/sample/confluence/data-retention-gdpr-policy.md` | `compliance`, `gdpr`, `pci-dss`, `data-retention`, `pii`, `security` |

---

## 4. Sample Jira Issues Catalogue

All issues are available locally in `data/sample/jira/issues.json`.

| Issue Key | Type | Priority | Status | Summary | Linked Documents |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`PAY-101`** | `Epic` | `High` | `In Progress` | Next-Gen Webhook Reliability & Idempotency Pipeline | `ENG-PAGE-01`, `ENG-PAGE-02` |
| **`PAY-102`** | `Bug` | `Highest` | `Closed` | Webhook delivery worker exhausted memory under high traffic burst | `ENG-PAGE-02` |
| **`PAY-103`** | `Bug` | `High` | `In Progress` | Intermittent 504 Gateway Timeout during batch invoice settlement | `ENG-PAGE-01`, `ENG-PAGE-02` |
| **`PAY-104`** | `Story` | `High` | `Done` | Implement Tiered Rate Limiting middleware with Redis Token Bucket | `ENG-PAGE-04` |
| **`PAY-105`** | `Task` | `Medium` | `In Review` | Update Developer Onboarding script for Apple Silicon Docker builds | `ENG-PAGE-03` |
| **`PAY-106`** | `Incident`| `Highest` | `Closed` | SEV-2 Postmortem: Database connection pool starvation during Black Friday | `ENG-PAGE-01` |
| **`PAY-107`** | `Story` | `Medium` | `To Do` | Implement automated PII anonymization cron for customer data purge older than 90 days | `ENG-PAGE-05` |
| **`PAY-108`** | `Bug` | `Low` | `Open` | Sandbox test card returns HTTP 500 when expiry date format is MM/YY instead of MM/YYYY | `ENG-PAGE-03` |

---

## 5. Offline Seed Data & Python Helper

You can work with the sample dataset directly in Python without connecting to live Atlassian servers:

```python
from rag_assistant import (
    load_sample_confluence_pages,
    load_sample_jira_issues,
    load_benchmark_queries,
)

# Load sample Confluence pages
pages = load_sample_confluence_pages()
print(f"Loaded {len(pages)} Confluence pages.")
for page in pages:
    print(f"- [{page.id}] {page.title} (tags: {', '.join(page.labels)})")

# Load sample Jira issues
issues = load_sample_jira_issues()
print(f"\nLoaded {len(issues)} Jira issues.")
for issue in issues:
    print(f"- [{issue.key}] {issue.summary} ({issue.status} / {issue.priority})")

# Load benchmark queries
queries = load_benchmark_queries()
print(f"\nLoaded {len(queries)} evaluation queries.")
```

---

## 6. Benchmark Evaluation Queries

The file `data/sample/queries.json` provides questions for evaluating RAG retrieval and answer synthesis accuracy:

1. **Webhook Troubleshooting**: *"What should an on-call engineer do when the webhook worker experiences 504 Gateway Timeouts?"* (Target: `ENG-PAGE-02`, `PAY-102`)
2. **Rate Limiting Policy**: *"What are the API rate limits for each merchant tier?"* (Target: `ENG-PAGE-04`, `PAY-104`)
3. **GDPR / Data Retention**: *"How long do we retain customer PII and financial transaction records under our GDPR policy?"* (Target: `ENG-PAGE-05`, `PAY-107`)
4. **Developer Environment**: *"Why does docker compose crash on Apple Silicon M-series Macs and what is the fix?"* (Target: `ENG-PAGE-03`, `PAY-105`)
5. **Issue Status**: *"What is the status of the intermittent 504 Gateway Timeout bug during batch settlement?"* (Target: `PAY-103`, `ENG-PAGE-01`)
6. **Incident Postmortem**: *"What caused the database connection pool starvation during Black Friday and how was it fixed?"* (Target: `PAY-106`, `ENG-PAGE-01`)

---

## 7. Next Milestone Preview

In **Milestone 3 (Document Loaders & Connectors)**, we will build:
- Confluence document loader (offline JSON/Markdown parser & REST API client).
- Jira issue loader (offline JSON parser & REST API client).
- Unified internal document schema for downstream chunking.
