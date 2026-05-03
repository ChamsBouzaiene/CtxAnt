# Chrome Web Store submission kit

Everything needed to submit `CtxAnt` to the Chrome Web Store. Copy the
listing copy below into the Developer Dashboard fields as-is.

---

## 1. Before you upload

- [ ] Bump `extension/manifest.json` version if re-submitting (Chrome requires a strictly-higher version on every upload).
- [ ] Regenerate icons if the brand changes: `.venv/bin/python extension/icons/build_icons.py`.
- [ ] Host `privacy.html` somewhere public (GitHub Pages, Vercel — `https://ctxant.com/privacy.html`) and put that URL into the Developer Dashboard's **Privacy policy** field. The file in `extension/privacy.html` is the source of truth; mirror it.
- [ ] Zip the extension for upload: `cd extension && zip -r ../ctxant-extension-v$(jq -r .version manifest.json).zip . -x '*.DS_Store' -x 'store-assets/*' -x 'icons/build_icons.py'`

## 2. Listing fields

**Name** (max 75 chars)
```
CtxAnt — Text your browser anything
```

**Developer / publisher**
```
Bouzaiene Chamseddine
```

**Summary** (max 132 chars — this is what shows under the name in search)
```
A local Chrome companion for the CtxAnt Mac app. User-triggered browser automation in the Chrome profile you already use.
```

**Category:** Productivity

**Language:** English

**Description** (max 16k chars — keep it scannable, lead with the differentiator):

```
CtxAnt is an AI sidekick that lives in your Chrome and takes orders from Telegram. You text the bot "apply to 5 senior React jobs in Berlin" or "summarize my unread email" — and the AI drives YOUR browser, logged into YOUR accounts, looking at YOUR tabs.

Other AI agents open a fresh sandboxed browser that doesn't know you. CtxAnt uses the browser you're already signed into. That's the whole pitch.

WHAT IT DOES
• Reads, clicks, types, scrolls, navigates — on any site.
• Handles forms, logins (you're already signed in), and multi-tab flows.
• Takes screenshots and extracts page content needed to complete the task.
• Schedules recurring tasks ("every morning at 9am, summarize my inbox").
• Deploys a dedicated Telegram bot per task: Job Hunter, Deal Finder, Inbox Triage, and more.

HOW IT WORKS
1. Install the CtxAnt Mac app (https://ctxant.com).
2. Install this extension — it auto-pairs with the app over localhost.
3. Text your own Telegram bot anything.

PRIVACY
• 100% local between Chrome and the CtxAnt app. The extension talks to the Mac app over ws://127.0.0.1:8765. Nothing goes to a CtxAnt server because there is no CtxAnt server.
• BYOK. You bring your own xAI (Grok) or Anthropic (Claude) API key. Prompts go directly from your machine to the provider.
• Your browsing is not observed unless you issue a command.

WHAT IT ISN'T
• Not a cloud agent. Not a Chrome sidebar chatbot. Not a passive page monitor.
• No account, no subscription, no telemetry, and no remote code loading.

Requires the companion Mac app. Windows and Linux coming soon.
```

**Screenshots** (at least 1, up to 5 — 1280×800 or 640×400 PNG/JPEG)

Drop files into this folder named `screenshot-1.png` … `screenshot-5.png`. Suggested shots:

1. Split: Telegram chat "/run" → Chrome filling a LinkedIn Easy Apply form.
2. The hub bot's `/start` screen with the agent deploy buttons.
3. The dashboard at `http://127.0.0.1:8766/dashboard`.
4. A Job Hunter agent DM'ing a morning digest.
5. The popup showing the connected state and localhost explanation.

**Promotional tile** (440×280 PNG — optional but recommended for discovery)

Save as `promo-tile-440x280.png`. Use `icons/icon-512.png` enlarged on the brand gradient with the tagline "Text your browser anything."

**Marquee tile** (1400×560 PNG — only needed if Google features the listing)

Save as `marquee-1400x560.png`.

## 3. Privacy policy & permissions justifications

The Web Store review asks you to justify every permission and `<all_urls>` host access. Paste these verbatim into the "Privacy practices" tab:

**Justification for `activeTab`, `tabs`, `scripting`:**
```
Required to act on the current tab on behalf of the user. The extension executes browser automation (click, type, scroll, extract content, take screenshots) only in response to commands the user sends through the companion Mac app. Without these permissions, the product cannot function.
```

**Justification for `storage`:**
```
Stores the extension's local connection status so the popup can show whether the companion Mac app is connected. No browsing data is stored remotely.
```

**Justification for `alarms`:**
```
Chrome MV3 service workers idle out after ~30s. We use a periodic alarm to keep the local WebSocket to the companion app alive so commands arrive without delay.
```

**Justification for `host_permissions: <all_urls>`:**
```
Users ask the AI to work on arbitrary sites they visit (Gmail, LinkedIn, their bank, any web form). The extension cannot know in advance which origins those commands will target, so broad host access is required. The extension does not inject a persistent content script or observe browsing activity outside of an active user command.
```

**Justification for `host_permissions: http://127.0.0.1/*, http://localhost/*`:**
```
Used to pair with the companion Mac app running on the user's own machine (localhost HTTP endpoint at port 8766). Required once at install time to fetch the pairing secret.
```

**Single purpose description:**
```
Let users drive their own Chrome browser through the CtxAnt Mac app using natural-language commands sent through Telegram.
```

**Are you handling user data?** Yes — conversation content and page content only as needed to carry out the user's command through the companion Mac app and the user's configured AI provider. No CtxAnt-owned servers.

**Data uses checklist (check these):**
- [x] Personally identifiable information — only what the user types into chat.
- [ ] Health, financial, location — only if the user directs an agent to those sites; we do not store it.
- [x] Authentication information — the local pairing secret handled between the extension and the companion app on localhost.
- [x] Website content — in response to user commands.

**Do not check:**
- We do NOT sell, transfer, or use this data for any purpose unrelated to the single stated purpose.

**Privacy policy URL:** `https://ctxant.com/privacy.html`

**Support URL:** `https://github.com/ChamsBouzaiene/CtxAnt/issues`

## 4. Upload sequence

1. https://chrome.google.com/webstore/devconsole → New item
2. Upload the `.zip` from step 1.
3. Fill listing fields (copy above).
4. Fill Privacy practices tab (justifications above).
5. Pay the one-time $5 developer fee if you haven't.
6. Submit. Typical review: 1–3 business days.

## 5. After approval

- [ ] Update ctxant.com install CTA from "direct `.crx` download" to Web Store URL.
- [ ] Update onboarding step 4 in `backend/onboarding.py` with the Web Store URL.
- [ ] Tweet the listing.
