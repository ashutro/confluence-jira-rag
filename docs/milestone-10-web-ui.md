# Milestone 10: Interactive Web User Interface

## Goal

Provide a responsive, modern web application for employees and engineers to interact with the Confluence + Jira RAG Assistant directly in their browser with dark glassmorphic styling, clickable citation badges, and confidence meters.

```text
               Browser / Web Client
       (Vanilla HTML5 / CSS3 / ES6 JS)
                     |
            REST API (FastAPI)
                     |
       +----------------------------+
       |   POST /api/ask            |
       |   GET  /api/stats          |
       |   GET  /api/samples        |
       |   GET  /api/health         |
       +----------------------------+
                     |
       +----------------------------+
       |   RAGAssistant             |
       |   (Retrieval + Guardrails  |
       |    + LLM Generation)       |
       +----------------------------+
```

---

## 1. Web Application Features

### A. Dark Glassmorphic Design System
- **Curated Theme**: Deep obsidian background (`#080c14`), frosted glass message cards with backdrop blur, glowing indigo/cyan accents (`#6366f1` / `#06b6d4`), and typography powered by **Inter**, **Outfit**, and **JetBrains Mono**.
- **Responsive Layout**: Adapts gracefully across desktop and mobile screen sizes.

### B. Interactive Controls & Sidebar
- **Live Knowledge Base Stats Widget**: Real-time display of vector chunks (77), document count (13), and vector engine (Qdrant).
- **Source Filter Chips**: Filter answers across All Sources, Confluence Docs Only, or Jira Issues Only.
- **Confidence Threshold Slider**: Adjust guardrail refusal sensitivity dynamically (`0.00` to `1.00`, default `0.20`).
- **One-Click Suggested Questions**: Instant prompt pills for triage runbooks, rate limit policies, GDPR retention rules, Docker setups, and adversarial test questions.
- **Copy to Clipboard**: Quick copy button for generated answers with animated toast notifications.

### C. Trust & Guardrails Visualization
- **Grounded Verification Badge**: Green `✓ Grounded & Verified` tag for validated answers vs yellow `⚠ Guardrail Refusal` for out-of-domain queries.
- **Clickable Citation Badges**: Expandable reference drawer with direct hyperlinks to Confluence spaces (`ENG`) and Jira issues (`PAY`).

---

## 2. API Reference

| Endpoint | Method | Description | Example Request / Response |
|---|---|---|---|
| `/` | `GET` | Serves Single-Page Web Application | HTML5 App |
| `/api/health` | `GET` | Health check & active model status | `{"status": "healthy", "provider": "mock", "model": "mock-gpt-4o"}` |
| `/api/stats` | `GET` | Knowledge base chunk & document counts | `{"total_chunks": 77, "total_documents": 13, "collection": "knowledge_base"}` |
| `/api/samples` | `GET` | Curated sample benchmark queries | `[{"id": "QUERY-01", "question": "..."}]` |
| `/api/ask` | `POST` | Ask a question with guardrails & citations | `POST {"question": "...", "top_k": 3, "score_threshold": 0.20}` |

---

## 3. Starting the Web Server

Start the local web server:

```bash
# Start in mock mode (offline, zero API keys required):
rag-assistant serve --host 127.0.0.1 --port 8000 --mock

# Start with OpenAI GPT-4o (requires OPENAI_API_KEY in .env):
rag-assistant serve --host 127.0.0.1 --port 8000 --provider openai --model gpt-4o
```

Then open your browser at **`http://localhost:8000`**.

---

## 4. Automated Testing

```bash
pytest tests/test_web_api.py -v
```

Tests cover:
- Health check endpoint `/api/health`.
- Stats endpoint `/api/stats`.
- Sample queries endpoint `/api/samples`.
- Question answering endpoint `/api/ask` (valid payload & empty validation).
- Static HTML index and CSS/JS asset delivery.
