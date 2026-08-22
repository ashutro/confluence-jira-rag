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
    raw/                # Exported source data
      confluence/       # Confluence connector output (pages.json)
    processed/          # Cleaned/chunked data later, not committed
  docs/                 # Notes and project documentation
    milestone-1-setup.md
    milestone-2-atlassian-setup.md
    milestone-3-confluence-connector.md
  src/
    rag_assistant/      # Python package
      config.py         # Environment configuration
      cli.py            # Command Line Interface
      sample_data.py    # Sample dataset loaders
      connectors/       # External source connectors
        confluence.py   # Confluence REST API connector
        html_cleaner.py # XHTML storage format cleaner
  tests/                # Automated tests
    test_sample_data.py
    test_confluence_connector.py
```

## Local Setup

Create and activate the virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

Run automated tests:

```bash
pytest tests/ -v
```

## Running the Confluence Connector (Milestone 3)

Retrieve Confluence pages and export to structured JSON:

```bash
# Offline Mock Mode (uses safe local test dataset):
rag-assistant fetch-confluence --mock --output data/raw/confluence/pages.json

# Live Confluence Cloud Mode (requires .env credentials):
rag-assistant fetch-confluence --space ENG --output data/raw/confluence/pages.json
```

See [docs/milestone-3-confluence-connector.md](file:///Users/ashutosh/Documents/Codex/2026-08-22/referenced-chatgpt-conversation-this-is-an/confluence-jira-rag/docs/milestone-3-confluence-connector.md) for full documentation.

## Status

- [x] **Milestone 1**: Local Project Setup
- [x] **Milestone 2**: Atlassian Setup & Sample Data
- [x] **Milestone 3**: Confluence Connector
- [ ] **Milestone 4**: Jira Connector
