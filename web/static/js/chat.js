const SESSION_KEY = "student-advisory-session-token";

async function ensureSession() {
  const current = window.localStorage.getItem(SESSION_KEY);
  if (current) {
    return current;
  }
  const response = await fetch("/api/sessions", { method: "POST" });
  const payload = await response.json();
  window.localStorage.setItem(SESSION_KEY, payload.session.session_token);
  return payload.session.session_token;
}

async function sendMessage(content) {
  const sessionToken = await ensureSession();
  return fetch(`/api/sessions/${sessionToken}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
}

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("chat-form");
  const input = document.getElementById("chat-input");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const content = input.value.trim();
    if (!content) return;
    await sendMessage(content);
    input.value = "";
  });
});