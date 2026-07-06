"""Streamlit UI for ColdEmails — drive the whole engine without the CLI.

Run with:  streamlit run app.py

Design: "Direction 1b" from design_handoff_1b_streamlit/ — a SaaS-style
restyle (warm stone neutrals, orange accent, Geist type) of the original
single-column layout: sidebar config status → campaign cards → dynamic form →
discover-firms panel → run controls → results. Tokens and component specs live
in that handoff README; this file recreates them with scoped CSS + native
Streamlit widgets (keyed containers, pills, segmented control, dialog).
"""

from __future__ import annotations

import os
from string import Template

import streamlit as st

# The redesigned UI relies on st.dialog / st.pills / st.segmented_control /
# keyed containers. Fail with instructions rather than a mid-page traceback.
if not hasattr(st, "dialog"):
    st.error(
        f"This app needs Streamlit ≥ 1.40 (you have {st.__version__}). "
        "Run it with the project venv:\n\n"
        "`.venv/bin/streamlit run app.py`\n\n"
        "or upgrade: `pip install -U streamlit`"
    )
    st.stop()

from coldemails.campaigns import CAMPAIGNS, get_campaign
from coldemails.engine import Engine
from coldemails.store import Store

st.set_page_config(page_title="ColdEmails", layout="centered")

# ---------------------------------------------------------------------------
# Design tokens (design_handoff_1b_streamlit/README.md · "Design Tokens")
# ---------------------------------------------------------------------------
LIGHT = dict(
    page="#FAFAF9", surface="#FFFFFF", hairline="#F5F5F4", border="#E7E5E4",
    border_strong="#D6D3D1", text="#1C1917", text_strong="#292524",
    text_mid="#44403C", text_mid2="#57534E", muted="#78716C", faint="#A8A29E",
    accent="#EA580C", accent_hover="#C2410C", accent_tint="#FFF7ED",
    accent_ring="#FFEDD5", accent_text="#9A3412", accent_text2="#C2410C",
    green="#16A34A", green_bg="#F0FDF4", green_bd="#BBF7D0",
    red="#DC2626", red_bg="#FEF2F2", red_bd="#FECACA",
    blue="#2563EB", blue_bg="#EFF6FF", blue_bd="#BFDBFE",
)
DARK = dict(
    LIGHT,
    page="#0C0A09", surface="#1C1917", hairline="#292524", border="#292524",
    border_strong="#44403C", text="#FAFAF9", text_strong="#FAFAF9",
    text_mid="#D6D3D1", text_mid2="#D6D3D1", muted="#A8A29E", faint="#57534E",
    accent="#F97316", accent_tint="#2A1508", accent_ring="#3B2010",
    accent_text="#FDBA74", accent_text2="#F97316",
    green="#4ADE80", green_bg="#122117", green_bd="#1E3A26",
    red="#F87171", red_bg="#2A1414", red_bd="#452020",
    blue="#60A5FA", blue_bg="#111B2E", blue_bd="#1E3355",
)

