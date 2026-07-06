# Handoff: ColdEmails — SaaS Redesign (Direction 1b, "Streamlit-shaped")

## Overview
ColdEmails is a personal cold-outreach engine: the user picks a **campaign type**, enters a
few search criteria, and the engine finds real prospects (Hunter.io), researches them, drafts a
personalized email with AI, and sends via Gmail — throttled, de-duplicated, and tracked in a
local SQLite DB. Today the UI is a default Streamlit app (`app.py`); this handoff is the redesign
that makes it feel like a modern SaaS product (Linear / Resend / Attio) while staying **portable
to Streamlit almost 1:1**.

This package covers **Direction 1b only** — the "Streamlit-shaped" layout: a left **sidebar**
(config status) + a single centered **column** that flows top-to-bottom (campaign picker → inputs
→ discover-firms panel → run controls → results). This maps directly onto Streamlit's
`st.sidebar`, `st.columns`, `st.expander`, `st.metric`, and vertical flow.

## About the Design Files
The file in this bundle (`ColdEmails Redesign.dc.html`) is a **design reference created in HTML** —
a high-fidelity prototype showing intended look and behavior, **not production code to copy
directly**. The task is to **recreate this design in the target environment**. The stated
implementation target is **Streamlit (Python)**, so the primary path is to restyle the existing
`app.py` with custom CSS (`st.markdown(..., unsafe_allow_html=True)` + a small CSS block) and
reorganize the layout to match the mock. Where a pattern isn't achievable in vanilla Streamlit,
it's flagged below under **Streamlit feasibility** so you can decide whether to reach for
`streamlit-extras` / custom components, or move to a Next.js + shadcn/ui rebuild (Direction B,
1c/1d, is the design for that path — not included here).

The prototype file contains 5 artboards (1a–1e). **Build from 1b.** The others are reference:
- **1a** — faithful recreation of the *current* Streamlit UI (the "before").
- **1b** — THIS design (the target).
- **1c / 1d** — Direction B (app-shell, two-pane, needs Next.js). Ignore unless you switch paths.
- **1e** — component states (buttons, badges, inputs, prospect card, send-confirm dialog). Use
  as the source of truth for component styling.

## Fidelity
**High-fidelity (hifi).** Final colors, typography, spacing, and states are specified. Recreate
pixel-close using Streamlit theming + a scoped CSS block. Exact hex values and sizes are in
**Design Tokens** below.

---

## Screens / Views

### Sidebar — Configuration status (read-only)
- **Purpose:** show which credentials are set, all read from `.env`. Never an input.
- **Layout:** fixed left column, 280px, white bg, 1px right border, 28px/24px padding, vertical
  flex, 24px gap.
- **Components (top → bottom):**
  - **Wordmark:** 24×18px envelope glyph (1.5px stroke rect with a rotated-square "flap") + "ColdEmails" 15px/600, letter-spacing −0.01em.
  - **Section label:** "CONFIGURATION", Geist Mono 11px, letter-spacing 0.1em, color `#A8A29E`.
  - **Status rows** (one per credential), each: a status dot (8px circle) + label (13px/500) +
    env var name (Geist Mono 11px `#A8A29E`) + right-aligned note ("required" `#78716C` /
    "optional" `#A8A29E`). Row padding 9px/10px, radius 8px.
    - Hunter.io key — `HUNTER_API_KEY` — **green dot `#16A34A`** — required
    - Anthropic key — `ANTHROPIC_API_KEY` — **gray dot `#D6D3D1`**, label muted `#78716C` — optional
    - Serper key — `SERPER_API_KEY` — gray dot — optional
    - Sender email — `SENDER_EMAIL` — green dot — required
    - Gmail OAuth — `GMAIL_CREDENTIALS_FILE` — green dot — required
  - **Note card:** subtle box (`#FAFAF9` bg, 1px `#E7E5E4`, radius 10px, 12/14px pad), 12px/1.55
    text `#78716C`: "Keys live in `.env`, not the UI. Edit the file and restart the app to reload."
  - **Footer (margin-top:auto):** Dark-mode toggle row ("Dark mode" label + 34×20 pill switch,
    off state) and a Geist Mono 11px `#A8A29E` line "SQLite · coldemails.db".
