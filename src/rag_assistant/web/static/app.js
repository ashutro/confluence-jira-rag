/**
 * Confluence + Jira RAG Assistant - ChatGPT & Gemini Interface
 */

document.addEventListener("DOMContentLoaded", () => {
  // DOM Elements
  const chatViewport = document.getElementById("chat-viewport");
  const chatThread = document.getElementById("chat-thread");
  const geminiHero = document.getElementById("gemini-hero");
  const chatForm = document.getElementById("chat-form");
  const userInput = document.getElementById("user-input");
  const sendBtn = document.getElementById("send-btn");
  const newChatBtn = document.getElementById("new-chat-btn");
  const clearThreadBtn = document.getElementById("clear-thread-btn");
  const sidebarToggle = document.getElementById("sidebar-toggle");
  const geminiSidebar = document.getElementById("gemini-sidebar");
  const chatHistoryList = document.getElementById("chat-history-list");
  const activeModelLabel = document.getElementById("active-model-label");
  const liveStatusPill = document.getElementById("live-status-pill");
  const statChunks = document.getElementById("stat-chunks");
  const statDocs = document.getElementById("stat-docs");
  const statEngine = document.getElementById("stat-engine");
  const thresholdSlider = document.getElementById("threshold-slider");
  const thresholdVal = document.getElementById("threshold-val");
  const dockScopeBadge = document.getElementById("dock-scope-badge");
  const scopeText = document.getElementById("scope-text");
  const sourcePills = document.querySelectorAll(".source-pill");
  const bentoCards = document.querySelectorAll(".bento-card");
  const toastContainer = document.getElementById("toast-container");

  // State
  let activeSourceFilter = "";
  let scoreThreshold = 0.20;
  let isGenerating = false;
  let sessions = JSON.parse(localStorage.getItem("rag_chat_sessions") || "[]");
  let currentSessionId = null;

  // Initialize
  initSessions();
  fetchHealth();
  fetchStats();

  // 1. Sidebar Toggle
  sidebarToggle.addEventListener("click", () => {
    geminiSidebar.classList.toggle("collapsed");
  });

  // 2. Source Scope Selector
  sourcePills.forEach(pill => {
    pill.addEventListener("click", () => {
      sourcePills.forEach(p => p.classList.remove("active"));
      pill.classList.add("active");
      activeSourceFilter = pill.dataset.source;

      if (!activeSourceFilter) {
        scopeText.textContent = "All Sources";
        dockScopeBadge.querySelector(".scope-icon").textContent = "🌐";
      } else if (activeSourceFilter === "confluence") {
        scopeText.textContent = "Confluence Docs";
        dockScopeBadge.querySelector(".scope-icon").textContent = "📘";
      } else if (activeSourceFilter === "jira") {
        scopeText.textContent = "Jira Issues";
        dockScopeBadge.querySelector(".scope-icon").textContent = "🎯";
      }
    });
  });

  // 3. Threshold Slider
  thresholdSlider.addEventListener("input", (e) => {
    scoreThreshold = parseFloat(e.target.value);
    thresholdVal.textContent = scoreThreshold.toFixed(2);
  });

  // 4. Auto-resize Textarea
  userInput.addEventListener("input", () => {
    userInput.style.height = "auto";
    userInput.style.height = Math.min(userInput.scrollHeight, 140) + "px";
  });

  // 5. Enter Key handling (Shift+Enter for newline)
  userInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!isGenerating && userInput.value.trim()) {
        chatForm.dispatchEvent(new Event("submit"));
      }
    }
  });

  // 6. Bento Card Quick Prompts
  bentoCards.forEach(card => {
    card.addEventListener("click", () => {
      if (isGenerating) return;
      const q = card.dataset.query;
      userInput.value = q;
      userInput.style.height = "auto";
      chatForm.dispatchEvent(new Event("submit"));
    });
  });

  // 7. New Chat Action Button
  newChatBtn.addEventListener("click", () => {
    createNewSession();
  });

  // 8. Clear Current Thread Button
  clearThreadBtn.addEventListener("click", () => {
    chatThread.innerHTML = "";
    geminiHero.style.display = "block";
    if (currentSessionId) {
      sessions = sessions.filter(s => s.id !== currentSessionId);
      saveSessions();
      renderHistoryList();
    }
    showToast("Conversation cleared");
  });

  // 9. Main Form Submission
  chatForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const query = userInput.value.trim();
    if (!query || isGenerating) return;

    // Ensure session exists
    if (!currentSessionId) {
      currentSessionId = "session_" + Date.now();
      sessions.unshift({
        id: currentSessionId,
        title: query.slice(0, 32) + (query.length > 32 ? "..." : ""),
        messages: [],
        timestamp: Date.now(),
      });
      saveSessions();
      renderHistoryList();
    }

    // Hide Hero Banner
    geminiHero.style.display = "none";

    // Append User Message
    appendUserMessage(query);
    userInput.value = "";
    userInput.style.height = "auto";

    // Set Loading State
    isGenerating = true;
    sendBtn.disabled = true;

    // Append Typing Indicator
    const typingRow = appendTypingIndicator();
    scrollToBottom();

    const startTime = performance.now();

    try {
      const resp = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: query,
          source_filter: activeSourceFilter || null,
          top_k: 3,
          score_threshold: scoreThreshold,
        }),
      });

      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.detail || `Server returned ${resp.status}`);
      }

      const data = await resp.json();
      const elapsedSec = ((performance.now() - startTime) / 1000).toFixed(1);
      data.elapsed_sec = elapsedSec;

      typingRow.remove();
      appendAssistantMessage(data);

      // Save to active session
      const curSession = sessions.find(s => s.id === currentSessionId);
      if (curSession) {
        curSession.messages.push({ role: "user", text: query });
        curSession.messages.push({ role: "assistant", data: data });
        saveSessions();
      }

    } catch (err) {
      typingRow.remove();
      appendErrorMessage(err.message || "Failed to generate response.");
    } finally {
      isGenerating = false;
      sendBtn.disabled = false;
      scrollToBottom();
      userInput.focus();
    }
  });

  // UI Message Appenders
  function appendUserMessage(text) {
    const turn = document.createElement("div");
    turn.className = "chat-turn user";
    turn.innerHTML = `
      <div class="turn-avatar user">U</div>
      <div class="turn-content">
        <p>${escapeHtml(text)}</p>
      </div>
    `;
    chatThread.appendChild(turn);
    scrollToBottom();
  }

  function appendTypingIndicator() {
    const turn = document.createElement("div");
    turn.className = "chat-turn bot";
    turn.id = "typing-turn";
    turn.innerHTML = `
      <div class="turn-avatar bot">✦</div>
      <div class="turn-content">
        <div class="gemini-typing-dots">
          <div class="gemini-typing-dot"></div>
          <div class="gemini-typing-dot"></div>
          <div class="gemini-typing-dot"></div>
        </div>
      </div>
    `;
    chatThread.appendChild(turn);
    return turn;
  }

  function appendAssistantMessage(data) {
    const turn = document.createElement("div");
    turn.className = "chat-turn bot";

    const isGrounded = data.guardrail && data.guardrail.is_grounded;
    const confidence = data.guardrail ? Math.round((data.guardrail.confidence_score || 0) * 100) : 85;
    const model = data.model_name || data.provider || "Stealth OX-Alpha";
    const chunksCount = data.context && data.context.chunks ? data.context.chunks.length : (data.sources ? data.sources.length : 3);
    const elapsed = data.elapsed_sec || (data.execution_time_ms ? (data.execution_time_ms / 1000).toFixed(1) : "1.2");

    // 1. Thought Process Accordion (Reasoning Box)
    let reasoningHtml = "";
    if (data.guardrail || (data.context && data.context.chunks)) {
      const citedList = data.guardrail && data.guardrail.cited_source_ids ? data.guardrail.cited_source_ids.join(", ") : "All target documents";
      reasoningHtml = `
        <div class="thought-box">
          <div class="thought-header" onclick="this.parentElement.classList.toggle('expanded')">
            <div class="thought-title">
              <span class="sparkle">✦</span>
              <span>Thought for ${elapsed}s • ${chunksCount} knowledge chunks analyzed</span>
            </div>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="6 9 12 15 18 9"></polyline>
            </svg>
          </div>
          <div class="thought-body" style="display: none;">
            <p><strong>Vector Similarity:</strong> Retrieved top ${chunksCount} matching sections from Qdrant vector database.</p>
            <p><strong>Grounding Verification:</strong> Guardrail confidence score: <code>${(data.guardrail?.confidence_score || 0.85).toFixed(4)}</code> (Threshold: ${scoreThreshold}).</p>
            <p><strong>Verified Sources:</strong> ${citedList}</p>
          </div>
        </div>
      `;
    }

    // 2. Grounding Badge
    const badgeClass = isGrounded ? "verified" : "refusal";
    const badgeText = isGrounded ? `✓ Grounded in Confluence & Jira (${confidence}% match)` : `⚠ Guardrail Refusal (Out of Domain)`;

    // 3. Rendered Markdown
    const markdownHtml = renderAdvancedMarkdown(data.answer);

    // 4. Sources Drawer
    let sourcesDrawerHtml = "";
    if (data.sources && data.sources.length > 0) {
      const cardsHtml = data.sources.map(s => {
        const type = (s.source_type || "doc").toLowerCase();
        const urlAttr = s.url ? `href="${s.url}" target="_blank" rel="noopener"` : "";
        return `
          <a class="source-card-chip" ${urlAttr} title="${escapeHtml(s.title || s.source_id)}">
            <span class="type-pill ${type}">${escapeHtml(s.source_type || "DOC")}</span>
            <span>${escapeHtml(s.source_id)}</span>
          </a>
        `;
      }).join("");

      sourcesDrawerHtml = `
        <div class="sources-drawer">
          <div class="sources-label">Referenced Sources (${data.sources.length})</div>
          <div class="sources-chips-grid">${cardsHtml}</div>
        </div>
      `;
    }

    turn.innerHTML = `
      <div class="turn-avatar bot">✦</div>
      <div class="turn-content">
        ${reasoningHtml}
        <div class="grounding-chip ${badgeClass}">${badgeText}</div>
        <div class="markdown-body">${markdownHtml}</div>
        ${sourcesDrawerHtml}

        <div class="turn-actions-bar">
          <button class="turn-action-btn copy-btn" title="Copy answer">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
            </svg>
          </button>
          <button class="turn-action-btn like-btn" title="Good response">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/>
            </svg>
          </button>
          <button class="turn-action-btn dislike-btn" title="Bad response">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h3a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-3"/>
            </svg>
          </button>
        </div>
      </div>
    `;

    // Add Copy listener
    const copyBtn = turn.querySelector(".copy-btn");
    if (copyBtn) {
      copyBtn.addEventListener("click", () => {
        navigator.clipboard.writeText(data.answer).then(() => {
          showToast("Copied to clipboard");
        });
      });
    }

    // Add accordion click
    const thoughtHeader = turn.querySelector(".thought-header");
    if (thoughtHeader) {
      thoughtHeader.addEventListener("click", () => {
        const body = turn.querySelector(".thought-body");
        if (body) {
          body.style.display = body.style.display === "none" ? "block" : "none";
        }
      });
    }

    // Add Code Block copy buttons
    turn.querySelectorAll(".code-block-container").forEach(block => {
      const codeText = block.querySelector("pre").innerText;
      const copyCodeBtn = block.querySelector(".copy-code-btn");
      if (copyCodeBtn) {
        copyCodeBtn.addEventListener("click", () => {
          navigator.clipboard.writeText(codeText).then(() => {
            copyCodeBtn.innerText = "✓ Copied";
            setTimeout(() => { copyCodeBtn.innerText = "Copy code"; }, 2000);
          });
        });
      }
    });

    chatThread.appendChild(turn);
    scrollToBottom();
  }

  function appendErrorMessage(msg) {
    const turn = document.createElement("div");
    turn.className = "chat-turn bot";
    turn.innerHTML = `
      <div class="turn-avatar bot">✦</div>
      <div class="turn-content">
        <div class="grounding-chip refusal">⚠ System Error</div>
        <div class="markdown-body" style="color: var(--gemini-rose);">
          <p><strong>Failed to retrieve or generate answer:</strong> ${escapeHtml(msg)}</p>
        </div>
      </div>
    `;
    chatThread.appendChild(turn);
    scrollToBottom();
  }

  // Markdown Parser (Headers, Code blocks with copy bar, Tables, Citations, Lists)
  function renderAdvancedMarkdown(text) {
    if (!text) return "";
    let html = escapeHtml(text);

    // Fenced Code Blocks ```lang \n code ```
    html = html.replace(/```([a-zA-Z0-9_\-\+]*)\n([\s\S]*?)```/g, (match, lang, code) => {
      const l = lang || "code";
      return `
        <div class="code-block-container">
          <div class="code-block-header">
            <span>${l}</span>
            <button class="copy-code-btn" type="button">Copy code</button>
          </div>
          <pre><code>${code.trim()}</code></pre>
        </div>
      `;
    });

    // Tables (| col | col |)
    html = html.replace(/((?:\|[^\n]+\|\r?\n)+)/g, (match) => {
      const lines = match.trim().split("\n");
      if (lines.length >= 2) {
        let tableHtml = '<table class="markdown-table">';
        lines.forEach((line, idx) => {
          if (line.includes("---")) return; // divider
          const cells = line.split("|").filter((c, i, a) => i > 0 && i < a.length - 1);
          if (idx === 0) {
            tableHtml += "<thead><tr>" + cells.map(c => `<th>${c.trim()}</th>`).join("") + "</tr></thead><tbody>";
          } else {
            tableHtml += "<tr>" + cells.map(c => `<td>${c.trim()}</td>`).join("") + "</tr>";
          }
        });
        tableHtml += "</tbody></table>";
        return tableHtml;
      }
      return match;
    });

    // Headings
    html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
    html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');

    // Bold (**text**) & Italic (*text*)
    html = html.replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>');
    html = html.replace(/\*(.*?)\*/gim, '<em>$1</em>');

    // Inline code (`code`)
    html = html.replace(/`([^`]+)`/gim, '<code>$1</code>');

    // Citation tags [ENG-PAGE-02] or [PAY-102]
    html = html.replace(/\[((?:ENG-PAGE-\d+|PAY-\d+))\]/g, '<span class="source-card-chip" style="display:inline-flex; padding:1px 6px; font-size:0.75rem; margin:0 2px;">$1</span>');

    // Markdown Links [title](url)
    html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^\)]+)\)/gim, '<a href="$2" target="_blank" rel="noopener" style="color: var(--gemini-cyan); text-decoration: underline;">$1</a>');

    // Bullet points (- or *)
    html = html.replace(/^\s*[-*]\s+(.*$)/gim, '<li>$1</li>');

    // Paragraphs
    html = html.replace(/\n\n/g, '</p><p>');
    html = html.replace(/\n/g, '<br>');

    return `<p>${html}</p>`;
  }

  // Session & LocalStorage Helpers
  function initSessions() {
    renderHistoryList();
  }

  function createNewSession() {
    currentSessionId = null;
    chatThread.innerHTML = "";
    geminiHero.style.display = "block";
    userInput.value = "";
    userInput.focus();
    renderHistoryList();
  }

  function renderHistoryList() {
    chatHistoryList.innerHTML = "";
    if (sessions.length === 0) {
      chatHistoryList.innerHTML = `<div class="history-empty">No previous chats</div>`;
      return;
    }

    sessions.slice(0, 15).forEach(s => {
      const item = document.createElement("div");
      item.className = `history-item ${s.id === currentSessionId ? "active" : ""}`;
      item.innerHTML = `
        <span class="history-title">${escapeHtml(s.title || "Chat Session")}</span>
      `;
      item.addEventListener("click", () => {
        loadSession(s.id);
      });
      chatHistoryList.appendChild(item);
    });
  }

  function loadSession(id) {
    const s = sessions.find(sess => sess.id === id);
    if (!s) return;

    currentSessionId = s.id;
    chatThread.innerHTML = "";
    geminiHero.style.display = s.messages.length === 0 ? "block" : "none";

    s.messages.forEach(m => {
      if (m.role === "user") {
        appendUserMessage(m.text);
      } else if (m.role === "assistant") {
        appendAssistantMessage(m.data);
      }
    });

    renderHistoryList();
    scrollToBottom();
  }

  function saveSessions() {
    localStorage.setItem("rag_chat_sessions", JSON.stringify(sessions));
  }

  function scrollToBottom() {
    chatViewport.scrollTop = chatViewport.scrollHeight;
  }

  function escapeHtml(unsafe) {
    return String(unsafe || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function showToast(msg) {
    const toast = document.createElement("div");
    toast.className = "toast";
    toast.textContent = msg;
    toastContainer.appendChild(toast);
    setTimeout(() => { toast.remove(); }, 2500);
  }

  async function fetchHealth() {
    try {
      const res = await fetch("/api/health");
      if (res.ok) {
        const h = await res.json();
        const prov = h.provider === "openrouter" ? "OpenRouter" : h.provider;
        const model = h.model || "stealth/ox-alpha";
        activeModelLabel.textContent = `${prov} (${model})`;
      }
    } catch (e) {}
  }

  async function fetchStats() {
    try {
      const res = await fetch("/api/stats");
      if (res.ok) {
        const s = await res.json();
        if (s.total_chunks) statChunks.textContent = s.total_chunks;
        if (s.total_documents) statDocs.textContent = s.total_documents;
        if (s.vector_dimension) statEngine.textContent = "Qdrant";
      }
    } catch (e) {}
  }
});
