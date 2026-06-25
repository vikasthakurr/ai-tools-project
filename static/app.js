/**
 * Text-to-SQL Frontend Application
 * ==================================
 * Connects to FastAPI backend via Fetch API.
 * Handles loading states, error states, retry logic,
 * SQL rendering, and result table rendering.
 */

// ============================================================
// CONFIGURATION
// ============================================================

const CONFIG = {
  apiBase: window.location.origin + "/api",
  maxRetries: 2,
  retryDelayMs: 1500,
  requestTimeoutMs: 30000,
  maxHistoryItems: 30,
};

const ENDPOINTS = {
  query: `${CONFIG.apiBase}/query`,
  schema: `${CONFIG.apiBase}/schema`,
  health: `${CONFIG.apiBase}/health`,
  history: `${CONFIG.apiBase}/history`,
};

// ============================================================
// DOM ELEMENTS
// ============================================================

const DOM = {
  // Form
  form: document.getElementById("query-form"),
  input: document.getElementById("question-input"),
  submitBtn: document.getElementById("submit-btn"),
  btnText: document.querySelector(".btn-text"),
  btnLoading: document.querySelector(".btn-loading"),
  charCurrent: document.getElementById("char-current"),

  // Results
  resultsSection: document.getElementById("results-section"),
  sqlPanel: document.getElementById("sql-panel"),
  sqlOutput: document.getElementById("sql-output"),
  copySqlBtn: document.getElementById("copy-sql-btn"),
  errorPanel: document.getElementById("error-panel"),
  errorMessage: document.getElementById("error-message"),
  tablePanel: document.getElementById("table-panel"),
  tableHead: document.getElementById("table-head"),
  tableBody: document.getElementById("table-body"),
  rowCount: document.getElementById("row-count"),

  // History
  historyList: document.getElementById("history-list"),
  historyCount: document.getElementById("history-count"),
};

// ============================================================
// STATE
// ============================================================

const state = {
  isLoading: false,
  currentRequest: null, // AbortController for cancellation
  history: [],
};

// ============================================================
// API CLIENT (with retry logic)
// ============================================================

/**
 * Make an API request with automatic retry on failure.
 * @param {string} url - Request URL
 * @param {object} options - Fetch options
 * @param {number} retries - Number of retries remaining
 * @returns {Promise<object>} Parsed JSON response
 */
async function apiRequest(url, options = {}, retries = CONFIG.maxRetries) {
  // Create abort controller for timeout
  const controller = new AbortController();
  state.currentRequest = controller;

  const timeoutId = setTimeout(
    () => controller.abort(),
    CONFIG.requestTimeoutMs,
  );

  const fetchOptions = {
    ...options,
    signal: controller.signal,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  };

  try {
    const response = await fetch(url, fetchOptions);
    clearTimeout(timeoutId);

    // Handle HTTP errors
    if (!response.ok) {
      const errorBody = await response.json().catch(() => ({}));

      // Rate limited — no retry, show specific message
      if (response.status === 429) {
        throw new ApiError(
          errorBody.detail || "Too many requests. Please wait a moment.",
          response.status,
          false, // don't retry
        );
      }

      // Server error — retry if attempts remain
      if (response.status >= 500 && retries > 0) {
        console.warn(
          `Server error ${response.status}, retrying in ${CONFIG.retryDelayMs}ms...`,
        );
        await delay(CONFIG.retryDelayMs);
        return apiRequest(url, options, retries - 1);
      }

      throw new ApiError(
        errorBody.detail ||
          errorBody.error ||
          `Server error (${response.status})`,
        response.status,
        false,
      );
    }

    return await response.json();
  } catch (error) {
    clearTimeout(timeoutId);

    // Timeout (AbortError)
    if (error.name === "AbortError") {
      if (retries > 0) {
        console.warn("Request timed out, retrying...");
        await delay(CONFIG.retryDelayMs);
        return apiRequest(url, options, retries - 1);
      }
      throw new ApiError(
        "Request timed out. The server may be busy. Please try again.",
        0,
        false,
      );
    }

    // Network error (offline, DNS, etc.)
    if (error instanceof TypeError) {
      if (retries > 0) {
        console.warn("Network error, retrying...");
        await delay(CONFIG.retryDelayMs);
        return apiRequest(url, options, retries - 1);
      }
      throw new ApiError(
        "Cannot connect to server. Please check if it is running.",
        0,
        false,
      );
    }

    // Re-throw ApiErrors as-is
    if (error instanceof ApiError) throw error;

    // Unknown errors
    throw new ApiError(
      error.message || "An unexpected error occurred.",
      0,
      false,
    );
  } finally {
    state.currentRequest = null;
  }
}

/**
 * Custom error class for API failures.
 */
class ApiError extends Error {
  constructor(message, statusCode = 0, retryable = false) {
    super(message);
    this.name = "ApiError";
    this.statusCode = statusCode;
    this.retryable = retryable;
  }
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// ============================================================
// EVENT LISTENERS
// ============================================================

// Form submission
DOM.form.addEventListener("submit", handleSubmit);

// Character counter
DOM.input.addEventListener("input", updateCharCount);

// Enter to submit (Shift+Enter for newline)
DOM.input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    DOM.form.dispatchEvent(new Event("submit"));
  }
});

