const dot = document.getElementById("dot");
const text = document.getElementById("status-text");
const detail = document.getElementById("status-detail");

const labels = {
  connected: "Connected to CtxAnt",
  connecting: "Connecting to the Mac app…",
  disconnected: "Disconnected",
};

const details = {
  connected: "The extension is paired with the local CtxAnt app and ready for user-triggered browser tasks.",
  connecting: "Trying to reach the localhost pairing and WebSocket endpoints now.",
  disconnected: "Start the CtxAnt Mac app and keep Chrome open. Reload the extension if you recently changed the local pairing secret.",
};

function render(s, explicitDetail) {
  dot.className = `dot ${s}`;
  text.textContent = labels[s] || s;
  detail.textContent = explicitDetail || details[s] || details.disconnected;
}

chrome.storage.session.get(["wsStatus", "wsStatusDetail"], ({ wsStatus, wsStatusDetail }) => {
  render(wsStatus || "disconnected", wsStatusDetail || "");
});

chrome.storage.session.onChanged.addListener((changes) => {
  if (changes.wsStatus || changes.wsStatusDetail) {
    chrome.storage.session.get(["wsStatus", "wsStatusDetail"], ({ wsStatus, wsStatusDetail }) => {
      render(wsStatus || "disconnected", wsStatusDetail || "");
    });
  }
});
