const SESSION_KEY = "student-advisory-session-token";
const POLL_INTERVAL_MS = 1200;

let pollTimer = null;
let currentSessionToken = null;

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
    ["Nam tuyen sinh", profile.admission_year],
    ["Tong diem", profile.total_score],
    ["Nganh quan tam", (profile.preferred_majors || []).join(", ")],
    ["Khu vuc", profile.location_preference],
    ["Con thieu", (profile.missing_slots || []).join(", ")],
  ].filter(([, value]) => value);

  if (entries.length === 0) {
    node.textContent = "Chua co du lieu ho so.";
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
  node.textContent = latest ? latest.content : "Chua co khuyen nghi.";
}

function renderSnapshot(snapshot) {
  renderTranscript(snapshot.messages || []);
  renderProfileSummary(snapshot);
  renderRecommendation(snapshot);
}

async function createSession() {
  const response = await fetch("/api/sessions", { method: "POST" });
  if (!response.ok) {
    throw new Error("Khong the tao phien chat moi.");
  }
  const payload = await response.json();
  currentSessionToken = payload.session.session_token;
  window.localStorage.setItem(SESSION_KEY, currentSessionToken);
  return payload;
}

async function fetchSessionSnapshot(sessionToken) {
  const response = await fetch(`/api/sessions/${sessionToken}`);
  if (!response.ok) {
    throw new Error("Khong the tai lai lich su hoi thoai.");
  }
  return response.json();
}

async function ensureSession() {
  const stored = window.localStorage.getItem(SESSION_KEY);
  if (!stored) {
    return createSession();
  }
  currentSessionToken = stored;
  return fetchSessionSnapshot(stored);
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
      setStatus("Da co ket qua tu van.", "success");
      stopPolling();
      return;
    }
    if (snapshot.session.status === "failed") {
      setStatus("Qua trinh phan tich bi gian doan.", "error");
      stopPolling();
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
    throw new Error("Khong gui duoc tin nhan.");
  }
  return response.json();
}

document.addEventListener("DOMContentLoaded", async () => {
  const form = document.getElementById("chat-form");
  const input = document.getElementById("chat-input");
  const resetButton = document.getElementById("reset-session");

  const bootstrap = await ensureSession();
  renderSnapshot(bootstrap);
  setStatus("San sang tu van.", "info");

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const content = input.value.trim();
    if (!content) return;

    setStatus("Dang gui tin nhan...", "pending");
    const result = await sendMessage(content);
    input.value = "";

    const snapshot = await fetchSessionSnapshot(currentSessionToken);
    renderSnapshot(snapshot);

    if (result.should_start_run) {
      setStatus("Dang phan tich ho so...", "pending");
      schedulePolling(currentSessionToken);
      return;
    }

    setStatus("Da nhan cau hoi tiep theo.", "info");
  });

  resetButton.addEventListener("click", async () => {
    stopPolling();
    window.localStorage.removeItem(SESSION_KEY);
    const snapshot = await createSession();
    renderSnapshot(snapshot);
    setStatus("Da bat dau phien chat moi.", "info");
  });
});