// Sample question chips
document.querySelectorAll(".chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    const question = chip.dataset.question;
    DOM.input.value = question;
    updateCharCount();
    DOM.input.focus();
  });
});

// Copy SQL button
DOM.copySqlBtn.addEventListener("click", handleCopySQL);

// ============================================================
// MAIN QUERY HANDLER
// ============================================================

async function handleSubmit(e) {
  e.preventDefault();

  const question = DOM.input.value.trim();

  // Validation
  if (!question) {
    shakeInput();
    return;
  }
  if (question.length > 500) {
    showError("Question must be 500 characters or fewer.");
    return;
  }
  if (state.isLoading) return;

  // Start loading
  setLoadingState(true);
  hideAllPanels();

  try {
    // Call backend API
    const data = await apiRequest(ENDPOINTS.query, {
      method: "POST",
      body: JSON.stringify({ question }),
    });

    // Show results section
    DOM.resultsSection.classList.remove("hidden");

    if (data.success) {
      // Success: show SQL + results
      renderSQL(data.sql);
      renderResults(data.columns, data.results);
      addToHistory(question, true, data.sql);
    } else {
      // Backend returned an error (invalid query, CANNOT_ANSWER, etc.)
      if (data.sql) renderSQL(data.sql);
      showError(
        data.error ||
          "Could not generate a valid query. Try rephrasing your question.",
      );
      addToHistory(question, false, data.sql);
    }
  } catch (error) {
    // Network/timeout/server error
    DOM.resultsSection.classList.remove("hidden");
    showError(error.message);
    addToHistory(question, false, null);
  } finally {
    setLoadingState(false);
  }
}

// ============================================================
// UI STATE MANAGEMENT
// ============================================================

function setLoadingState(loading) {
  state.isLoading = loading;
  DOM.submitBtn.disabled = loading;
  DOM.input.readOnly = loading;

  DOM.btnText.classList.toggle("hidden", loading);
  DOM.btnLoading.classList.toggle("hidden", !loading);

  if (loading) {
    DOM.input.classList.add("loading");
  } else {
    DOM.input.classList.remove("loading");
  }
}

function hideAllPanels() {
  DOM.sqlPanel.classList.add("hidden");
  DOM.errorPanel.classList.add("hidden");
  DOM.tablePanel.classList.add("hidden");
}

function updateCharCount() {
  const len = DOM.input.value.length;
  DOM.charCurrent.textContent = len;
  DOM.charCurrent.style.color = len > 450 ? "#ef4444" : "";
}

function shakeInput() {
  DOM.input.classList.add("shake");
  DOM.input.focus();
  setTimeout(() => DOM.input.classList.remove("shake"), 500);
}

// ============================================================
// SQL RENDERING
// ============================================================

function renderSQL(sql) {
  if (!sql) return;

  // Format SQL for readability
  const formatted = formatSQL(sql);
  DOM.sqlOutput.textContent = formatted;
  DOM.sqlPanel.classList.remove("hidden");
}

function formatSQL(sql) {
  // Add line breaks before major SQL clauses
  const clauses = [
    "FROM",
    "WHERE",
    "JOIN",
    "LEFT JOIN",
    "RIGHT JOIN",
    "INNER JOIN",
    "CROSS JOIN",
    "GROUP BY",
    "ORDER BY",
    "HAVING",
    "LIMIT",
    "UNION",
    "UNION ALL",
    "EXCEPT",
    "INTERSECT",
  ];

  let formatted = sql.trim();

  clauses.forEach((clause) => {
    // Match the clause as a keyword (not inside a string)
    const regex = new RegExp(`\\s+(${clause})\\b`, "gi");
    formatted = formatted.replace(regex, `\n$1`);
  });

  // Indent sub-clauses
  formatted = formatted.replace(/\n(AND|OR)\b/gi, "\n  $1");

  return formatted;
}

function handleCopySQL() {
  const sql = DOM.sqlOutput.textContent;
  if (!sql) return;

  navigator.clipboard
    .writeText(sql)
    .then(() => {
      // Show feedback
      const btn = DOM.copySqlBtn;
      const original = btn.innerHTML;
      btn.innerHTML = '<span style="color:#22c55e">Copied!</span>';
      btn.disabled = true;
      setTimeout(() => {
        btn.innerHTML = original;
        btn.disabled = false;
      }, 1500);
    })
    .catch(() => {
      // Fallback for older browsers
      const textarea = document.createElement("textarea");
      textarea.value = sql;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
    });
}

// ============================================================
// RESULTS TABLE RENDERING
// ============================================================

