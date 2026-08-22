# Confluence + Jira RAG Assistant

Internal knowledge assistant that will eventually answer questions from Confluence pages and Jira issues.

Milestone 1 is only project setup:

- Confirm local tools are installed.
- Create a Python virtual environment.
- Create a clean project structure.
- Initialize Git.

No Confluence, Jira, vector database, or LLM code belongs in this milestone.

## Project Structure

```text
confluence-jira-rag/
  data/
    raw/            # Exported source data later, not committed
    processed/      # Cleaned/chunked data later, not committed
  docs/             # Notes and project documentation
  src/
    rag_assistant/  # Python package
  tests/            # Automated tests
```

## Local Setup

Create and activate the virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python --version
```

Install dependencies when the project has them:

```bash
pip install -r requirements.txt
```

## Current Status

Milestone 1 foundation is ready. The next milestone should define the sample data and source-connection plan before writing any Confluence or Jira API code.
