const dot = document.getElementById("dot");
const text = document.getElementById("status-text");

const labels = {
  connected:    "Connected to CtxAnt",
  connecting:   "Connecting…",
  disconnected: "Disconnected — is the CtxAnt app running?",
};

function render(s) {
  dot.className = `dot ${s}`;
  text.textContent = labels[s] || s;
}

chrome.storage.session.get("wsStatus", ({ wsStatus }) => {
  render(wsStatus || "disconnected");
});

chrome.storage.session.onChanged.addListener((changes) => {
  if (changes.wsStatus) render(changes.wsStatus.newValue);
});