function renderResults(columns, rows) {
  if (!columns || !rows) {
    showEmptyState();
    return;
  }

  // Row count badge
  const count = rows.length;
  DOM.rowCount.textContent = `${count} row${count !== 1 ? "s" : ""}${count >= 100 ? " (limited)" : ""}`;

  if (count === 0) {
    showEmptyState();
    return;
  }

  // Build table header
  DOM.tableHead.innerHTML = `<tr>${columns
    .map((col) => `<th>${escapeHtml(col)}</th>`)
    .join("")}</tr>`;

  // Build table body
  DOM.tableBody.innerHTML = rows
    .map((row) => {
      const cells = columns
        .map((col) => {
          const value = row[col];
          const cellClass = isNumeric(value) ? ' class="num"' : "";
          const display = formatCellValue(value);
          return `<td${cellClass}>${display}</td>`;
        })
        .join("");
      return `<tr>${cells}</tr>`;
    })
    .join("");

  DOM.tablePanel.classList.remove("hidden");
}

function showEmptyState() {
  DOM.rowCount.textContent = "0 rows";
  DOM.tableHead.innerHTML = "";
  DOM.tableBody.innerHTML = `
        <tr>
            <td colspan="99" style="text-align:center;color:var(--text-muted);padding:2rem;">
                No results found for this query.
            </td>
        </tr>`;
  DOM.tablePanel.classList.remove("hidden");
}

function formatCellValue(value) {
  if (value === null || value === undefined) {
    return '<span style="color:var(--text-muted);font-style:italic">NULL</span>';
  }
  if (typeof value === "number") {
    // Format large numbers with commas, decimals to 2 places
    if (Number.isInteger(value)) {
      return escapeHtml(value.toLocaleString());
    }
    return escapeHtml(
      value.toLocaleString(undefined, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      }),
    );
  }
  return escapeHtml(String(value));
}

function isNumeric(value) {
  return typeof value === "number";
}

// ============================================================
// ERROR DISPLAY
// ============================================================

function showError(message) {
  DOM.errorMessage.textContent = message;
  DOM.errorPanel.classList.remove("hidden");
}

// ============================================================
// QUERY HISTORY
// ============================================================

function addToHistory(question, success, sql = null) {
  const entry = {
    question,
    success,
    sql,
    time: new Date().toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    }),
    timestamp: new Date().toISOString(),
  };

  state.history.unshift(entry);

  // Cap history
  if (state.history.length > CONFIG.maxHistoryItems) {
    state.history = state.history.slice(0, CONFIG.maxHistoryItems);
  }

  renderHistory();
}

function renderHistory() {
  DOM.historyCount.textContent = state.history.length;

  if (state.history.length === 0) {
    DOM.historyList.innerHTML =
      '<p style="color:var(--text-muted);font-size:0.8rem;padding:0.5rem 0;">No queries yet.</p>';
    return;
  }

  DOM.historyList.innerHTML = state.history
    .map(
      (entry, idx) => `
        <div class="history-item" data-index="${idx}" role="button" tabindex="0" aria-label="Re-run: ${escapeAttr(entry.question)}">
            <div class="history-status ${entry.success ? "success" : "failure"}"></div>
            <span class="history-question">${escapeHtml(entry.question)}</span>
            <span class="history-time">${entry.time}</span>
        </div>
    `,
    )
    .join("");

  // Click to re-run a history item
  DOM.historyList.querySelectorAll(".history-item").forEach((item) => {
    const handler = () => {
      const idx = parseInt(item.dataset.index);
      const entry = state.history[idx];
      if (entry) {
        DOM.input.value = entry.question;
        updateCharCount();
        DOM.input.focus();
        window.scrollTo({ top: 0, behavior: "smooth" });
      }
    };
    item.addEventListener("click", handler);
    item.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") handler();
    });
  });
}

// ============================================================
// SERVER HISTORY (load on page open)
// ============================================================

async function loadServerHistory() {
  try {
    const data = await apiRequest(ENDPOINTS.history, { method: "GET" }, 0);
    if (data.history && data.history.length > 0) {
      state.history = data.history.map((h) => ({
        question: h.question,
        success: h.success,
        sql: h.sql || null,
        time: formatTimestamp(h.timestamp),
        timestamp: h.timestamp,
      }));
      renderHistory();
    }
  } catch (e) {
    // Non-critical — silently ignore
    console.warn("Could not load history:", e.message);
  }
}

function formatTimestamp(isoString) {
  try {
    return new Date(isoString).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
}

// ============================================================
// HEALTH CHECK (startup indicator)
// ============================================================

async function checkHealth() {
  try {
    const data = await apiRequest(ENDPOINTS.health, { method: "GET" }, 0);
    if (data.status === "unhealthy") {
      console.warn("Server health: unhealthy", data);
    } else if (data.gemini === "not configured") {
      console.warn("Gemini API not configured — queries will fail");
    } else {
      console.info("Server healthy:", data);
    }
  } catch (e) {
    console.warn("Health check failed:", e.message);
  }
}

// ============================================================
// UTILITY FUNCTIONS
// ============================================================

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function escapeAttr(text) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

// ============================================================
// INITIALIZATION
// ============================================================

(function init() {
  // Update char count on load (if input has value from browser autofill)
  updateCharCount();

  // Check server health
  checkHealth();

  // Load server-side history
  loadServerHistory();

  // Focus input
  DOM.input.focus();

  console.info("Text-to-SQL app initialized");
})();
