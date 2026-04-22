# Demo GIF Storyboard

Ten GIFs for the landing page carousel and the Twitter launch thread. Each is:

- **8–15 seconds**, silent, autoplay-loop
- **Split-screen**: Telegram chat on the left (phone-frame or plain window — pick one and be consistent), Chrome on the right
- **No cursor jitter** — record with a steady hand or use `ffmpeg` to cut out cursor hunting
- **Typed text is realistic** — don't paste; actually type, backspaces and all. People smell a fake demo immediately
- **Filename format**: `NN-slug.gif` (lowercase, hyphen-separated), matching what `/web/index.html` references

**Encoding cheatsheet:**

```bash
# screen record at 30fps, then:
ffmpeg -i raw.mov -vf "fps=18,scale=1280:-1:flags=lanczos,palettegen" -y palette.png
ffmpeg -i raw.mov -i palette.png -filter_complex "fps=18,scale=1280:-1:flags=lanczos[x];[x][1:v]paletteuse" -y output.gif
```

Target: <4MB per GIF, <1280px wide. If a GIF is over 4MB, drop fps to 12 before you drop resolution — motion smoothness matters less than legible text.

---

## 01 — Morning digest

**File:** `01-morning-digest.gif`
**Length:** 10s
**Hook:** 400 unread shrinks to 3 bullets.

| Time | Left (Telegram) | Right (Chrome) |
|---|---|---|
| 0:00 | Chat list open, `@ChamsMorningBot` highlighted | Gmail tab open — "Inbox (412 unread)" visible at top |
| 0:01 | Type: `/morning` and send | — |
| 0:02 | "⏳ reading your inbox…" bubble | Gmail scrolls through unread; a few open and close |
| 0:06 | Bot bubble appears: **Your morning:** 3 bulleted items (reply to boss about budget, calendar conflict 2pm, flight delay from United) | Gmail closes back to inbox |
| 0:09 | Hold on the 3 bullets | Chrome blurred in background |

**Voiceover-safe caption:** "400 unread → 3 bullets before coffee."

---

## 02 — Job blast

**File:** `02-job-blast.gif`
**Length:** 15s (the longest — this is the hero demo, worth the frames)
**Hook:** photo of resume + natural-language command → five Easy Apply forms firing.

| Time | Left | Right |
|---|---|---|
| 0:00 | Chat with `@ChamsJobHunterBot` | LinkedIn logged in, job search page |
| 0:01 | User taps paperclip, attaches a PDF of resume | — |
| 0:02 | Caption typed: "apply to 5 Senior React roles in Berlin posted today" | — |
| 0:03 | Send | Chrome navigates: LinkedIn → /jobs search |
| 0:05 | "⏳ searching LinkedIn…" | Search filters apply: Berlin, Senior, React, past 24h |
| 0:07 | "Found 27 matches, opening top 5." | Five tabs spawn in parallel (visible tab strip) |
| 0:09 | — | Tab 1: Easy Apply modal pops, form fills, "Submit" click |
| 0:11 | — | Tabs 2–5 blink through same motion (time-lapsed 2x) |
| 0:13 | "✅ 5 applications submitted. Company names + IDs attached." | Tab strip shows 5 green-check favicons |

**Voiceover-safe caption:** "Photo of your CV. Five jobs. One message."

---

## 03 — Price drop

**File:** `03-price-drop.gif`
**Length:** 12s
**Hook:** set a watch, then time-lapse until the ping.

| Time | Left | Right |
|---|---|---|
| 0:00 | Chat with `@ChamsDealBot` | Amazon product page: "$649.99" on an OLED TV |
| 0:01 | Type: `/watch` and paste the URL, then `below 500` | — |
| 0:03 | "👀 watching that URL hourly until it hits $500" | — |
| 0:04 | Time-lapse indicator (spinner + "24 hours later…") | Product page rapidly refreshes: $649 → $639 → $579 → $499 |
| 0:09 | Notification sound (visual only — show a "🔔" badge) + bubble: "💥 $499 now. Link." | Amazon page shows $499 |
| 0:11 | Hold on bubble | — |

