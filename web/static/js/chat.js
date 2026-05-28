const SESSION_KEY = "student-advisory-session-token";
const POLL_INTERVAL_MS = 1200;
const TRACE_POLL_INTERVAL_MS = 1000;
const TRACE_STAGES = ["profile", "retrieve", "conflict", "reason", "policy", "explain"];
let tracePollTimer = null;
const expandedStages = new Set();

function debugUiEnabled() {
  const fromTemplate = document.querySelector(".chat-shell")?.dataset.debugUi === "true";
  const fromUrl = new URLSearchParams(window.location.search).get("debug") === "1";
  return fromTemplate || fromUrl;
}

function showTracePanel() {
  const panel = document.getElementById("trace-panel");
  if (panel) panel.hidden = false;
}

async function fetchTrace(sessionToken) {
  const r = await fetch(`/api/sessions/${sessionToken}/trace`);
  if (!r.ok) throw new Error("trace fetch failed");
  return r.json();
}

function formatDuration(ms) {
  if (ms == null) return "";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function statusMeta(event) {
  switch (event.status) {
    case "completed": return formatDuration(event.duration_ms);
    case "running":   return "running…";
    case "failed":    return "failed";
    default:          return "pending";
  }
}

function statusIcon(status) {
  switch (status) {
    case "completed": return "●";
    case "running":   return "⟳";
    case "failed":    return "✕";
    default:          return "○";
  }
}

function renderTraceCards(events) {
  const root = document.getElementById("trace-cards");
  if (!root) return;
  events.forEach((event) => {
    const card = root.querySelector(`[data-stage="${event.stage}"]`);
    if (!card) return;

    card.classList.remove(
      "trace-card--pending",
      "trace-card--running",
      "trace-card--completed",
      "trace-card--failed",
    );
    card.classList.add(`trace-card--${event.status}`);

    card.querySelector(".trace-card__icon").textContent = statusIcon(event.status);
    card.querySelector(".trace-card__meta").textContent = statusMeta(event);

    const body = card.querySelector(".trace-card__body");
    if (event.status === "completed" && event.output_json) {
      body.textContent = JSON.stringify(event.output_json, null, 2);
    } else if (event.status === "failed") {
      body.textContent = event.error_text || "(no error text)";
    } else {
      body.textContent = "";
    }

    // Restore expanded state
    const isExpanded = expandedStages.has(event.stage);
    body.hidden = !isExpanded;
    card.querySelector(".trace-card__header").setAttribute("aria-expanded", String(isExpanded));
  });
}

let pollTimer = null;
let currentSessionToken = null;

function stopTracePolling() {
  if (tracePollTimer) {
    window.clearTimeout(tracePollTimer);
    tracePollTimer = null;
  }
}

function startTracePolling(sessionToken) {
  if (!debugUiEnabled()) return;
  stopTracePolling();

  const tick = async () => {
    try {
      const payload = await fetchTrace(sessionToken);
      renderTraceCards(payload.events);
      if (payload.run_status === "running" || payload.run_status === "queued") {
        tracePollTimer = window.setTimeout(tick, TRACE_POLL_INTERVAL_MS);
      }
    } catch (e) {
      // trace fetch failures must not interfere with the chat UX
      tracePollTimer = window.setTimeout(tick, TRACE_POLL_INTERVAL_MS * 2);
    }
  };

  tick();
}

function setStatus(message, tone = "info") {
  const node = document.getElementById("chat-status");
  if (!node) return;
  node.textContent = message || "";
  node.dataset.tone = tone;
}

function getProfileState(snapshot) {
  return snapshot?.session?.profile_state_json || {};
}

function getLatestRecommendation(messages) {
  return [...messages].reverse().find((message) => message.kind === "assistant_result") || null;
}

function renderTranscript(messages) {
  const node = document.getElementById("chat-transcript");
  if (!node) return;
  node.innerHTML = "";
  messages.forEach((message) => {
    const item = document.createElement("article");
    item.className = `message message--${message.role}`;
    item.dataset.kind = message.kind;
    item.textContent = message.content;
    node.appendChild(item);
  });
}

function renderProfileSummary(snapshot) {
  const node = document.getElementById("profile-summary");
  if (!node) return;
  const profile = getProfileState(snapshot);
  const entries = [
    ["Năm tuyển sinh", profile.admission_year],
    ["Tổng điểm", profile.total_score],
    ["Ngành quan tâm", (profile.preferred_majors || []).join(", ")],
    ["Khu vực", profile.location_preference],
    ["Còn thiếu", (profile.missing_slots || []).join(", ")],
  ].filter(([, value]) => value);

  if (entries.length === 0) {
    node.textContent = "Chưa có dữ liệu hồ sơ.";
    return;
  }

  node.innerHTML = entries
    .map(([label, value]) => `<p><strong>${label}:</strong> ${value}</p>`)
    .join("");
}

function renderRecommendation(snapshot) {
  const node = document.getElementById("recommendation-panel");
  if (!node) return;
  const latest = getLatestRecommendation(snapshot.messages || []);
  node.textContent = latest ? latest.content : "Chưa có khuyến nghị.";
}

function renderSnapshot(snapshot) {
  renderTranscript(snapshot.messages || []);
  renderProfileSummary(snapshot);
  renderRecommendation(snapshot);
}

async function createSession() {
  const response = await fetch("/api/sessions", { method: "POST" });
  if (!response.ok) {
    throw new Error("Không thể tạo phiên chat mới.");
  }
  const payload = await response.json();
  currentSessionToken = payload.session.session_token;
  window.localStorage.setItem(SESSION_KEY, currentSessionToken);
  return payload;
}

async function fetchSessionSnapshot(sessionToken) {
  const response = await fetch(`/api/sessions/${sessionToken}`);
  if (!response.ok) {
    throw new Error("Không thể tải lại lịch sử hội thoại.");
  }
  return response.json();
}

async function ensureSession() {
  const stored = window.localStorage.getItem(SESSION_KEY);
  if (!stored) {
    return createSession();
  }

  try {
    currentSessionToken = stored;
    return await fetchSessionSnapshot(stored);
  } catch (error) {
    window.localStorage.removeItem(SESSION_KEY);
    currentSessionToken = null;
    return createSession();
  }
}

function stopPolling() {
  if (pollTimer) {
    window.clearTimeout(pollTimer);
    pollTimer = null;
  }
}

function schedulePolling(sessionToken) {
  stopPolling();
  pollTimer = window.setTimeout(async () => {
    const snapshot = await fetchSessionSnapshot(sessionToken);
    renderSnapshot(snapshot);
    if (snapshot.session.status === "completed") {
      setStatus("Đã có kết quả tư vấn.", "success");
      stopPolling();
      // do one last trace fetch so the final stage flips to completed instantly
      if (debugUiEnabled()) {
        fetchTrace(sessionToken).then((p) => renderTraceCards(p.events)).catch(() => {});
        stopTracePolling();
      }
      return;
    }
    if (snapshot.session.status === "failed") {
      setStatus("Quá trình phân tích bị gián đoạn.", "error");
      stopPolling();
      if (debugUiEnabled()) {
        fetchTrace(sessionToken).then((p) => renderTraceCards(p.events)).catch(() => {});
        stopTracePolling();
      }
      return;
    }
    schedulePolling(sessionToken);
  }, POLL_INTERVAL_MS);
}

async function sendMessage(content) {
  const sessionToken = currentSessionToken || window.localStorage.getItem(SESSION_KEY);
  const response = await fetch(`/api/sessions/${sessionToken}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  if (!response.ok) {
    throw new Error("Không gửi được tin nhắn.");
  }
  return response.json();
}

document.addEventListener("DOMContentLoaded", async () => {
  const form = document.getElementById("chat-form");
  const input = document.getElementById("chat-input");
  const resetButton = document.getElementById("reset-session");

  if (debugUiEnabled()) {
    showTracePanel();
  }

  document.querySelectorAll("#trace-cards .trace-card").forEach((card) => {
    const header = card.querySelector(".trace-card__header");
    header.addEventListener("click", () => {
      const stage = card.dataset.stage;
      const body = card.querySelector(".trace-card__body");
      const expanded = expandedStages.has(stage);
      if (expanded) {
        expandedStages.delete(stage);
        body.hidden = true;
        header.setAttribute("aria-expanded", "false");
      } else {
        expandedStages.add(stage);
        body.hidden = false;
        header.setAttribute("aria-expanded", "true");
      }
    });
  });

  try {
    const bootstrap = await ensureSession();
    renderSnapshot(bootstrap);
    setStatus("Sẵn sàng tư vấn.", "info");
    if (debugUiEnabled() && bootstrap.session && bootstrap.session.status === "running") {
      startTracePolling(currentSessionToken);
    }
  } catch (error) {
    setStatus("Không thể khởi tạo phiên chat.", "error");
    form.querySelector("button[type='submit']").disabled = true;
    return;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const content = input.value.trim();
    if (!content) return;

    try {
      setStatus("Đang gửi tin nhắn...", "pending");
      const result = await sendMessage(content);
      input.value = "";

      const snapshot = await fetchSessionSnapshot(currentSessionToken);
      renderSnapshot(snapshot);

      if (result.should_start_run) {
        setStatus("Đang phân tích hồ sơ...", "pending");
        schedulePolling(currentSessionToken);
        startTracePolling(currentSessionToken);
        return;
      }

      setStatus("Đã nhận câu hỏi tiếp theo.", "info");
    } catch (error) {
      setStatus("Không gửi được tin nhắn.", "error");
    }
  });

  resetButton.addEventListener("click", async () => {
    stopPolling();
    stopTracePolling();
    window.localStorage.removeItem(SESSION_KEY);
    const snapshot = await createSession();
    renderSnapshot(snapshot);
    setStatus("Đã bắt đầu phiên chat mới.", "info");
  });
});