- **Status dot rule:** green `#16A34A` = set, gray `#D6D3D1` = unset. (Replaces the old ✅/— emoji.)

### Main column — New campaign (single centered column, max-width 860px, 48px section gaps)
Header: "New campaign" 26px/600 (−0.02em) + subtitle 14px `#78716C`: "Find the right people,
draft with AI, send only when you're sure."

#### Step 01 — Choose a campaign
- Step header: mono "01" `#A8A29E` + "Choose a campaign" 15px/600.
- **Campaign picker = 4-column grid of cards** (7 cards). Each card: white bg, 1px `#E7E5E4`,
  radius 10px, 14px pad, vertical flex 8px gap:
  - mono tag chip (10px/600, letter-spacing 0.06em, `#78716C` on `#F5F5F4`, radius 5px, 2/7px pad)
  - title 13.5px/600
  - one-line description 12px/1.45 `#78716C`
- **Selected card** (mock shows Fundraising selected): bg `#FFF7ED`, border `#EA580C`, plus a
  3px `#FFEDD5` outer ring (`box-shadow: 0 0 0 3px #FFEDD5`); tag chip `#C2410C` on `#FFEDD5`;
  description color `#9A3412`.
- **The 7 cards (tag — title — description):**
  1. `JOB` — Job outreach — "Reach hiring managers about a role"
  2. `VC` — Fundraising — "Pitch investors at target firms"
  3. `B2B` — B2B sales — "Email decision-makers your offer"
  4. `PR` — PR / media pitch — "Pitch a story to the right beat"
  5. `POD` — Podcast guesting — "Pitch yourself to shows & hosts"
  6. `BD` — Partnerships — "Propose a collab to BD & execs"
  7. `REC` — Recruiting — "Reach candidates about your role"

#### Step 02 — Tell it who to find (dynamic form)
- Fields render **depending on the selected campaign's `requires` list** (from
  `coldemails/campaigns.py`). 2-column grid, 20px gap. Each field: label 13px/500 `#44403C` (with
  a `#EA580C` `*` if required) + input (white, 1px `#E7E5E4`, radius 8px, 40px tall, 14px text) +
  helper text 12px `#A8A29E`.
- Field label map (keep from current app): `company`→"Company name", `role`→"Role / offer / story
  angle", `domain`→"Your domain (e.g. startup domain)", `location`→"Location".
- Per-campaign required fields (`requires`): jobs `[company, role]`, fundraising `[domain]` +
  `needs_firms`, b2b `[company, role]`, pr `[domain, role]`, podcast `[domain, role]`,
  partnerships `[company, role]`, recruiting `[company, role]`.

##### Fundraising-only — "Discover VC & angel firms" panel
Shown only when the selected campaign has `needs_firms` (fundraising). White card, 1px `#E7E5E4`,
radius 12px, 20px pad, vertical flex 16px:
- Title 14px/600 "Discover VC & angel firms" + subtitle 12.5px `#78716C`.
- Filter row: `grid-template-columns: 1fr 1fr 1fr auto`, 10px gap, items end-aligned —
  **Sector** (text), **Stage** (select: "", seed, early, growth), **Location** (text), and a
  dark **"Find firms"** button (`#1C1917` bg, white, radius 8px, 36px tall).
- Live-search toggle row: 30×18 pill switch + "Also search live · needs Serper key" 12.5px `#78716C`.
- Divider (1px `#F5F5F4`).
- Results header: mono "N MATCHES · M SELECTED" 11px `#A8A29E`.
- **Firm chips (selectable):** wrapping flex, 8px gap. Each chip: pill (radius 999px, 7/12px pad)
  with a check/checkbox marker + firm name (13px/600) + domain (Geist Mono 11px) + focus tag
  (10px, radius 4px, 1/6px pad).
  - **Selected chip:** border `#EA580C`, bg `#FFF7ED`, ✓ `#C2410C`, domain `#9A3412`, tag on `#FFEDD5`.
  - **Unselected chip:** border `#E7E5E4`, white bg, empty 12px circle marker, name `#57534E`,
    domain `#A8A29E`, tag on `#F5F5F4`.