**Voiceover-safe caption:** "Stop babysitting prices. Get pinged."

---

## 04 — Address update

**File:** `04-address-update.gif`
**Length:** 13s
**Hook:** one message → three sites update in parallel tabs.

| Time | Left | Right |
|---|---|---|
| 0:00 | Chat with `@ChamsAssistantBot` | Three-pane tab layout: Amazon account, Chase profile, DMV profile (pre-arranged) |
| 0:01 | Type: "update my address to 221B Baker St, NYC 10001 on Amazon, Chase, and the DMV" | — |
| 0:03 | "✏️ updating 3 sites" | Three tabs become active in quick cuts |
| 0:05 | — | Amazon: address form fills, "Save" click, green checkmark |
| 0:07 | — | Chase: profile edit, address fills, "Save" |
| 0:09 | — | DMV: form fills, "Submit" |
| 0:11 | "✅ done. Amazon, Chase, DMV all updated." | All three green checks visible |

**Voiceover-safe caption:** "Moved? Update your life in one message."

---

## 05 — Subscription audit

**File:** `05-subscription-audit.gif`
**Length:** 14s
**Hook:** find recurring charges in email, cancel inline.

| Time | Left | Right |
|---|---|---|
| 0:00 | Chat with `@ChamsAssistantBot` | Gmail |
| 0:01 | Type: `/audit-subs` | — |
| 0:02 | "🔎 scanning your inbox for recurring charges…" | Gmail search: `invoice OR subscription OR receipt` scrolls through hits |
| 0:06 | Bot replies with a list: "Found 10: Netflix $15, Spotify $10, Notion $8, Disney+ $13, HBO $16, FitnessApp $30, NewsletterX $5, CloudSync $5, Headspace $13, Adobe CC $55. Total: $170/mo. Tap to cancel." | — |
| 0:08 | User taps "Cancel FitnessApp" button | New tab: FitnessApp billing page |
| 0:10 | — | Auto-clicks through "Cancel subscription" → confirmation |
| 0:12 | "✅ canceled FitnessApp. Saving $30/mo." | Confirmation email in Gmail |

**Voiceover-safe caption:** "Subscription creep, audited."

---

## 06 — Form + photo

**File:** `06-form-photo.gif`
**Length:** 12s
**Hook:** photo of an ID + form URL → filled form.

| Time | Left | Right |
|---|---|---|
| 0:00 | Chat with `@ChamsAssistantBot` | Summer camp registration form, blank |
| 0:01 | User attaches photo of child's birth certificate | — |
| 0:02 | Caption typed: "fill out this camp form: [URL]" | — |
| 0:04 | "📄 reading the form and your photo…" | Chrome opens the form URL |
| 0:06 | "Filling: name, DOB, parent info, medical." | Fields populate progressively (name → DOB → address → emergency contact) |
| 0:10 | "Ready for your review. ⬇️" + screenshot of filled form | Filled form visible |

**Voiceover-safe caption:** "Photo of an ID. The form fills itself."

---

## 07 — Flight deal

**File:** `07-flight-deal.gif`
**Length:** 10s
**Hook:** set an alert, time-lapse, get the ping.

| Time | Left | Right |
|---|---|---|
| 0:00 | Chat with `@ChamsTravelBot` | Google Flights, blank |
| 0:01 | Type: `/flight NYC PAR may 12-18 alert below 500` | — |
| 0:03 | "🛫 watching that route daily" | — |
| 0:04 | Time-lapse ("3 days later…") with a simple price line-chart visual | Google Flights: $680 → $590 → $475 |
| 0:08 | "💥 $475 on Delta. Booking link." | Flights page shows $475 result highlighted |
| 0:09 | Hold | — |

