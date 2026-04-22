// Content script — injected into every page.
// background.js uses chrome.scripting.executeScript to call page functions
// directly, so this file mainly serves as a ping to confirm injection worked.
// We also expose a helper for the background to detect if content scripts loaded.

window.__browserControlReady = true;
