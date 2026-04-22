// Background service worker: WebSocket client + command router

const WS_URL   = "ws://localhost:8765";
const PAIR_URL = "http://127.0.0.1:8766/pair";

let ws = null;
let wsSecret = null;
let reconnectDelay = 1000;
let status = "disconnected";

// ── Pairing: fetch WS_SECRET from the local backend on first connect ─────────

async function fetchSecret() {
  try {
    const res = await fetch(PAIR_URL, { method: "GET" });
    if (!res.ok) return null;
    const data = await res.json();
    return data.secret || null;
  } catch {
    return null;
  }
}

// ── Status management ────────────────────────────────────────────────────────

function setStatus(s) {
  status = s;
  chrome.storage.session.set({ wsStatus: s });
}

// ── WebSocket connection ─────────────────────────────────────────────────────

async function connect() {
  if (ws && (ws.readyState === WebSocket.CONNECTING || ws.readyState === WebSocket.OPEN)) {
    return;
  }

  setStatus("connecting");

  if (!wsSecret) {
    wsSecret = await fetchSecret();
    if (!wsSecret) {
      console.log("[CtxAnt] Could not fetch pairing secret — backend not running?");
      setStatus("disconnected");
      setTimeout(connect, reconnectDelay);
      reconnectDelay = Math.min(reconnectDelay * 2, 30000);
      return;
    }
  }

  ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    ws.send(JSON.stringify({ type: "auth", token: wsSecret }));
    setStatus("connected");
    reconnectDelay = 1000;
    console.log("[CtxAnt] Connected to backend");
  };

  ws.onmessage = async (event) => {
    let cmd;
    try {
      cmd = JSON.parse(event.data);
    } catch {
      return;
    }
    await handleCommand(cmd);
  };

  ws.onclose = (ev) => {
    setStatus("disconnected");
    // 1008 = auth failure → invalidate cached secret so we re-pair
    if (ev && ev.code === 1008) {
      wsSecret = null;
    }
    console.log(`[CtxAnt] Disconnected. Reconnecting in ${reconnectDelay}ms...`);
    setTimeout(connect, reconnectDelay);
    reconnectDelay = Math.min(reconnectDelay * 2, 30000);
  };

  ws.onerror = (err) => {
    console.error("[CtxAnt] WebSocket error:", err);
  };
}

function send(payload) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(payload));
  }
}

function sendResult(id, data) {
  send({ id, success: true, data });
}

function sendError(id, error) {
  send({ id, success: false, error: String(error) });
}

// ── Command routing ──────────────────────────────────────────────────────────

async function getActiveTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab;
}

async function handleCommand(cmd) {
  const { id, type } = cmd;

  try {
    switch (type) {
      case "screenshot": {
        const tab = await getActiveTab();
        const dataUrl = await chrome.tabs.captureVisibleTab(tab.windowId, { format: "png" });
        // Strip the "data:image/png;base64," prefix
        const base64 = dataUrl.split(",")[1];
        sendResult(id, base64); // backend receives the raw base64
        // Also send as the old format for compatibility
        send({ type: "screenshot", id, data: base64, success: true });
        break;
      }

      case "navigate": {
        const tab = await getActiveTab();
        await chrome.tabs.update(tab.id, { url: cmd.url });
        // Wait for tab to finish loading
        await waitForTabLoad(tab.id);
        sendResult(id, { url: cmd.url });
        break;
      }

      case "click": {
        const tab = await getActiveTab();
        const result = await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          func: contentClick,
          args: [cmd.selector, cmd.x, cmd.y],
        });
        sendResult(id, result[0].result);
        break;
      }

      case "type": {
        const tab = await getActiveTab();
        const result = await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          func: contentType,
          args: [cmd.selector, cmd.text],
        });
        sendResult(id, result[0].result);
        break;
      }

      case "scroll": {
        const tab = await getActiveTab();
        const result = await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          func: contentScroll,
          args: [cmd.direction, cmd.pixels || 500],
        });
        sendResult(id, result[0].result);
        break;
      }

      case "get_content": {
        const tab = await getActiveTab();
        const result = await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          func: contentGetContent,
          args: [],
        });
        sendResult(id, result[0].result);
        break;
      }

      case "evaluate": {
        const tab = await getActiveTab();
        const result = await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          func: contentEvaluate,
          args: [cmd.code],
        });
        sendResult(id, { result: result[0].result });
        break;
      }

      case "list_tabs": {
        const tabs = await chrome.tabs.query({});
        sendResult(id, tabs.map(t => ({ id: t.id, title: t.title, url: t.url, active: t.active })));
        break;
      }

      case "switch_tab": {
        await chrome.tabs.update(cmd.tabId, { active: true });
        const tab = await chrome.tabs.get(cmd.tabId);
        await chrome.windows.update(tab.windowId, { focused: true });
        sendResult(id, { tabId: cmd.tabId });
        break;
      }

      case "new_tab": {
        const tab = await chrome.tabs.create({ url: cmd.url || "about:blank", active: true });
        if (cmd.url) await waitForTabLoad(tab.id);
        sendResult(id, { tabId: tab.id });
        break;
      }

      case "close_tab": {
        const tab = await getActiveTab();
        await chrome.tabs.remove(tab.id);
        sendResult(id, { closed: true });
        break;
      }

      default:
        sendError(id, `Unknown command type: ${type}`);
    }
  } catch (err) {
    sendError(id, err.message || String(err));
  }
}

