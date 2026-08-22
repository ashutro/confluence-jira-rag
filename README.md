# Confluence + Jira RAG Assistant

Internal knowledge assistant that answers questions from Confluence pages and Jira issues.

## Project Structure

```text
confluence-jira-rag/
  data/
    sample/             # Milestone 2 sample dataset (Confluence & Jira)
      confluence/       # Confluence pages (Markdown & pages.json)
      jira/             # Jira issues (issues.json)
      queries.json      # Benchmark evaluation questions
    raw/                # Exported source data later, not committed
    processed/          # Cleaned/chunked data later, not committed
  docs/                 # Notes and project documentation
    milestone-1-setup.md
    milestone-2-atlassian-setup.md
  src/
    rag_assistant/      # Python package
      sample_data.py    # Sample dataset loaders
  tests/                # Automated tests
    test_sample_data.py # Sample dataset test suite
```

## Local Setup

Create and activate the virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run automated tests:

```bash
pytest tests/ -v
```

## Sample Dataset (Milestone 2)

- **Domain**: CloudScale Payments Platform
- **Confluence Space**: `Engineering Knowledge Base` (`ENG`) — 5 rich architectural, operational, and onboarding pages.
- **Jira Project**: `Core Payments Team` (`PAY`) — 8 realistic epics, bugs, stories, tasks, and incident postmortems.
- **Evaluation Queries**: 6 cross-referencing benchmark questions in `data/sample/queries.json`.

See [docs/milestone-2-atlassian-setup.md](file:///Users/ashutosh/Documents/Codex/2026-08-22/referenced-chatgpt-conversation-this-is-an/confluence-jira-rag/docs/milestone-2-atlassian-setup.md) for full details and instructions on setting up a live Atlassian Cloud instance.

## Status

- [x] **Milestone 1**: Local Project Setup
- [x] **Milestone 2**: Atlassian Setup & Sample Data
- [ ] **Milestone 3**: Document Loaders & Connectors