**Voiceover-safe caption:** "Flight prices, watched so you don't have to."

---

## 08 — Comparison

**File:** `08-comparison.gif`
**Length:** 9s
**Hook:** one product, three stores, grid.

| Time | Left | Right |
|---|---|---|
| 0:00 | Chat with `@ChamsAssistantBot` | Blank new tab |
| 0:01 | Type: `/compare Ninja Air Fryer 8-quart` | — |
| 0:03 | "🛒 comparing Amazon, Walmart, Target…" | Three tabs spawn: Amazon, Walmart, Target each show the product |
| 0:06 | Bot bubble: formatted table, 3 rows (Amazon $129 ✅, Walmart $139, Target $135 ✅ in-stock) | Tabs visible behind |
| 0:08 | Hold | — |

**Voiceover-safe caption:** "Same product. Three stores. Twenty seconds."

---

## 09 — Appointment booking

**File:** `09-appointment.gif`
**Length:** 13s
**Hook:** "book a dentist" → confirmation email screenshot.

| Time | Left | Right |
|---|---|---|
| 0:00 | Chat with `@ChamsAssistantBot` | Blank tab |
| 0:01 | Type: "book a dentist next Tue or Thu after 5pm within 10 min of 10001, in-network with Aetna" | — |
| 0:03 | "🦷 finding dentists…" | Zocdoc search page loads |
| 0:05 | — | Results filter by insurance, distance, availability |
| 0:07 | "Found Dr. Kim at Flatiron Dental. Next Thu 5:30pm available." | Dr. Kim's booking page |
| 0:09 | "Booking now." | Form fills with user's details, "Confirm" click |
| 0:11 | Screenshot of Gmail confirmation email ("Appointment confirmed: Thu May 8, 5:30pm") | — |

**Voiceover-safe caption:** "Book it without the phone call."

---

## 10 — Schedule & ping

**File:** `10-schedule.gif`
**Length:** 10s
**Hook:** set a recurring macro, then show the morning ping arriving on a lock screen.

| Time | Left | Right |
|---|---|---|
| 0:00 | Chat with `@ChamsMorningBot` | — (or blurred Chrome) |
| 0:01 | Type: `/schedule every day at 9am` | — |
| 0:03 | "📅 scheduled. Next fire: tomorrow 9:00am." | — |
| 0:04 | Scene cut to **a Mac lock screen**, time 9:00am visible | — |
| 0:06 | Telegram notification slides in: "ChamsMorningBot: Your morning: …(3 bullets)" | — |
| 0:09 | Hold on the notification | — |

**Voiceover-safe caption:** "Set it once. It DMs you every morning."

---

## Production checklist

Before recording each GIF, verify:

- [ ] Telegram desktop is zoomed in enough to read (110–125% usually)
- [ ] Chrome has the bookmark bar **hidden** (`⌘⇧B`) — visual noise
- [ ] DevTools closed
- [ ] Adblock extension temporarily off (otherwise a grey "blocked" box ends up in the frame)
- [ ] macOS notifications set to Do Not Disturb (no Slack pings)
- [ ] A throwaway LinkedIn / Amazon / Gmail account with realistic-looking data (not all "TEST TEST TEST")
- [ ] Cursor hidden during recording where possible (`defaults write NSGlobalDomain AppleMiniaturizeOnDoubleClick -int 0`, or use CleanShot X)
- [ ] No personal PII in the frame — blur addresses, masked card numbers, real phone numbers
- [ ] The first frame and last frame are both "clean states" so the loop reads well

## Distribution

- `/web/demos/` — landing page pulls the first three (`01`, `02`, `03`) above the fold
- Twitter thread — all ten, one per tweet, in the order above
- Product Hunt gallery — pick the five strongest (`01`, `02`, `05`, `06`, `10`) in that order
- Email followups — attach the single most relevant GIF per recipient segment