// ── Tab load helper ──────────────────────────────────────────────────────────

function waitForTabLoad(tabId, timeout = 15000) {
  return new Promise((resolve, reject) => {
    const deadline = setTimeout(() => {
      chrome.tabs.onUpdated.removeListener(listener);
      resolve(); // don't fail on timeout, just continue
    }, timeout);

    function listener(updatedId, info) {
      if (updatedId === tabId && info.status === "complete") {
        clearTimeout(deadline);
        chrome.tabs.onUpdated.removeListener(listener);
        resolve();
      }
    }
    chrome.tabs.onUpdated.addListener(listener);
  });
}

// ── Content functions (serialised and injected via executeScript) ─────────────
// These run inside the page context, NOT in the service worker.

function contentClick(selector, x, y) {
  try {
    let el = null;
    if (selector) {
      el = document.querySelector(selector);
      if (!el) return { error: `Element not found: ${selector}` };
    }
    if (el) {
      el.scrollIntoView({ block: "center" });
      el.click();
      return { clicked: selector };
    }
    // coordinate click
    const target = document.elementFromPoint(x, y);
    if (target) {
      target.click();
      return { clicked: `element at (${x},${y})` };
    }
    return { error: `No element at (${x},${y})` };
  } catch (e) {
    return { error: e.message };
  }
}

function contentType(selector, text) {
  try {
    const el = document.querySelector(selector);
    if (!el) return { error: `Element not found: ${selector}` };
    el.focus();
    el.value = "";
    // Dispatch input events so frameworks like React/Vue pick it up
    const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
      window.HTMLInputElement.prototype, "value"
    )?.set || Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value")?.set;
    if (nativeInputValueSetter) {
      nativeInputValueSetter.call(el, text);
    } else {
      el.value = text;
    }
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
    return { typed: text, into: selector };
  } catch (e) {
    return { error: e.message };
  }
}

function contentScroll(direction, pixels) {
  const map = { up: [0, -pixels], down: [0, pixels], left: [-pixels, 0], right: [pixels, 0] };
  const [x, y] = map[direction] || [0, pixels];
  window.scrollBy(x, y);
  return { scrolled: direction, pixels };
}

function contentGetContent() {
  return {
    title: document.title,
    url: location.href,
    text: document.body ? document.body.innerText.slice(0, 20000) : "",
  };
}

function contentEvaluate(code) {
  // eslint-disable-next-line no-new-func
  return new Function(code)();
}

// ── Keepalive: prevent MV3 service worker from being killed ──────────────────
// Chrome terminates idle service workers after ~30s, dropping the WebSocket.
// An alarm fires every 20s to wake the worker and reconnect if needed.

chrome.alarms.create("keepalive", { periodInMinutes: 0.33 }); // ~20 seconds

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "keepalive") {
    if (!ws || ws.readyState === WebSocket.CLOSED || ws.readyState === WebSocket.CLOSING) {
      connect();
    }
  }
});

// ── Start ────────────────────────────────────────────────────────────────────

connect();

chrome.runtime.onStartup.addListener(connect);
chrome.runtime.onInstalled.addListener(() => {
  chrome.alarms.create("keepalive", { periodInMinutes: 0.33 });
  connect();
});