- **Target firm domains textarea** (below panel): label "Target firm domains *" + monospace
  textarea (12.5px/1.8, `#44403C`) auto-filled one-domain-per-line from the selection + helper
  "Auto-filled from your selection — add or remove domains freely, one per line."

#### Step 03 — Review & run
- Two columns (`1fr 1.4fr`, 24px gap):
  - **Max prospects** slider (range 1–25, default 10): label + right-aligned mono value in accent
    `#EA580C`; track 4px `#E7E5E4`, filled portion `#EA580C`, 14px white thumb with 2px `#EA580C`
    ring; min/max 11px `#A8A29E`.
  - **Draft mode** = 3-segment control on `#F5F5F4` (radius 10px, 3px pad, 3px gap). Active
    segment: white, radius 8px, subtle shadow. Segments: **Claude Code CLI** / "no API key"
    (default active), **Claude API** / "needs key", **Template** / "no AI".
- **Action bar** (white card, 1px `#E7E5E4`, radius 12px, 16/20px pad, flex align-center 20px gap):
  - **Preview — dry run** primary: `#EA580C` bg, white, radius 8px, 44px tall, 28px pad, 14px/600,
    shadow `0 1px 2px rgba(234,88,12,.35)`. Caption under: "Drafts everything, sends nothing".
  - **Send via Gmail** danger-secondary: white bg, 1px `#FECACA`, text `#DC2626`, radius 8px,
    44px tall, 22px pad, 14px/600. Caption: "Asks to confirm · throttled 45 s".
  - Right note (margin-left:auto), 12.5px `#78716C`, max 280px: "Runs are idempotent — anyone
    already contacted is skipped automatically."

#### Results (appears below on the same page after a run)
- Divider, then a row: "Last run" 15px/600 + mono meta "today 14:32 · preview · fundraising".
- **Metrics row:** single white card, 1px `#E7E5E4`, radius 12px, 5 equal columns divided by 1px
  `#F5F5F4`. Each cell: mono uppercase label 11px `#A8A29E` (letter-spacing 0.08em) + big number
  28px/600. Labels **FOUND / RENDERED / SENT / SKIPPED / FAILED**. Number colors: Found/Rendered
  default `#1C1917`; Sent `#A8A29E` when 0 (else green); Skipped `#78716C`; Failed `#DC2626`.
- **Prospect cards** (one per prospect):
  - **Collapsed:** white card, 1px `#E7E5E4`, radius 12px, 16/20px pad, flex align-center 14px gap:
    name 14px/600 + email (Geist Mono 12.5px `#78716C`) + "Title · Company" 13px `#78716C`, then a
    status badge, then a chevron `#A8A29E`. Skipped/failed rows mute the name/meta color.
  - **Expanded** (border-top `#F5F5F4`, 20px pad, 18px gap):
    - **RESEARCH** quote block: 2px left border `#E7E5E4`, 14px left pad; mono label + italic
      13px `#78716C` background text.
    - **SUBJECT** mono label + 14px/600 subject line.
    - **BODY:** mono label + "click to edit" hint; editable body box `#FAFAF9`, 1px `#E7E5E4`,
      radius 8px, 16/18px pad, 14px/1.65 `#292524`.
- **Run log** = dashed-border collapsed row (`1px dashed #D6D3D1`, radius 10px) with a chevron +
  "Run log" + mono "38 lines". Expands to a monospace code block.
- **Download CSV** button: white, 1px `#E7E5E4`, radius 8px, 38px tall, 13px/500 `#44403C`.

