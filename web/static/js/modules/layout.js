// web/static/js/modules/layout.js
// Layout helpers: collapse-able side panels (persisted) + mobile drawers.

const LAYOUT_STORAGE_KEY = "layout";
const MOBILE_QUERY = "(max-width: 899px)";

function readLayoutState() {
  try {
    const raw = window.localStorage.getItem(LAYOUT_STORAGE_KEY);
    if (!raw) return { left: false, right: false };
    const parsed = JSON.parse(raw);
    return {
      left: Boolean(parsed.left),
      right: Boolean(parsed.right),
    };
  } catch {
    return { left: false, right: false };
  }
}

function writeLayoutState(state) {
  try {
    window.localStorage.setItem(LAYOUT_STORAGE_KEY, JSON.stringify(state));
  } catch {
    /* storage unavailable; skip persistence */
  }
}

function applyCollapsed(shell, state) {
  shell.classList.toggle("left-collapsed", state.left);
  shell.classList.toggle("right-collapsed", state.right);
  const leftPanel = document.getElementById("profile-panel");
  const rightPanel = document.getElementById("trace-panel");
  if (leftPanel) leftPanel.setAttribute("aria-hidden", String(state.left));
  if (rightPanel) rightPanel.setAttribute("aria-hidden", String(state.right));
}

function wireCollapseButton(shell, state, side) {
  const buttonId = side === "left" ? "collapse-left" : "collapse-right";
  const button = document.getElementById(buttonId);
  if (!button) return;
  button.addEventListener("click", () => {
    state[side] = !state[side];
    applyCollapsed(shell, state);
    writeLayoutState(state);
  });
}

function closeDrawerInternal() {
  document.body.classList.remove("drawer-open--left", "drawer-open--right");
  const backdrop = document.getElementById("drawer-backdrop");
  if (backdrop) backdrop.hidden = true;
}

function openDrawerInternal(side) {
  const cls = side === "left" ? "drawer-open--left" : "drawer-open--right";
  document.body.classList.remove("drawer-open--left", "drawer-open--right");
  document.body.classList.add(cls);
  const backdrop = document.getElementById("drawer-backdrop");
  if (backdrop) backdrop.hidden = false;
}

function wireDrawerButton(side) {
  const buttonId = side === "left" ? "open-left-drawer" : "open-right-drawer";
  const button = document.getElementById(buttonId);
  if (!button) return;
  button.addEventListener("click", () => openDrawerInternal(side));
}

function wireDrawerDismiss() {
  const backdrop = document.getElementById("drawer-backdrop");
  if (backdrop) {
    backdrop.addEventListener("click", closeDrawerInternal);
  }
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeDrawerInternal();
  });
}

function syncDrawerForViewport(mql) {
  // When transitioning out of mobile, ensure no stale drawer state lingers.
  if (!mql.matches) closeDrawerInternal();
}

export function openDrawer(side) {
  openDrawerInternal(side === "right" ? "right" : "left");
}

export function closeDrawer() {
  closeDrawerInternal();
}

export function initCollapseHandles() {
  const shell = document.querySelector(".app-shell");
  if (!shell) return;

  const state = readLayoutState();
  applyCollapsed(shell, state);

  wireCollapseButton(shell, state, "left");
  wireCollapseButton(shell, state, "right");
  wireDrawerButton("left");
  wireDrawerButton("right");
  wireDrawerDismiss();

  const mql = window.matchMedia(MOBILE_QUERY);
  syncDrawerForViewport(mql);
  if (typeof mql.addEventListener === "function") {
    mql.addEventListener("change", syncDrawerForViewport);
  } else if (typeof mql.addListener === "function") {
    // Safari < 14 fallback
    mql.addListener(syncDrawerForViewport);
  }
}
