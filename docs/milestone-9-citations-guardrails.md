# Milestone 9: Citations & Guardrails

## Goal

Ensure that every generated answer is **trustworthy, factual, verifiable, and strictly grounded**, while protecting against hallucinations and out-of-domain speculation with standardized **"I don't know"** fallback behavior.

```text
               User Question
                     ↓
         +-----------------------+
         |     RAGRetriever      |
         |  (Threshold Filter)   |
         +-----------------------+
                     ↓
       [Top Score >= Threshold?]
         /                     \
       YES                      NO
        ↓                        ↓
 +-------------------+  +--------------------------------+
 | Grounded LLM      |  | Direct Guardrail Fallback      |
 | Synthesis         |  | "I don't know based on current |
 +-------------------+  | Confluence/Jira records..."    |
        ↓               +--------------------------------+
 +-------------------+                   |
 | Citation Verifier |                   |
 | & Source Links    |                   |
 +-------------------+                   |
        \                               /
         v                             v
       Trustworthy, Verifiable Grounded Answer
```

---

## 1. Core Guardrail Mechanisms

### A. "I Don't Know" Fallback & Confidence Thresholds
If retrieval similarity score is below the confidence threshold (default: `0.20` or `--score-threshold`) or if the query contains no topical lexical overlap with the knowledge base, the system bypasses LLM synthesis and immediately returns a clean, honest response:

```markdown
### Summary
I do not have enough information in the Confluence documentation or Jira records to answer this question.

- **Query**: *"What is the best recipe for chocolate chip cookies?"*
- **Status**: No matching internal knowledge base articles or Jira issues met the confidence threshold.
- **Guidance**: Please verify your search terms or consult the relevant Confluence space (`ENG`) or Jira project (`PAY`).
```

### B. Citation Verification & Hallucination Defense
[`GuardrailService`](file:///Users/ashutosh/Documents/Codex/2026-08-22/referenced-chatgpt-conversation-this-is-an/confluence-jira-rag/src/rag_assistant/guardrails/service.py) inspects the synthesized answer:
- Scans for all cited document IDs (e.g. `[ENG-PAGE-02]`, `[PAY-102]`).
- Compares each against the retrieved context's available sources.
- Flags any hallucinated/fabricated document IDs in `GuardrailResult.hallucinated_source_ids`.
- Validates that `citations_valid == True` and `is_grounded == True`.

### C. Clickable Source Links & References
Appends a verified footer with document titles, source types, IDs, and clickable URLs:
```markdown
### Sources & References
- **[CONFLUENCE ENG-PAGE-02]**: Incident Response Runbook: Payment Webhook 504 Gateway Timeouts - [View in Confluence](https://cloudscale-pay.atlassian.net/wiki/spaces/ENG/pages/1002/Runbook+Webhook+504+Timeouts)
- **[JIRA PAY-102]**: [PAY-102] Webhook worker exhausted memory under traffic burst - [View in Jira](https://cloudscale-pay.atlassian.net/browse/PAY-102)
```

---

## 2. Guardrail Benchmark Evaluation

Run automated guardrail defense evaluation:

```bash
rag-assistant test-guardrails --mock
```

Results:

| Test ID | Query Type | Query | Expected Refusal | Actual Refusal | Confidence Score | Result |
|---|---|---|---|---|---|---|
| `Test 1` | In-Domain | *"What is the runbook for webhook 504 gateway timeouts?"* | `False` | `False` | `0.8602` | **PASS** |
| `Test 2` | In-Domain | *"What are the rate limit tiers for merchants?"* | `False` | `False` | `0.3630` | **PASS** |
| `Test 3` | Out-of-Domain | *"What is the best recipe for chocolate chip cookies?"* | `True` | `True` | `0.3183` | **PASS** |
| `Test 4` | Out-of-Domain | *"Who was the captain of the 1998 French World Cup team?"* | `True` | `True` | `0.2424` | **PASS** |
| `Test 5` | Out-of-Domain | *"What is the secret flight schedule to the Moon?"* | `True` | `True` | `0.2503` | **PASS** |

**Guardrail Protection Rate**: **5/5 (100.0%)**

---

## 3. CLI Usage

### Ask with Custom Confidence Threshold
```bash
rag-assistant ask "What is the runbook for webhook 504?" --score-threshold 0.30 --mock
```

### Run Guardrail Defense Tests
```bash
rag-assistant test-guardrails --mock
```

---

## 4. Automated Tests

```bash
pytest tests/test_guardrails.py -v
```

Includes:
- Threshold check unit tests (above vs below vs empty context).
- Citation validation tests (valid vs fabricated IDs like `PAY-999`).
- Source link enrichment formatting tests.
- In-domain Q&A success tests.
- Adversarial out-of-domain refusal tests.
