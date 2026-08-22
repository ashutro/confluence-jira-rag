/**
 * Confluence + Jira RAG Assistant Web App (Milestone 10)
 */

document.addEventListener("DOMContentLoaded", () => {
  // DOM Elements
  const chatViewport = document.getElementById("chat-viewport");
  const messagesContainer = document.getElementById("messages-container");
  const welcomeCard = document.getElementById("welcome-card");
  const chatForm = document.getElementById("chat-form");
  const userInput = document.getElementById("user-input");
  const sendBtn = document.getElementById("send-btn");
  const clearChatBtn = document.getElementById("clear-chat-btn");
  const filterChips = document.querySelectorAll(".filter-chip");
  const sourceBadge = document.getElementById("source-badge");
  const thresholdSlider = document.getElementById("threshold-slider");
  const thresholdVal = document.getElementById("threshold-val");
  const sampleBtns = document.querySelectorAll(".sample-btn");
  const modelNameBadge = document.getElementById("model-name");
  const statChunks = document.getElementById("stat-chunks");
  const statDocs = document.getElementById("stat-docs");
  const toastContainer = document.getElementById("toast-container");

  // State
  let activeSourceFilter = "";
  let scoreThreshold = 0.20;
  let isGenerating = false;

  // Initialize stats & health
  fetchStats();
  fetchHealth();

  // 1. Source Filter toggles
  filterChips.forEach(chip => {
    chip.addEventListener("click", () => {
      filterChips.forEach(c => c.classList.remove("active"));
      chip.classList.add("active");
      activeSourceFilter = chip.dataset.source;

      if (!activeSourceFilter) {
        sourceBadge.textContent = "All Knowledge";
        sourceBadge.style.color = "var(--accent-primary)";
      } else if (activeSourceFilter === "confluence") {
        sourceBadge.textContent = "Confluence Only";
        sourceBadge.style.color = "var(--accent-cyan)";
      } else if (activeSourceFilter === "jira") {
        sourceBadge.textContent = "Jira Only";
        sourceBadge.style.color = "var(--accent-amber)";
      }
    });
  });

  // 2. Threshold slider
  thresholdSlider.addEventListener("input", (e) => {
    scoreThreshold = parseFloat(e.target.value);
    thresholdVal.textContent = scoreThreshold.toFixed(2);
  });

  // 3. Auto-resize textarea
  userInput.addEventListener("input", () => {
    userInput.style.height = "auto";
    userInput.style.height = Math.min(userInput.scrollHeight, 120) + "px";
  });

  // 4. Enter to submit (Shift+Enter for newline)
  userInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!isGenerating) {
        chatForm.dispatchEvent(new Event("submit"));
      }
    }
  });

  // 5. Sample Query buttons
  sampleBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      if (isGenerating) return;
      const q = btn.dataset.query;
      userInput.value = q;
      userInput.style.height = "auto";
      chatForm.dispatchEvent(new Event("submit"));
    });
  });

  // 6. Clear chat
  clearChatBtn.addEventListener("click", () => {
    messagesContainer.innerHTML = "";
    welcomeCard.style.display = "block";
    showToast("Chat cleared");
  });

  // 7. Form submission
  chatForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const query = userInput.value.trim();
    if (!query || isGenerating) return;

    // Hide welcome card
    welcomeCard.style.display = "none";

    // Append User Message
    appendUserMessage(query);
    userInput.value = "";
    userInput.style.height = "auto";

    // Set generating state
    isGenerating = true;
    sendBtn.disabled = true;

    // Append Typing Indicator
    const typingIndicator = appendTypingIndicator();
    scrollToBottom();

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
        throw new Error(errData.detail || `Server returned error ${resp.status}`);
      }

      const data = await resp.json();
      typingIndicator.remove();
      appendAssistantMessage(data);

    } catch (err) {
      typingIndicator.remove();
      appendErrorMessage(err.message || "An unexpected error occurred.");
    } finally {
      isGenerating = false;
      sendBtn.disabled = false;
      scrollToBottom();
      userInput.focus();
    }
  });

  // UI Helper Functions
  function appendUserMessage(text) {
    const row = document.createElement("div");
    row.className = "message-row user";
    row.innerHTML = `
      <div class="avatar user">You</div>
      <div class="message-bubble">${escapeHtml(text)}</div>
    `;
    messagesContainer.appendChild(row);
    scrollToBottom();
  }

  function appendTypingIndicator() {
    const row = document.createElement("div");
    row.className = "message-row bot";
    row.id = "typing-row";
    row.innerHTML = `
      <div class="avatar bot">AI</div>
      <div class="message-bubble">
        <div class="typing-indicator">
          <div class="typing-dot"></div>
          <div class="typing-dot"></div>
          <div class="typing-dot"></div>
        </div>
      </div>
    `;
    messagesContainer.appendChild(row);
    return row;
  }

  function appendAssistantMessage(data) {
    const row = document.createElement("div");
    row.className = "message-row bot";

    const isGrounded = data.guardrail && data.guardrail.is_grounded;
    const badgeClass = isGrounded ? "verified" : "fallback";
    const badgeText = isGrounded ? "✓ Grounded & Verified" : "⚠ Guardrail Refusal";
    const latency = data.execution_time_ms ? `${data.execution_time_ms.toFixed(1)}ms` : "";
    const model = data.model_name || data.provider || "Assistant";

    // Format markdown body
    const formattedHtml = renderSimpleMarkdown(data.answer);

    // Render source chips
    let sourcesHtml = "";
    if (data.sources && data.sources.length > 0) {
      const sourceBadges = data.sources.map(s => {
        const typeClass = s.source_type.toLowerCase();
        const urlAttr = s.url ? `href="${s.url}" target="_blank" rel="noopener"` : "";
        return `
          <a class="source-badge-item" ${urlAttr}>
            <span class="source-tag-type ${typeClass}">${escapeHtml(s.source_type)}</span>
            <span>${escapeHtml(s.source_id)}</span>
          </a>
        `;
      }).join("");

      sourcesHtml = `
        <div class="sources-card">
          <div class="sources-toggle">
            <span>Referenced Documents (${data.sources.length})</span>
          </div>
          <div class="source-badges-row">${sourceBadges}</div>
        </div>
      `;
    }

    row.innerHTML = `
      <div class="avatar bot">AI</div>
      <div class="message-bubble">
        <div class="message-header">
          <div class="message-meta">
            <span class="guardrail-badge ${badgeClass}">${badgeText}</span>
            <span class="latency-badge">${model} &bull; ${latency}</span>
          </div>
          <div class="message-actions">
            <button class="action-icon-btn copy-btn" title="Copy Answer">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
              </svg>
            </button>
          </div>
        </div>
        <div class="message-body">${formattedHtml}</div>
        ${sourcesHtml}
      </div>
    `;

    // Add copy listener
    const copyBtn = row.querySelector(".copy-btn");
    if (copyBtn) {
      copyBtn.addEventListener("click", () => {
        navigator.clipboard.writeText(data.answer).then(() => {
          showToast("Answer copied to clipboard!");
        });
      });
    }

    messagesContainer.appendChild(row);
    scrollToBottom();
  }

  function appendErrorMessage(errorMsg) {
    const row = document.createElement("div");
    row.className = "message-row bot";
    row.innerHTML = `
      <div class="avatar bot">AI</div>
      <div class="message-bubble" style="border-color: var(--accent-rose);">
        <div class="message-header">
          <div class="message-meta">
            <span class="guardrail-badge" style="background: rgba(244,63,94,0.15); color: var(--accent-rose); border: 1px solid rgba(244,63,94,0.3);">Error</span>
          </div>
        </div>
        <div class="message-body">
          <p style="color: var(--accent-rose);"><strong>Failed to generate response:</strong> ${escapeHtml(errorMsg)}</p>
        </div>
      </div>
    `;
    messagesContainer.appendChild(row);
    scrollToBottom();
  }

  function renderSimpleMarkdown(text) {
    if (!text) return "";
    let html = escapeHtml(text);

    // Headings (### )
    html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
    html = html.replace(/^## (.*$)/gim, '<h3>$1</h3>');

    // Bold (**text**)
    html = html.replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>');

    // Italic (*text*)
    html = html.replace(/\*(.*?)\*/gim, '<em>$1</em>');

    // Inline code (`code`)
    html = html.replace(/`([^`]+)`/gim, '<code>$1</code>');

    // Markdown Links [text](url)
    html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^\)]+)\)/gim, '<a href="$2" target="_blank" rel="noopener" style="color: var(--accent-cyan); text-decoration: underline;">$1</a>');

    // Bullet points (- or *)
    html = html.replace(/^\s*[-*]\s+(.*$)/gim, '<li>$1</li>');

    // Numbered lists (1. 2. etc.)
    html = html.replace(/^\s*\d+\.\s+(.*$)/gim, '<li>$1</li>');

    // Line breaks
    html = html.replace(/\n\n/g, '</p><p>');
    html = html.replace(/\n/g, '<br>');

    return `<p>${html}</p>`;
  }

  function scrollToBottom() {
    chatViewport.scrollTop = chatViewport.scrollHeight;
  }

  function escapeHtml(unsafe) {
    return unsafe
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
    setTimeout(() => {
      toast.remove();
    }, 2500);
  }

  async function fetchStats() {
    try {
      const res = await fetch("/api/stats");
      if (res.ok) {
        const stats = await res.json();
        if (stats.total_chunks) statChunks.textContent = stats.total_chunks;
        if (stats.total_documents) statDocs.textContent = stats.total_documents;
      }
    } catch (e) {}
  }

  async function fetchHealth() {
    try {
      const res = await fetch("/api/health");
      if (res.ok) {
        const h = await res.json();
        if (h.model) modelNameBadge.textContent = `${h.provider} (${h.model})`;
      }
    } catch (e) {}
  }
});
