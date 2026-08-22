/**
 * Confluence + Jira RAG Assistant - ChatGPT Clean Web App
 */

document.addEventListener("DOMContentLoaded", () => {
  // DOM Elements
  const gptSidebar = document.getElementById("gpt-sidebar");
  const sidebarToggleBtn = document.getElementById("sidebar-toggle-btn");
  const sidebarCloseBtn = document.getElementById("sidebar-close-btn");
  const newChatBtn = document.getElementById("new-chat-btn");
  const clearThreadBtn = document.getElementById("clear-thread-btn");
  const chatHistoryList = document.getElementById("chat-history-list");
  const chatViewport = document.getElementById("chat-viewport");
  const gptHero = document.getElementById("gpt-hero");
  const chatThread = document.getElementById("chat-thread");
  const chatForm = document.getElementById("chat-form");
  const userInput = document.getElementById("user-input");
  const sendBtn = document.getElementById("send-btn");
  const activeModelLabel = document.getElementById("active-model-label");
  const statChunks = document.getElementById("stat-chunks");
  const statDocs = document.getElementById("stat-docs");
  const thresholdSlider = document.getElementById("threshold-slider");
  const thresholdVal = document.getElementById("threshold-val");
  const scopeBtns = document.querySelectorAll(".scope-btn");
  const dockScopeBadge = document.getElementById("dock-scope-badge");
  const scopeText = document.getElementById("scope-text");
  const capsuleBtns = document.querySelectorAll(".capsule-btn");
  const toastContainer = document.getElementById("toast-container");

  // State
  let activeSourceFilter = "";
  let scoreThreshold = 0.20;
  let isGenerating = false;
  let sessions = JSON.parse(localStorage.getItem("gpt_rag_sessions") || "[]");
  let currentSessionId = null;

  // Initialize
  initSessions();
  fetchHealth();
  fetchStats();
  updateSendBtnState();

  // 1. Sidebar Toggles
  if (sidebarToggleBtn) {
    sidebarToggleBtn.addEventListener("click", () => {
      gptSidebar.classList.remove("collapsed");
    });
  }
  if (sidebarCloseBtn) {
    sidebarCloseBtn.addEventListener("click", () => {
      gptSidebar.classList.add("collapsed");
    });
  }

  // 2. Source Scope Selector
  scopeBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      scopeBtns.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      activeSourceFilter = btn.dataset.source;

      const dot = dockScopeBadge.querySelector(".scope-dot");
      if (!activeSourceFilter) {
        scopeText.textContent = "All Knowledge";
        if (dot) dot.className = "scope-dot all";
      } else if (activeSourceFilter === "confluence") {
        scopeText.textContent = "Confluence Only";
        if (dot) dot.className = "scope-dot conf";
      } else if (activeSourceFilter === "jira") {
        scopeText.textContent = "Jira Only";
        if (dot) dot.className = "scope-dot jira";
      }
    });
  });

  // 3. Sensitivity Threshold
  thresholdSlider.addEventListener("input", (e) => {
    scoreThreshold = parseFloat(e.target.value);
    thresholdVal.textContent = scoreThreshold.toFixed(2);
  });

  // 4. Auto-resize Textarea & Send Button State
  userInput.addEventListener("input", () => {
    userInput.style.height = "auto";
    userInput.style.height = Math.min(userInput.scrollHeight, 180) + "px";
    updateSendBtnState();
  });

  function updateSendBtnState() {
    const hasText = userInput.value.trim().length > 0;
    sendBtn.disabled = !hasText || isGenerating;
  }

  // 5. Enter Key handling (Shift+Enter for newline)
  userInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!isGenerating && userInput.value.trim()) {
        chatForm.dispatchEvent(new Event("submit"));
      }
    }
  });

  // 6. Capsule Quick Prompts
  capsuleBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      if (isGenerating) return;
      const q = btn.dataset.query;
      userInput.value = q;
      userInput.style.height = "auto";
      updateSendBtnState();
      chatForm.dispatchEvent(new Event("submit"));
    });
  });

  // 7. New Chat Action Button
  newChatBtn.addEventListener("click", () => {
    createNewSession();
  });

  // 8. Clear Current Conversation
  clearThreadBtn.addEventListener("click", () => {
    chatThread.innerHTML = "";
    gptHero.style.display = "block";
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
        title: query.slice(0, 34) + (query.length > 34 ? "..." : ""),
        messages: [],
        timestamp: Date.now(),
      });
      saveSessions();
      renderHistoryList();
    }

    // Hide Hero
    gptHero.style.display = "none";

    // Append User Message
    appendUserMessage(query);
    userInput.value = "";
    userInput.style.height = "auto";
    updateSendBtnState();

    // Set Loading State
    isGenerating = true;
    sendBtn.disabled = true;

    // Append Typing Indicator
    const typingTurn = appendTypingIndicator();
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

      typingTurn.remove();
      appendAssistantMessage(data);

      // Save to active session
      const curSession = sessions.find(s => s.id === currentSessionId);
      if (curSession) {
        curSession.messages.push({ role: "user", text: query });
        curSession.messages.push({ role: "assistant", data: data });
        saveSessions();
      }

    } catch (err) {
      typingTurn.remove();
      appendErrorMessage(err.message || "Failed to generate answer.");
    } finally {
      isGenerating = false;
      updateSendBtnState();
      scrollToBottom();
      userInput.focus();
    }
  });

  // UI Message Appenders
  function appendUserMessage(text) {
    const turn = document.createElement("div");
    turn.className = "message-turn user";
    turn.innerHTML = `
      <div class="user-bubble">${escapeHtml(text)}</div>
    `;
    chatThread.appendChild(turn);
    scrollToBottom();
  }

  function appendTypingIndicator() {
    const turn = document.createElement("div");
    turn.className = "message-turn assistant";
    turn.id = "typing-turn";
    turn.innerHTML = `
      <div class="assistant-body">
        <div class="gpt-typing-dots">
          <div class="gpt-dot"></div>
          <div class="gpt-dot"></div>
          <div class="gpt-dot"></div>
        </div>
      </div>
    `;
    chatThread.appendChild(turn);
    return turn;
  }

  function appendAssistantMessage(data) {
    const turn = document.createElement("div");
    turn.className = "message-turn assistant";

    const isGrounded = data.guardrail && data.guardrail.is_grounded;
    const confidence = data.guardrail ? Math.round((data.guardrail.confidence_score || 0) * 100) : 85;
    const chunksCount = data.context && data.context.chunks ? data.context.chunks.length : (data.sources ? data.sources.length : 3);
    const elapsed = data.elapsed_sec || (data.execution_time_ms ? (data.execution_time_ms / 1000).toFixed(1) : "1.2");

    // 1. Thought Accordion (ChatGPT o1/o3 style)
    let thoughtHtml = "";
    if (data.guardrail || (data.context && data.context.chunks)) {
      const citedList = data.guardrail && data.guardrail.cited_source_ids ? data.guardrail.cited_source_ids.join(", ") : "All target documents";
      thoughtHtml = `
        <div class="thought-dropdown">
          <div class="thought-summary">
            <span>Thought for ${elapsed} seconds (${chunksCount} sources retrieved)</span>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M6 9l6 6 6-6"/>
            </svg>
          </div>
          <div class="thought-content" style="display: none;">
            <p>• Similarity score: <code>${(data.guardrail?.confidence_score || 0.85).toFixed(4)}</code> (Threshold: ${scoreThreshold})</p>
            <p>• Grounded in: ${citedList}</p>
          </div>
        </div>
      `;
    }

    // 2. Grounding status pill
    const badgeClass = isGrounded ? "verified" : "refusal";
    const badgeText = isGrounded ? `✓ Grounded in Confluence & Jira (${confidence}% match)` : `⚠ Guardrail Refusal`;

    // 3. Formatted Markdown
    const markdownHtml = renderGptMarkdown(data.answer);

    // 4. Citation Pills Row
    let citationsHtml = "";
    if (data.sources && data.sources.length > 0) {
      const chips = data.sources.map(s => {
        const type = (s.source_type || "doc").toLowerCase();
        const urlAttr = s.url ? `href="${s.url}" target="_blank" rel="noopener"` : "";
        return `
          <a class="citation-chip" ${urlAttr} title="${escapeHtml(s.title || s.source_id)}">
            <span class="chip-tag ${type}">${escapeHtml(s.source_type || "DOC")}</span>
            <span>${escapeHtml(s.source_id)}</span>
          </a>
        `;
      }).join("");

      citationsHtml = `
        <div class="citations-row">
          <span style="font-size:0.75rem; color:var(--gpt-text-muted); margin-right:4px;">Sources:</span>
          ${chips}
        </div>
      `;
    }

    turn.innerHTML = `
      <div class="assistant-body">
        ${thoughtHtml}
        <div class="grounded-badge ${badgeClass}">${badgeText}</div>
        <div class="gpt-prose">${markdownHtml}</div>
        ${citationsHtml}

        <div class="message-actions-bar">
          <button class="action-btn copy-btn" title="Copy response">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
            </svg>
          </button>
          <button class="action-btn" title="Good response">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/>
            </svg>
          </button>
          <button class="action-btn" title="Bad response">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h3a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-3"/>
            </svg>
          </button>
        </div>
      </div>
    `;

    // Copy Action
    const copyBtn = turn.querySelector(".copy-btn");
    if (copyBtn) {
      copyBtn.addEventListener("click", () => {
        navigator.clipboard.writeText(data.answer).then(() => {
          showToast("Copied to clipboard");
        });
      });
    }

    // Thought Toggle
    const thoughtSummary = turn.querySelector(".thought-summary");
    if (thoughtSummary) {
      thoughtSummary.addEventListener("click", () => {
        const content = turn.querySelector(".thought-content");
        if (content) {
          content.style.display = content.style.display === "none" ? "block" : "none";
        }
      });
    }

    // Code Block Copy Buttons
    turn.querySelectorAll(".code-container").forEach(block => {
      const codeText = block.querySelector("pre").innerText;
      const copyCodeBtn = block.querySelector(".code-copy-btn");
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
    turn.className = "message-turn assistant";
    turn.innerHTML = `
      <div class="assistant-body">
        <div class="grounded-badge refusal">⚠ Error</div>
        <div class="gpt-prose" style="color: var(--gpt-accent-red);">
          <p>${escapeHtml(msg)}</p>
        </div>
      </div>
    `;
    chatThread.appendChild(turn);
    scrollToBottom();
  }

  // Markdown Parser
  function renderGptMarkdown(text) {
    if (!text) return "";
    let html = escapeHtml(text);

    // Fenced Code Blocks ```lang \n code ```
    html = html.replace(/```([a-zA-Z0-9_\-\+]*)\n([\s\S]*?)```/g, (match, lang, code) => {
      const l = lang || "text";
      return `
        <div class="code-container">
          <div class="code-header">
            <span>${l}</span>
            <button class="code-copy-btn" type="button">Copy code</button>
          </div>
          <pre><code>${code.trim()}</code></pre>
        </div>
      `;
    });

    // Tables (| col | col |)
    html = html.replace(/((?:\|[^\n]+\|\r?\n)+)/g, (match) => {
      const lines = match.trim().split("\n");
      if (lines.length >= 2) {
        let tableHtml = '<table class="gpt-table">';
        lines.forEach((line, idx) => {
          if (line.includes("---")) return;
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
    html = html.replace(/\[((?:ENG-PAGE-\d+|PAY-\d+))\]/g, '<span class="citation-chip" style="padding:1px 5px; font-size:0.75rem; margin:0 2px;">$1</span>');

    // Markdown Links [title](url)
    html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^\)]+)\)/gim, '<a href="$2" target="_blank" rel="noopener" style="color: var(--gpt-text-link); text-decoration: underline;">$1</a>');

    // Bullet points
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
    gptHero.style.display = "block";
    userInput.value = "";
    updateSendBtnState();
    userInput.focus();
    renderHistoryList();
  }

  function renderHistoryList() {
    chatHistoryList.innerHTML = "";
    if (sessions.length === 0) {
      chatHistoryList.innerHTML = `<div class="history-empty">No conversations yet</div>`;
      return;
    }

    sessions.slice(0, 15).forEach(s => {
      const item = document.createElement("div");
      item.className = `history-entry ${s.id === currentSessionId ? "active" : ""}`;
      item.textContent = s.title || "Conversation";
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
    gptHero.style.display = s.messages.length === 0 ? "block" : "none";

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
    localStorage.setItem("gpt_rag_sessions", JSON.stringify(sessions));
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
        const prov = h.provider === "openrouter" ? "ChatGPT 4o" : h.provider;
        const model = h.model || "stealth/ox-alpha";
        activeModelLabel.textContent = `${prov} • ${model}`;
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
      }
    } catch (e) {}
  }
});
