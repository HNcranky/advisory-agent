import { initTheme } from "./modules/theme.js";
import { initCollapseHandles } from "./modules/layout.js";
import { renderTranscript, appendMessage, renderRecommendationCard } from "./modules/messages.js";
import {
  renderTrace,
  startTracePolling,
  stopTracePolling,
  debugUiEnabled,
} from "./modules/trace.js";
import { toast } from "./modules/toasts.js";

const COMPOSER_MAX_PX = 240;

function autoGrow(textarea) {
  if (!textarea) return;
  textarea.style.height = "auto";
  textarea.style.height = Math.min(textarea.scrollHeight, COMPOSER_MAX_PX) + "px";
}

function syncSendDisabled(input, button, statusEl) {
  if (!input || !button) return;
  const empty = input.value.trim().length === 0;
  const pending = statusEl?.dataset.tone === "pending";
  button.disabled = empty || pending;
}

const SESSION_KEY = "student-advisory-session-token";
const POLL_INTERVAL_MS = 1200;

let pollTimer = null;
let currentSessionToken = null;

const traceOpts = () => ({
  debug: debugUiEnabled(),
  stageLabels: window.__stageLabels || [],
});

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

function profileIsEmpty(profile) {
  if (!profile) return true;
  return Object.values(profile).every(
    (v) => v == null || v === "" || (Array.isArray(v) && v.length === 0),
  );
}

function renderProfileSummary(snapshot) {
  const node = document.getElementById("profile-summary");
  if (!node) return;
  const profile = getProfileState(snapshot);

  if (profileIsEmpty(profile)) {
    node.innerHTML =
      '<p class="card-empty">Hồ sơ sẽ tự cập nhật khi em trò chuyện.</p>';
    return;
  }

  const entries = [
    ["Năm tuyển sinh", profile.admission_year],
    ["Tổng điểm", profile.total_score],
    ["Ngành quan tâm", (profile.preferred_majors || []).join(", ")],
    ["Khu vực", profile.location_preference],
    ["Còn thiếu", (profile.missing_slots || []).join(", ")],
  ].filter(([, value]) => value);

  if (entries.length === 0) {
    node.innerHTML =
      '<p class="card-empty">Hồ sơ sẽ tự cập nhật khi em trò chuyện.</p>';
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
  const status = snapshot.session?.status;

  if (!latest && (status === "running" || status === "queued")) {
    node.innerHTML = `
      <div class="skeleton" aria-hidden="true">
        <div class="skeleton-line skeleton-line--100"></div>
        <div class="skeleton-line skeleton-line--85"></div>
        <div class="skeleton-line skeleton-line--60"></div>
      </div>
      <span class="visually-hidden">Đang soạn khuyến nghị...</span>`;
    return;
  }

  if (!latest) {
    node.innerHTML = '<p class="card-empty">Chưa có khuyến nghị.</p>';
    return;
  }

  renderRecommendationCard(node, latest.content);
}

function renderSnapshot(snapshot) {
  const transcript = document.getElementById("chat-transcript");
  renderTranscript(transcript, snapshot.messages || []);
  renderProfileSummary(snapshot);
  renderRecommendation(snapshot);
}

async function createSession() {
  let response;
  try {
    response = await fetch("/api/sessions", { method: "POST" });
  } catch (e) {
    toast("Không khởi tạo được phiên. Tải lại trang.", { variant: "error" });
    throw e;
  }
  if (!response.ok) {
    toast("Không khởi tạo được phiên. Tải lại trang.", { variant: "error" });
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
    toast("Phiên cũ đã hết hạn, đã tạo phiên mới.", { variant: "info" });
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
    try {
      const snapshot = await fetchSessionSnapshot(sessionToken);
      renderSnapshot(snapshot);
      if (snapshot.session.status === "completed") {
        setStatus("Đã có kết quả tư vấn.", "success");
        stopPolling();
        stopTracePolling();
        return;
      }
      if (snapshot.session.status === "failed") {
        setStatus("Quá trình phân tích bị gián đoạn.", "error");
        stopPolling();
        stopTracePolling();
        return;
      }
      schedulePolling(sessionToken);
    } catch (e) {
      toast("Mất kết nối, đang thử lại...", { variant: "warning" });
      pollTimer = window.setTimeout(() => schedulePolling(sessionToken), POLL_INTERVAL_MS);
    }
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
  const sendButton = document.getElementById("send-button");
  const statusEl = document.getElementById("chat-status");

  input.addEventListener("input", () => {
    autoGrow(input);
    syncSendDisabled(input, sendButton, statusEl);
  });

  input.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      event.preventDefault();
      if (!sendButton.disabled) form.requestSubmit();
    }
  });

  // Keep send-disabled in sync whenever status tone changes.
  const statusObserver = new MutationObserver(() =>
    syncSendDisabled(input, sendButton, statusEl)
  );
  if (statusEl) {
    statusObserver.observe(statusEl, { attributes: true, attributeFilter: ["data-tone"] });
  }

  // Initial state.
  autoGrow(input);
  syncSendDisabled(input, sendButton, statusEl);

  initCollapseHandles();
  initTheme();

  document.getElementById("chat-transcript")?.addEventListener("click", (event) => {
    const chip = event.target.closest(".chip[data-prompt]");
    if (!chip) return;
    const textarea = document.getElementById("chat-input");
    if (!textarea) return;
    textarea.value = chip.dataset.prompt;
    textarea.dispatchEvent(new Event("input", { bubbles: true }));
    textarea.focus();
  });

  const helpButton = document.getElementById("help-button");
  const helpPopover = document.getElementById("help-popover");
  if (helpButton && helpPopover && typeof helpPopover.showModal === "function") {
    helpButton.addEventListener("click", () => {
      if (helpPopover.open) helpPopover.close();
      else helpPopover.showModal();
    });
    helpPopover.addEventListener("click", (e) => {
      if (e.target === helpPopover) helpPopover.close();
    });
  }

  if (debugUiEnabled()) {
    const panel = document.getElementById("trace-panel");
    if (panel) panel.hidden = false;
  }

  try {
    const bootstrap = await ensureSession();
    renderSnapshot(bootstrap);
    setStatus("Sẵn sàng tư vấn.", "info");
    if (debugUiEnabled() && bootstrap.session && bootstrap.session.status === "running") {
      startTracePolling(currentSessionToken, traceOpts());
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
      setStatus("Đang gửi tin nhắn", "pending");
      const result = await sendMessage(content);
      input.value = "";
      autoGrow(input);
      syncSendDisabled(input, sendButton, statusEl);

      const snapshot = await fetchSessionSnapshot(currentSessionToken);
      renderSnapshot(snapshot);

      if (result.should_start_run) {
        setStatus("Đang phân tích hồ sơ", "pending");
        schedulePolling(currentSessionToken);
        startTracePolling(currentSessionToken, traceOpts());
        return;
      }

      setStatus("Đã nhận câu hỏi tiếp theo.", "info");
    } catch (error) {
      setStatus("Không gửi được tin nhắn.", "error");
    }
  });

  resetButton?.addEventListener("click", async () => {
    stopPolling();
    stopTracePolling();
    window.localStorage.removeItem(SESSION_KEY);
    if (helpPopover?.open) helpPopover.close();
    const snapshot = await createSession();
    renderSnapshot(snapshot);
    setStatus("Đã bắt đầu phiên chat mới.", "info");
  });
});