### Status badges (see 1e)
Pill, radius 999px, 4/12px pad, 12px/600, with a 6px leading dot. **Status → color:**
- **previewed = blue:** text/dot `#2563EB`, bg `#EFF6FF`, border `#BFDBFE`.
- **sent = green:** text/dot `#16A34A`, bg `#F0FDF4`, border `#BBF7D0`.
- **failed = red:** text/dot `#DC2626`, bg `#FEF2F2`, border `#FECACA`.
- **skipped = gray:** text `#78716C`, dot `#A8A29E`, bg `#F5F5F4`, border `#E7E5E4`.

### Send-confirm dialog (see 1e) — the chosen confirm pattern
Modal, 420px, white, 1px `#E7E5E4`, radius 14px, shadow `0 32px 64px -24px rgba(28,25,23,.3)`,
24px pad, 18px gap:
- Title "Send N emails via Gmail?" 16px/600 + subtitle "This sends real email from your account.
  It can't be undone." 13px `#78716C`.
- **Summary box** (`#FAFAF9`, radius 10px): rows for Campaign, Prospects ("9 previewed · 2
  skipped"), Throttle ("45 s between sends (~7 min)"), From (`SENDER_EMAIL`, mono).
- **Confirm checkbox:** 16px accent-filled check + "I previewed these drafts" — send button stays
  disabled until checked.
- Buttons (right-aligned): **Cancel** (white, 1px `#E7E5E4`) + **Send N emails** (`#DC2626` bg,
  white, 13px/600).

### Empty state (first run)
Full-screen (or main-column) friendly 3-step explainer. Outline envelope glyph, "Three steps, no
surprises", subtitle "Nothing is ever sent without a preview and a confirm.", then steps
01 Pick a campaign / 02 Preview / 03 Send with mono accent numbers `#EA580C`. (See 1c results pane
for exact copy — reuse it in the single-column layout.)

---

## Interactions & Behavior
- **Campaign select** swaps the Step-02 fields per `requires`, and shows/hides the Discover-firms
  panel per `needs_firms`. On change, clear stale inputs for fields no longer shown.
- **Discover firms → Find firms:** calls `coldemails.firmfinder.discover(sector, stage, location,
  limit=25, use_search)`. Results become selectable chips; selection populates the domains
  textarea (comma or newline separated → list). Empty result → info: "No matches — try a broader
  sector or enable live search."
- **Preview (dry run):** runs the engine with `send=False`; success toast "Preview complete —
  nothing was sent." then render metrics + prospect cards. Never sends.
- **Send via Gmail:** opens the **confirm dialog**; send button disabled until "I previewed these
  drafts" is checked; on confirm, run engine with `send=True`, throttled per campaign
  `throttle_seconds` (30–45s). Idempotent: already-sent prospects are skipped.
- **Prospect card:** click header to expand/collapse; body textarea is editable.
- **Dark mode toggle** flips the whole theme (see Direction B 1d for the dark palette if you
  implement it).
- **Validation:** required fields marked with `*`; block Preview/Send with inline error
  ("Company is required.", input border `#DC2626`, 11.5px `#DC2626` message) if empty.

## State Management
- `campaign` (selected key) → drives fields + firms panel.
- Input values: `company`, `role`, `domain`, `location` (+ `firms: string[]` for fundraising).
- `discovered_firms` (from firmfinder), `selected_firms` (subset).
- `limit` (int 1–25, default 10), `draft_mode` (`claude_cli` | `claude` | `template`).
- `confirm_send` (bool gate), run result (`found/rendered/sent/skipped/failed`), `logs[]`,
  `rows[]` (prospects), `dark_mode` (bool).
- Data: engine reads/writes SQLite via `coldemails.store.Store`; credentials from `os.environ` /
  `.env` (read-only in UI).

## Streamlit feasibility (per component)
- **Sidebar status rows, metrics row, expanders (run log, prospect cards), slider, selectbox,
  download button** — native Streamlit; just restyle via CSS. ✅
- **Campaign card grid** — build with `st.columns` + clickable cards. Vanilla Streamlit has no
  card-button; use `st.button` styled via CSS, or `streamlit-extras`/`st.container(border=True)`
  + a hidden radio, or a small custom component. ⚠️ Flag.
- **Segmented control (draft mode)** — `st.radio(horizontal=True)` styled as segments, or
  `st.segmented_control` (Streamlit ≥1.40). ✅/⚠️
- **Selectable firm chips** — closest native is `st.multiselect`; the pill-chip look needs custom
  CSS or a custom component. ⚠️ Flag. `st.multiselect` is an acceptable fallback.
- **Modal send-confirm dialog** — use `st.dialog` (Streamlit ≥1.37). ✅ (Old two-click inline
  confirm is the fallback if on an older version.)
- **Inline editable body** — `st.text_area` inside the expander. ✅
- **Toast/success** — `st.success` / `st.toast`. ✅
- If the chip/card fidelity matters more than staying in Streamlit, that's the trigger to consider
  the Next.js + shadcn/ui rebuild (Direction B).

## Design Tokens
**Type:** UI/sans = **Geist** (400/500/600/700); mono/data = **Geist Mono** (400/500/600). System
sans fallback. Sizes: display 26px, section 15px, body 13–14px, meta/label 11–12.5px (mono labels
uppercase, letter-spacing 0.08–0.1em).

**Neutrals (warm stone):** page `#FAFAF9`, surface `#FFFFFF`, hairline `#F5F5F4`, border
`#E7E5E4`, border-strong `#D6D3D1`, text `#1C1917`, text-strong `#292524`, text-mid `#44403C` /
`#57534E`, text-muted `#78716C`, text-faint `#A8A29E`.

**Accent (orange):** `#EA580C` (primary), hover `#C2410C`, disabled `#FDBA74`, tint bg `#FFF7ED`,
tint ring `#FFEDD5`, tint text `#9A3412` / `#C2410C`.

**Status:** blue `#2563EB` / bg `#EFF6FF` / border `#BFDBFE`; green `#16A34A` / `#F0FDF4` /
`#BBF7D0`; red `#DC2626` / `#FEF2F2` / `#FECACA`; gray `#78716C` / dot `#A8A29E` / `#F5F5F4` /
`#E7E5E4`.

**Radius:** inputs/buttons 8px, cards 10–12px, dialog 14px, pills/chips 999px.
**Shadow:** card `0 24px 48px -24px rgba(28,25,23,.18)`; primary btn `0 1px 2px rgba(234,88,12,.35)`;
dialog `0 32px 64px -24px rgba(28,25,23,.3)`; segment active `0 1px 2px rgba(28,25,23,.08)`.
**Spacing:** section gap 48px, field gap 16–20px, card pad 14–20px, control height 36–44px.

**Dark palette (bonus, from 1d):** page `#0C0A09` / `#141110`, surface `#1C1917`, border
`#292524` / `#44403C`, text `#FAFAF9` / `#D6D3D1` / `#A8A29E` / `#57534E`, accent `#F97316`,
status greens/reds shift to `#4ADE80` / `#F87171` / `#60A5FA`.

## Assets
- **No image assets.** The only graphic is the envelope wordmark glyph, drawn in CSS/HTML (a
  bordered rect + a rotated square flap) — reproduce with CSS or a small inline SVG. No clip-art,
  no icon library required. Emoji from the current app (✉️ ⚙️ 🔍 📤 📊) are **removed** in this
  redesign in favor of the mono tags and status dots.

## Files
- `ColdEmails Redesign.dc.html` — the HTML prototype (all artboards). Build from **artboard 1b**;
  use **1e** for component states and the **send-confirm dialog**; ignore 1a (before), 1c/1d
  (Direction B). Open in a browser to inspect exact spacing/colors via devtools.
- Source app being restyled: `app.py` (repo `deka1105/ColdEmails`); campaign config in
  `coldemails/campaigns.py`; firm discovery in `coldemails/firmfinder.py`; engine in
  `coldemails/engine.py`; store in `coldemails/store.py`.
