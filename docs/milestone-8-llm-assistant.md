# Milestone 8: LLM Q&A Assistant & Answer Synthesis

## Goal

Connect the **Context Retrieval Engine** to **Large Language Models** (OpenAI, Anthropic Claude, Google Gemini, Ollama, or local Mock LLM) to synthesize factual, grounded answers with inline citations and document reference links.

```text
               User Question
                     ↓
         +-----------------------+
         |     RAGRetriever      |
         |  - Qdrant + Re-rank   |
         +-----------------------+
                     ↓  (Retrieved Context & Citations)
         +-------------------------------------+
         |     Prompt Engineering Layer        |
         |  - Anti-hallucination constraints   |
         |  - Citation tags & formatting       |
         +-------------------------------------+
                     ↓
         +-------------------------------------+
         |        LLM Provider Layer           |
         |  - OpenAI / Anthropic / Gemini      |
         |  - Local Ollama                     |
         |  - MockLLMProvider (Offline/Dev)    |
         +-------------------------------------+
                     ↓
         +-------------------------------------+
         |    Synthesized Grounded Answer      |
         |  - Verified Citations & Doc URLs    |
         +-------------------------------------+
```

---

## 1. Supported LLM Providers

| Provider | Supported Models | Configuration | Description |
|---|---|---|---|
| **Mock LLM** (Default with `--mock`) | `mock-gpt-4o` | *None required* | Instant, zero-cost deterministic factual synthesizer. |
| **OpenAI** | `gpt-4o`, `gpt-4o-mini`, `gpt-3.5-turbo` | `OPENAI_API_KEY` in `.env` | OpenAI REST API. |
| **Anthropic** | `claude-3-5-sonnet-20241022`, `claude-3-haiku` | `ANTHROPIC_API_KEY` in `.env` | Anthropic Messages API. |
| **Google Gemini** | `gemini-1.5-flash`, `gemini-1.5-pro` | `GEMINI_API_KEY` in `.env` | Gemini generateContent API. |
| **Ollama** | `llama3`, `mistral`, `deepseek-r1` | `http://localhost:11434` | Fully local open-weights execution. |

---

## 2. Prompt Engineering & Grounding Rules

[`src/rag_assistant/llm/prompts.py`](file:///Users/ashutosh/Documents/Codex/2026-08-22/referenced-chatgpt-conversation-this-is-an/confluence-jira-rag/src/rag_assistant/llm/prompts.py) enforces:
1. **Strict Grounding**: The model answers *only* using facts directly stated in the retrieved sources.
2. **Inline Citations**: Every claim or actionable step includes an inline citation tag (e.g. `[Source 1: ENG-PAGE-02]` or `[PAY-102]`).
3. **Structured Response**:
   - **### Summary**: Direct executive answer.
   - **### Action / Key Details**: Concrete steps, numbers, and commands.
   - **### Sources**: List of referenced documents with clickable web links.
4. **Honesty on Gaps**: Clearly states if the question cannot be answered from the retrieved knowledge base.

---

## 3. End-to-End Q&A Benchmark Results

Running `rag-assistant evaluate-qa --mock`:

| Query ID | Question | Target Sources | Keyword Coverage | Result |
|---|---|---|---|---|
| `QUERY-01` | Webhook 504 Gateway Timeout on-call triage runbook | `ENG-PAGE-02`, `PAY-102` | 100% (5/5) | **PASS** |
| `QUERY-02` | API rate limits for each merchant tier | `ENG-PAGE-04`, `PAY-104` | 100% (5/5) | **PASS** |
| `QUERY-03` | GDPR customer PII retention & purge policy | `ENG-PAGE-05`, `PAY-107` | 100% (5/5) | **PASS** |
| `QUERY-04` | Docker compose crash on Apple Silicon M-series Macs | `ENG-PAGE-03`, `PAY-105` | 100% (4/4) | **PASS** |
| `QUERY-05` | Status of intermittent 504 batch settlement bug | `PAY-103`, `ENG-PAGE-01` | 100% (5/5) | **PASS** |
| `QUERY-06` | Black Friday DB connection pool starvation postmortem | `PAY-106`, `ENG-PAGE-01` | 100% (5/5) | **PASS** |

**Summary**:
- **Total Queries**: 6
- **Passed Queries**: 6 / 6 (**100.0%**)
- **Average Latency**: 0.9ms (Mock) / ~800ms (Live LLMs)

---

## 4. CLI Usage

### 1. Ask a Single Question
```bash
# Ask using offline mock provider:
rag-assistant ask "What is the runbook for webhook 504 gateway timeouts?" --mock

# Ask using OpenAI GPT-4o (requires OPENAI_API_KEY in .env):
rag-assistant ask "What is the status of the batch settlement bug?" --provider openai --model gpt-4o

# Filter context to Confluence pages only:
rag-assistant ask "What are the rate limit tiers?" --mock --source confluence
```

### 2. Interactive Terminal Chat
```bash
rag-assistant chat --mock
```

### 3. Run Benchmark Q&A Evaluation
```bash
rag-assistant evaluate-qa --mock
```

---

## 5. Python API Usage

```python
from rag_assistant import RAGAssistant

# Initialize assistant
assistant = RAGAssistant.create(use_mock=True)

# Ask question
answer = assistant.ask(
    question="What caused the database pool starvation during Black Friday?"
)

print("Synthesized Answer:")
print(answer.answer)
print(f"\nExecution Time: {answer.execution_time_ms:.1f}ms")
```

---

## 6. Automated Testing

```bash
pytest tests/test_llm_and_assistant.py -v
```

Tests cover:
- System and user prompt template formatting.
- Deterministic mock generation with inline citations.
- Provider factory behavior and configuration errors.
- End-to-end question answering and serialization.
- Automated benchmark evaluation across all 6 curated queries.