CSS = Template("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&family=Geist+Mono:wght@400;500;600&display=swap');

html, body, [class*="st-"], .stApp { font-family: 'Geist', -apple-system, sans-serif; }
/* Don't override Streamlit's icon font (breaks into raw ligature text). */
[data-testid="stIconMaterial"], [class*="material-symbols"] {
  font-family: 'Material Symbols Rounded' !important;
}
.stApp { background: $page; color: $text; }
/* Hide Streamlit chrome (Deploy button, menu, colored header strip). */
header[data-testid="stHeader"] { background: transparent; }
[data-testid="stToolbar"], [data-testid="stDecoration"], #MainMenu { display: none; }
.block-container { max-width: 920px; padding-top: 2.6rem; }
h1, h2, h3 { letter-spacing: -0.02em; color: $text; }
hr { border-color: $hairline; }
code { font-family: 'Geist Mono', monospace; }

/* ---- sidebar -------------------------------------------------------- */
[data-testid="stSidebar"] {
  background: $surface; border-right: 1px solid $border; min-width: 280px;
}
[data-testid="stSidebar"] * { color: $text_mid; }
.ce-wordmark { display: flex; align-items: center; gap: 10px; margin: 4px 0 14px; }
.ce-wordmark .glyph {
  width: 24px; height: 18px; border: 1.5px solid $text; border-radius: 3px;
  position: relative; overflow: hidden; flex: none;
}
.ce-wordmark .glyph::after {
  content: ""; position: absolute; width: 16px; height: 16px; left: 2.5px; top: -10px;
  border: 1.5px solid $text; transform: rotate(45deg); background: $surface;
}
.ce-wordmark .name { font-size: 15px; font-weight: 600; letter-spacing: -0.01em; color: $text; }
.ce-label {
  font-family: 'Geist Mono', monospace; font-size: 11px; letter-spacing: 0.1em;
  color: $faint; text-transform: uppercase; margin: 10px 0 6px;
}
.ce-status { display: flex; align-items: center; gap: 9px; padding: 9px 10px; border-radius: 8px; }
.ce-status .dot { width: 8px; height: 8px; border-radius: 50%; flex: none; }
.ce-status .lbl { font-size: 13px; font-weight: 500; color: $text_mid; }
.ce-status .lbl.off { color: $muted; }
.ce-status .env { font-family: 'Geist Mono', monospace; font-size: 11px; color: $faint; }
.ce-status .note { margin-left: auto; font-size: 11px; }
.ce-note-card {
  background: $page; border: 1px solid $border; border-radius: 10px;
  padding: 12px 14px; font-size: 12px; line-height: 1.55; color: $muted; margin-top: 14px;
}
.ce-sidebar-foot {
  font-family: 'Geist Mono', monospace; font-size: 11px; color: $faint; margin-top: 10px;
}

/* ---- step headers ---------------------------------------------------- */
.ce-step { display: flex; align-items: baseline; gap: 10px; margin: 6px 0 12px; }
.ce-step .num { font-family: 'Geist Mono', monospace; font-size: 12px; color: $faint; }
.ce-step .ttl { font-size: 15px; font-weight: 600; color: $text; }
.ce-sub { font-size: 14px; color: $muted; margin-top: -8px; }

/* ---- campaign cards --------------------------------------------------- */
div[class*="st-key-card_"] {
  background: $surface; border: 1px solid $border; border-radius: 10px;
  padding: 14px; gap: 8px; height: 100%;
}
div[class*="st-key-card_"] .stButton button {
  background: transparent; border: none; padding: 0; min-height: 0;
  font-size: 13.5px; font-weight: 600; color: $text; justify-content: flex-start;
  text-align: left; width: 100%;
}
div[class*="st-key-card_"] .stButton button:hover { color: $accent_hover; background: transparent; }
div[class*="st-key-card_"] .stButton button:focus:not(:active) { color: $text; }
.ce-tag {
  display: inline-block; font-family: 'Geist Mono', monospace; font-size: 10px;
  font-weight: 600; letter-spacing: 0.06em; color: $muted; background: $hairline;
  border-radius: 5px; padding: 2px 7px;
}
.ce-card-desc { font-size: 12px; line-height: 1.45; color: $muted; margin: 0; }
div.st-key-card_$selected {
  background: $accent_tint; border-color: $accent; box-shadow: 0 0 0 3px $accent_ring;
}
div.st-key-card_$selected .ce-tag { color: $accent_text2; background: $accent_ring; }
div.st-key-card_$selected .ce-card-desc { color: $accent_text; }
div.st-key-card_$selected .stButton button { color: $text; }

/* ---- inputs ----------------------------------------------------------- */
.stTextInput input, .stTextArea textarea, .stSelectbox [data-baseweb="select"] > div {
  background: $surface; border: 1px solid $border; border-radius: 8px;
  font-size: 14px; color: $text_mid;
}
.stTextArea textarea { font-family: 'Geist Mono', monospace; font-size: 12.5px; line-height: 1.8; }
.stTextInput label p, .stTextArea label p, .stSelectbox label p, .stSlider label p,
.stCheckbox label p, .stToggle label p {
  font-size: 13px; font-weight: 500; color: $text_mid;
}
.stCaption, [data-testid="stCaptionContainer"] { color: $faint !important; }
.req { color: $accent; }

/* ---- discover firms card / bordered containers ------------------------ */
div.st-key-firms_panel, div.st-key-action_bar {
  background: $surface; border: 1px solid $border; border-radius: 12px; padding: 20px;
}
.ce-matches {
  font-family: 'Geist Mono', monospace; font-size: 11px; letter-spacing: 0.08em;
  color: $faint; text-transform: uppercase;
}
/* pills (firm chips) — st.pills renders as a stButtonGroup; scope via panel */
div.st-key-firms_panel [data-testid="stButtonGroup"] button {
  border-radius: 999px; border: 1px solid $border; background: $surface;
  color: $text_mid2; font-size: 13px; font-weight: 600;
}
div.st-key-firms_panel [data-testid="stButtonGroup"] button[aria-checked="true"] {
  border-color: $accent; background: $accent_tint; color: $accent_text2;
}

/* ---- segmented control / slider --------------------------------------- */
[data-testid="stButtonGroup"] button {
  font-size: 13px; background: $hairline; color: $text_mid; border-color: $border;
}
[data-testid="stButtonGroup"] button[aria-checked="true"] {
  background: $surface; color: $accent_text2; border-color: $accent;
}
.stSlider [data-baseweb="slider"] div[role="slider"] {
  background: $surface; border: 2px solid $accent;
}

/* ---- action buttons ---------------------------------------------------- */
div.st-key-btn_preview button {
  background: $accent; color: #fff; border: none; border-radius: 8px;
  height: 44px; padding: 0 28px; font-size: 14px; font-weight: 600;
  box-shadow: 0 1px 2px rgba(234,88,12,.35); width: 100%;
}
div.st-key-btn_preview button:hover { background: $accent_hover; color: #fff; }
div.st-key-btn_send button {
  background: $surface; color: $red; border: 1px solid $red_bd; border-radius: 8px;
  height: 44px; padding: 0 22px; font-size: 14px; font-weight: 600; width: 100%;
}
div.st-key-btn_send button:hover { border-color: $red; color: $red; }
.ce-action-note { font-size: 12.5px; color: $muted; max-width: 280px; }

/* ---- results ----------------------------------------------------------- */
.ce-run-meta { font-family: 'Geist Mono', monospace; font-size: 12px; color: $faint; }
.ce-metrics {
  display: grid; grid-template-columns: repeat(5, 1fr); background: $surface;
  border: 1px solid $border; border-radius: 12px; overflow: hidden; margin: 8px 0 16px;
}
.ce-metrics .cell { padding: 16px 20px; border-left: 1px solid $hairline; }
.ce-metrics .cell:first-child { border-left: none; }
.ce-metrics .k {
  font-family: 'Geist Mono', monospace; font-size: 11px; letter-spacing: 0.08em;
  text-transform: uppercase; color: $faint;
}
.ce-metrics .v { font-size: 28px; font-weight: 600; color: $text; margin-top: 2px; }
.ce-badge {
  display: inline-flex; align-items: center; gap: 6px; border-radius: 999px;
  padding: 4px 12px; font-size: 12px; font-weight: 600;
}
.ce-badge .d { width: 6px; height: 6px; border-radius: 50%; }
.ce-quote {
  border-left: 2px solid $border; padding-left: 14px; font-size: 13px;
  font-style: italic; color: $muted;
}
.ce-mono-label {
  font-family: 'Geist Mono', monospace; font-size: 11px; letter-spacing: 0.08em;
  text-transform: uppercase; color: $faint; margin-bottom: 2px;
}
[data-testid="stExpander"] {
  background: $surface; border: 1px solid $border; border-radius: 12px;
}
[data-testid="stExpander"] summary { font-size: 14px; font-weight: 600; color: $text; }
div.st-key-runlog [data-testid="stExpander"] {
  border: 1px dashed $border_strong; border-radius: 10px; background: transparent;
}
div.st-key-btn_csv button {
  background: $surface; border: 1px solid $border; border-radius: 8px;
  height: 38px; font-size: 13px; font-weight: 500; color: $text_mid;
}

/* ---- empty state -------------------------------------------------------- */
.ce-empty { text-align: center; padding: 48px 0 28px; }
.ce-empty .glyph {
  width: 44px; height: 33px; border: 2px solid $border_strong; border-radius: 5px;
  margin: 0 auto 18px; position: relative; overflow: hidden;
}
.ce-empty .glyph::after {
  content: ""; position: absolute; width: 30px; height: 30px; left: 5px; top: -19px;
  border: 2px solid $border_strong; transform: rotate(45deg);
}
.ce-empty h3 { font-size: 18px; margin-bottom: 4px; }
.ce-empty p { font-size: 13.5px; color: $muted; }
.ce-empty .steps { display: flex; justify-content: center; gap: 40px; margin-top: 26px; }
.ce-empty .step .n { font-family: 'Geist Mono', monospace; font-size: 12px; color: $accent; }
.ce-empty .step .t { font-size: 13.5px; font-weight: 600; color: $text_mid; margin-top: 3px; }
</style>
""")

CAMPAIGN_CARDS = [
    ("jobs", "JOB", "Job outreach", "Reach hiring managers about a role"),
    ("fundraising", "VC", "Fundraising", "Pitch investors at target firms"),
    ("b2b", "B2B", "B2B sales", "Email decision-makers your offer"),
    ("pr", "PR", "PR / media pitch", "Pitch a story to the right beat"),
    ("podcast", "POD", "Podcast guesting", "Pitch yourself to shows & hosts"),
    ("partnerships", "BD", "Partnerships", "Propose a collab to BD & execs"),
    ("recruiting", "REC", "Recruiting", "Reach candidates about your role"),
]

FIELD_LABELS = {
    "company": "Company name",
    "role": "Role / offer / story angle",
    "domain": "Your domain (e.g. startup domain)",
    "location": "Location",
}
FIELD_HELP = {
    "company": "Resolved to a web domain automatically",
    "role": "What you want / offer / pitch — used in the draft",
    "domain": "Used as context in the email",
    "location": "Optional — narrows the framing",
}

BADGE = {  # status -> (text, dot, bg, border)
    "previewed": ("blue", "blue", "blue_bg", "blue_bd"),
    "sent": ("green", "green", "green_bg", "green_bd"),
    "failed": ("red", "red", "red_bg", "red_bd"),
    "skipped": ("muted", "faint", "hairline", "border"),
    "found": ("muted", "faint", "hairline", "border"),
}


def db_path() -> str:
    return os.environ.get("COLDEMAILS_DB", "coldemails.db")


def T() -> dict:
    return DARK if st.session_state.get("dark_mode") else LIGHT


def badge(status: str) -> str:
    t = T()
    txt, dot, bg, bd = BADGE.get(status, BADGE["found"])
    return (
        f'<span class="ce-badge" style="color:{t[txt]};background:{t[bg]};'
        f'border:1px solid {t[bd]}"><span class="d" style="background:{t[dot]}">'
        f"</span>{status}</span>"
    )


# ---------------------------------------------------------------------------
# Sidebar — configuration status (read-only; design §Sidebar)
# ---------------------------------------------------------------------------
def credentials_sidebar() -> None:
    t = T()

    def row(label: str, env_name: str, note: str, is_set: bool | None = None) -> str:
        if is_set is None:
            is_set = bool(os.environ.get(env_name))
        dot = t["green"] if is_set else t["border_strong"]
        lbl_cls = "lbl" if is_set else "lbl off"
        note_color = t["muted"] if note == "required" else t["faint"]
        return (
            f'<div class="ce-status"><span class="dot" style="background:{dot}"></span>'
            f'<span><span class="{lbl_cls}">{label}</span><br>'
            f'<span class="env">{env_name}</span></span>'
            f'<span class="note" style="color:{note_color}">{note}</span></div>'
        )

    with st.sidebar:
        st.markdown(
            '<div class="ce-wordmark"><span class="glyph"></span>'
            '<span class="name">ColdEmails</span></div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div class="ce-label">Configuration</div>', unsafe_allow_html=True)
        st.markdown(
            row("Hunter.io key", "HUNTER_API_KEY", "required")
            + row("Anthropic key", "ANTHROPIC_API_KEY", "optional")
            + row("Serper key", "SERPER_API_KEY", "optional")
            + row("Sender email", "SENDER_EMAIL", "required")
            # The env var holds a *path* with a default — green only if the
            # OAuth client secret file actually exists.
            + row(
                "Gmail OAuth", "GMAIL_CREDENTIALS_FILE", "required",
                is_set=os.path.exists(
                    os.environ.get("GMAIL_CREDENTIALS_FILE", "credentials.json")
                ),
            ),
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="ce-note-card">Keys live in <code>.env</code>, not the UI. '
            "Edit the file and restart the app to reload.</div>",
            unsafe_allow_html=True,
        )
        st.toggle("Dark mode", key="dark_mode")
        st.markdown(
            f'<div class="ce-sidebar-foot">SQLite · {os.path.basename(db_path())}</div>',
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Run helpers (unchanged wiring — test_app.py depends on this signature)
# ---------------------------------------------------------------------------
def run_engine(campaign_name, args, limit, send, personalizer):
    logs: list[str] = []
    with Store(db_path()) as store:
        engine = Engine(store, log=logs.append)
        result = engine.run(
            campaign_name, args, limit=limit, send=send, personalizer=personalizer
        )
        rows = [dict(r) for r in store.list_prospects(campaign_name)]
    return result, logs, rows


def prospects_csv(rows: list[dict]) -> str:
    import csv
    import io

    cols = [
        "campaign", "name", "email", "title", "company", "domain",
        "status", "subject", "body", "background", "error",
    ]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(cols)
    for r in rows:
        w.writerow([r.get(c) for c in cols])
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Results (design §Results)
# ---------------------------------------------------------------------------
def show_result(result, logs, rows, meta: str) -> None:
    t = T()
    st.divider()
    c1, c2 = st.columns([1, 2])
    c1.markdown("**Last run**")
    c2.markdown(
        f'<div class="ce-run-meta" style="text-align:right">{meta}</div>',
        unsafe_allow_html=True,
    )

    sent_color = t["faint"] if result.sent == 0 else t["green"]
    cells = [
        ("Found", result.found, t["text"]),
        ("Rendered", result.rendered, t["text"]),
        ("Sent", result.sent, sent_color),
        ("Skipped", result.skipped, t["muted"]),
        ("Failed", result.failed, t["red"] if result.failed else t["faint"]),
    ]
    html = '<div class="ce-metrics">' + "".join(
        f'<div class="cell"><div class="k">{k}</div>'
        f'<div class="v" style="color:{c}">{v}</div></div>'
        for k, v, c in cells
    ) + "</div>"
    st.markdown(html, unsafe_allow_html=True)

    for r in rows:
        title = r["name"] or "(no name)"
        email = r.get("email") or "no email"
        meta_line = " · ".join(str(x) for x in [r.get("title"), r.get("company")] if x)
        with st.expander(f"{title} — {email}   ·   {r['status']}"):
            st.markdown(badge(r["status"]), unsafe_allow_html=True)
            if meta_line:
                st.caption(meta_line)
            if r.get("background"):
                st.markdown(
                    '<div class="ce-mono-label">Research</div>'
                    f'<div class="ce-quote">{r["background"]}</div>',
                    unsafe_allow_html=True,
                )
            if r.get("subject"):
                st.markdown(
                    '<div class="ce-mono-label">Subject</div>'
                    f'<div style="font-size:14px;font-weight:600">{r["subject"]}</div>',
                    unsafe_allow_html=True,
                )
            if r.get("body"):
                st.markdown('<div class="ce-mono-label">Body</div>', unsafe_allow_html=True)
                st.text_area(
                    "Body", r["body"], height=180,
                    key=f"body_{r['dedup_key']}", label_visibility="collapsed",
                )
            if r.get("error"):
                st.error(r["error"])

    with st.container(key="runlog"):
        with st.expander(f"Run log · {len(logs)} lines"):
            st.code("\n".join(logs) or "(no log output)")

    with st.container(key="btn_csv"):
        st.download_button(
            "Download CSV", prospects_csv(rows),
            file_name=f"coldemails_{rows[0]['campaign']}.csv" if rows else "coldemails.csv",
            mime="text/csv",
        )


def show_history(counts: dict, rows: list[dict], campaign_name: str) -> None:
    """Past prospects for this campaign (shown when there's no fresh run)."""
    st.divider()
    c1, c2 = st.columns([1, 2])
    c1.markdown("**Previous prospects**")
    meta = " · ".join(f"{n} {s}" for s, n in sorted(counts.items()))
    c2.markdown(
        f'<div class="ce-run-meta" style="text-align:right">{meta}</div>',
        unsafe_allow_html=True,
    )
    for r in rows:
        title = r["name"] or "(no name)"
        email = r.get("email") or "no email"
        with st.expander(f"{title} — {email}   ·   {r['status']}"):
            st.markdown(badge(r["status"]), unsafe_allow_html=True)
            meta_line = " · ".join(str(x) for x in [r.get("title"), r.get("company")] if x)
            if meta_line:
                st.caption(meta_line)
            if r.get("subject"):
                st.markdown(
                    '<div class="ce-mono-label">Subject</div>'
                    f'<div style="font-size:14px;font-weight:600">{r["subject"]}</div>',
                    unsafe_allow_html=True,
                )
            if r.get("body"):
                st.markdown('<div class="ce-mono-label">Body</div>', unsafe_allow_html=True)
                st.text_area(
                    "Body", r["body"], height=180,
                    key=f"hbody_{r['dedup_key']}", label_visibility="collapsed",
                )
            if r.get("error"):
                st.error(r["error"])
    with st.container(key="btn_csv"):
        st.download_button(
            "Download CSV", prospects_csv(rows),
            file_name=f"coldemails_{campaign_name}.csv", mime="text/csv",
        )


def empty_state() -> None:
    st.markdown(
        """
        <div class="ce-empty">
          <div class="glyph"></div>
          <h3>Three steps, no surprises</h3>
          <p>Nothing is ever sent without a preview and a confirm.</p>
          <div class="steps">
            <div class="step"><div class="n">01</div><div class="t">Pick a campaign</div></div>
            <div class="step"><div class="n">02</div><div class="t">Preview</div></div>
            <div class="step"><div class="n">03</div><div class="t">Send</div></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Send-confirm dialog (design §Send-confirm dialog)
# ---------------------------------------------------------------------------
@st.dialog("Send emails via Gmail?")
def confirm_send_dialog(campaign_name, args, limit, personalizer, throttle):
    t = T()
    st.markdown(
        f'<span style="font-size:13px;color:{t["muted"]}">This sends real email '
        "from your account. It can't be undone.</span>",
        unsafe_allow_html=True,
    )
    sender = os.environ.get("SENDER_EMAIL", "(SENDER_EMAIL not set)")
    st.markdown(
        f"""
| | |
|---|---|
| **Campaign** | {campaign_name} |
| **Max prospects** | {limit} |
| **Throttle** | {throttle} s between sends |
| **From** | `{sender}` |
"""
    )
    ok = st.checkbox("I previewed these drafts")
    c1, c2 = st.columns(2)
    if c1.button("Cancel", use_container_width=True):
        st.rerun()
    if c2.button("Send emails", type="primary", disabled=not ok, use_container_width=True):
        try:
            with st.spinner("Sending (throttled)…"):
                res = run_engine(campaign_name, args, limit, send=True, personalizer=personalizer)
            st.session_state["last_run"] = (res, "send", campaign_name)
        except Exception as e:
            st.session_state["last_error"] = str(e)
        st.rerun()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    st.session_state.setdefault("campaign", "jobs")
    st.markdown(
        CSS.substitute(T(), selected=st.session_state["campaign"]),
        unsafe_allow_html=True,
    )
    credentials_sidebar()

    st.markdown("## New campaign")
    st.markdown(
        '<p class="ce-sub">Find the right people, draft with AI, '
        "send only when you're sure.</p>",
        unsafe_allow_html=True,
    )

    # --- Step 01 — choose a campaign (card grid) -------------------------
    st.markdown(
        '<div class="ce-step"><span class="num">01</span>'
        '<span class="ttl">Choose a campaign</span></div>',
        unsafe_allow_html=True,
    )
    rows = [CAMPAIGN_CARDS[:4], CAMPAIGN_CARDS[4:]]
    for row_cards in rows:
        cols = st.columns(4)
        for col, (key, tag, title, desc) in zip(cols, row_cards):
            with col, st.container(key=f"card_{key}"):
                st.markdown(f'<span class="ce-tag">{tag}</span>', unsafe_allow_html=True)
                if st.button(title, key=f"pick_{key}"):
                    st.session_state["campaign"] = key
                    st.rerun()
                st.markdown(f'<p class="ce-card-desc">{desc}</p>', unsafe_allow_html=True)

    campaign_name = st.session_state["campaign"]
    campaign = get_campaign(campaign_name)
    required = set(campaign.get("requires", []))

    # --- Step 02 — dynamic form ------------------------------------------
    st.markdown(
        '<div class="ce-step"><span class="num">02</span>'
        '<span class="ttl">Tell it who to find</span></div>',
        unsafe_allow_html=True,
    )
    args: dict = {}
    fields = [f for f in ["company", "role", "domain", "location"] if f in required]
    fields += [f for f in ["location"] if f not in fields]  # location always shown
    cols = st.columns(2)
    for i, field in enumerate(fields):
        star = " :orange[*]" if field in required else ""
        args[field] = (
            cols[i % 2].text_input(
                FIELD_LABELS[field] + star, key=f"in_{campaign_name}_{field}",
                help=FIELD_HELP[field],
            )
            or None
        )

    # Fundraising-only: discover firms panel + target domains textarea.
    if campaign.get("needs_firms"):
        with st.container(key="firms_panel"):
            st.markdown("**Discover VC & angel firms**")
            st.caption("Filter a curated catalog by sector, stage, and location.")
            d1, d2, d3, d4 = st.columns([1, 1, 1, 0.8], vertical_alignment="bottom")
            sector = d1.text_input("Sector", placeholder="climate, fintech, ai…")
            stage = d2.selectbox("Stage", ["", "seed", "early", "growth"])
            loc = d3.text_input("Location", placeholder="US, EU…")
            find = d4.button("Find firms", use_container_width=True)
            use_search = st.toggle("Also search live · needs Serper key", value=False)
            if find:
                from coldemails.firmfinder import discover

                found = discover(
                    sector=sector or None, stage=stage or None, location=loc or None,
                    limit=25, use_search=use_search,
                )
                st.session_state["discovered_firms"] = found
                if not found:
                    st.info("No matches — try a broader sector or enable live search.")

            discovered = st.session_state.get("discovered_firms", [])
            if discovered:
                labels = {f.domain: f"{f.name} · {f.domain}" for f in discovered}
                selected = st.pills(
                    "Firms", [f.domain for f in discovered],
                    selection_mode="multi",
                    default=[f.domain for f in discovered],
                    format_func=lambda d: labels.get(d, d),
                    label_visibility="collapsed",
                )
                st.markdown(
                    f'<span class="ce-matches">{len(discovered)} matches · '
                    f"{len(selected)} selected</span>",
                    unsafe_allow_html=True,
                )
                st.session_state["selected_firms"] = selected

        firms_raw = st.text_area(
            "Target firm domains :orange[*]",
            value="\n".join(st.session_state.get("selected_firms", [])),
            placeholder="a16z.com\nsequoiacap.com",
            help="Auto-filled from your selection — add or remove domains freely, one per line.",
        )
        args["firms"] = [
            d.strip() for d in firms_raw.replace(",", "\n").splitlines() if d.strip()
        ]

    # --- Step 03 — review & run -------------------------------------------
    st.markdown(
        '<div class="ce-step"><span class="num">03</span>'
        '<span class="ttl">Review &amp; run</span></div>',
        unsafe_allow_html=True,
    )
    c1, c2 = st.columns([1, 1.4])
    limit = c1.slider("Max prospects", 1, 25, 10)
    mode = c2.segmented_control(
        "Draft mode",
        ["Claude Code CLI", "Claude API", "Template"],
        default="Claude Code CLI",
        help="Claude Code CLI uses your local `claude` login — no ANTHROPIC_API_KEY needed.",
    )
    personalizer = {
        "Claude Code CLI": "claude_cli",
        "Claude API": "claude",
        "Template": "template",
    }[mode or "Claude Code CLI"]

    with st.container(key="action_bar"):
        b1, b2, b3 = st.columns([1.1, 1, 1.4], vertical_alignment="center")
        with b1, st.container(key="btn_preview"):
            preview_clicked = st.button("Preview — dry run")
            st.caption("Drafts everything, sends nothing")
        with b2, st.container(key="btn_send"):
            send_clicked = st.button("Send via Gmail")
            st.caption(f"Asks to confirm · throttled {campaign.get('throttle_seconds', 30)} s")
        b3.markdown(
            '<p class="ce-action-note">Runs are idempotent — anyone already '
            "contacted is skipped automatically.</p>",
            unsafe_allow_html=True,
        )

    # Validation: block runs on missing required fields.
    def missing_fields() -> list[str]:
        miss = [FIELD_LABELS[f] for f in required if not args.get(f)]
        if campaign.get("needs_firms") and not args.get("firms"):
            miss.append("Target firm domains")
        return miss

    if err := st.session_state.pop("last_error", None):
        st.error(err)

    if preview_clicked:
        if miss := missing_fields():
            st.error(f"{miss[0]} is required.")
        else:
            try:
                with st.spinner("Finding people and drafting…"):
                    res = run_engine(
                        campaign_name, args, limit, send=False, personalizer=personalizer
                    )
                st.session_state["last_run"] = (res, "preview", campaign_name)
                st.toast("Preview complete — nothing was sent.")
            except Exception as e:
                st.error(f"{e}")

    if send_clicked:
        if miss := missing_fields():
            st.error(f"{miss[0]} is required.")
        else:
            confirm_send_dialog(
                campaign_name, args, limit, personalizer,
                campaign.get("throttle_seconds", 30),
            )

    # --- Results / history / empty state -------------------------------------
    last = st.session_state.get("last_run")
    if last and last[2] == campaign_name:
        (result, logs, rows), verb, _ = last
        import datetime

        stamp = datetime.datetime.now().strftime("today %H:%M")
        show_result(result, logs, rows, f"{stamp} · {verb} · {campaign_name}")
    else:
        with Store(db_path()) as store:
            counts = store.counts_by_status(campaign_name)
            rows = [dict(r) for r in store.list_prospects(campaign_name)]
        if rows:
            show_history(counts, rows, campaign_name)
        else:
            empty_state()


if __name__ == "__main__":
    main()
