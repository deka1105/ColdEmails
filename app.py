"""Streamlit UI for ColdEmails — drive the whole engine without the CLI.

Run with:  streamlit run app.py

Everything the CLI does is here: set credentials, pick a campaign, fill inputs,
preview (dry-run) rendered emails, send via Gmail, and review status — all from
the browser.
"""

from __future__ import annotations

import os

import streamlit as st

from coldemails.campaigns import CAMPAIGNS, get_campaign
from coldemails.engine import Engine
from coldemails.store import Store

st.set_page_config(page_title="ColdEmails", page_icon="✉️", layout="wide")

FIELD_LABELS = {
    "company": "Company name",
    "role": "Role / offer / story angle",
    "domain": "Your domain (e.g. startup domain)",
    "location": "Location",
}


def db_path() -> str:
    return os.environ.get("COLDEMAILS_DB", "coldemails.db")


# --------------------------------------------------------------------------
# Sidebar: credentials & sender identity (written to the process env)
# --------------------------------------------------------------------------
def credentials_sidebar() -> None:
    st.sidebar.header("⚙️ Configuration")
    st.sidebar.caption("Read from the environment / `.env`. Set these via the CLI, not here.")

    def status_row(label: str, env_name: str, needed: str = "") -> None:
        ok = bool(os.environ.get(env_name))
        st.sidebar.write(f"{'✅' if ok else '—'} **{label}**  \n`{env_name}`{needed}")

    status_row("Hunter.io key", "HUNTER_API_KEY", " · required to find people")
    status_row("Anthropic key", "ANTHROPIC_API_KEY", " · optional (only for 'Claude API key' mode)")
    status_row("Serper key", "SERPER_API_KEY", " · optional (search enrichment)")
    st.sidebar.divider()
    status_row("Sender email", "SENDER_EMAIL", " · required to send")
    status_row("Gmail OAuth file", "GMAIL_CREDENTIALS_FILE")
    st.sidebar.caption(
        "The default **Claude Code CLI** draft mode needs no Anthropic key."
    )


# --------------------------------------------------------------------------
# Run helpers
# --------------------------------------------------------------------------
def run_engine(campaign_name, args, limit, send, personalizer):
    logs: list[str] = []
    with Store(db_path()) as store:
        engine = Engine(store, log=logs.append)
        result = engine.run(
            campaign_name, args, limit=limit, send=send, personalizer=personalizer
        )
        rows = [dict(r) for r in store.list_prospects(campaign_name)]
    return result, logs, rows


def show_result(result, logs, rows):
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Found", result.found)
    c2.metric("Rendered", result.rendered)
    c3.metric("Sent", result.sent)
    c4.metric("Skipped", result.skipped)
    c5.metric("Failed", result.failed)

    with st.expander("Run log"):
        st.code("\n".join(logs) or "(no log output)")

    st.subheader("Prospects & drafted emails")
    if not rows:
        st.info("No prospects yet. Fill inputs and click Preview.")
        return
    for r in rows:
        header = f"{r['name'] or '(no name)'} — {r.get('email') or 'no email'}  ·  {r['status']}"
        with st.expander(header):
            meta = " · ".join(
                str(x) for x in [r.get("title"), r.get("company"), r.get("domain")] if x
            )
            if meta:
                st.caption(meta)
            if r.get("background"):
                st.markdown(f"**Background:** {r['background']}")
            if r.get("subject"):
                st.markdown(f"**Subject:** {r['subject']}")
            if r.get("body"):
                st.text_area("Body", r["body"], height=180, key=f"body_{r['dedup_key']}")
            if r.get("error"):
                st.error(r["error"])


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main() -> None:
    st.title("✉️ ColdEmails")
    st.caption("Find the right people, personalize with AI, and send — no command line needed.")
    credentials_sidebar()

    campaign_name = st.selectbox(
        "Campaign",
        list(CAMPAIGNS),
        format_func=lambda n: {
            "jobs": "Job outreach (company + role)",
            "fundraising": "Fundraising (find VCs/angels)",
            "b2b": "B2B sales",
            "pr": "PR / media pitch",
        }.get(n, n),
    )
    campaign = get_campaign(campaign_name)
    required = set(campaign.get("requires", []))

    st.subheader("Inputs")
    args: dict = {}
    cols = st.columns(2)
    for i, field in enumerate(["company", "role", "domain", "location"]):
        label = FIELD_LABELS[field] + (" *" if field in required else "")
        args[field] = cols[i % 2].text_input(label, key=f"in_{field}") or None

    if campaign.get("needs_firms"):
        with st.expander("🔎 Discover VC / angel firms (don't know the domains?)", expanded=True):
            from coldemails.firmfinder import discover

            d1, d2, d3 = st.columns(3)
            sector = d1.text_input("Sector", placeholder="climate, fintech, ai…")
            stage = d2.selectbox("Stage", ["", "seed", "early", "growth"])
            loc = d3.text_input("Location", placeholder="US, EU…")
            use_search = st.checkbox("Also search live (needs Serper key)", value=False)
            if st.button("Find firms"):
                found = discover(
                    sector=sector or None, stage=stage or None, location=loc or None,
                    limit=25, use_search=use_search,
                )
                st.session_state["discovered_firms"] = found
                if not found:
                    st.info("No matches — try a broader sector or enable live search.")

            discovered = st.session_state.get("discovered_firms", [])
            if discovered:
                options = [f.domain for f in discovered]
                labels = {f.domain: f"{f.domain} — {f.name}" for f in discovered}
                st.session_state.setdefault("selected_firms", options)
                st.multiselect(
                    "Firms to target (edit as you like)",
                    options,
                    default=st.session_state.get("selected_firms", options),
                    format_func=lambda d: labels.get(d, d),
                    key="selected_firms",
                )

        firms_raw = st.text_area(
            "Target firm domains * (one per line; auto-filled by discovery above)",
            value="\n".join(st.session_state.get("selected_firms", [])),
            placeholder="a16z.com\nsequoiacap.com",
        )
        args["firms"] = [
            d.strip()
            for d in firms_raw.replace(",", "\n").splitlines()
            if d.strip()
        ]

    c1, c2 = st.columns(2)
    limit = c1.slider("Max prospects", 1, 25, 10)
    mode = c2.selectbox(
        "Draft mode",
        ["Claude Code CLI (no API key)", "Claude API key", "Plain template (no AI)"],
        help="Claude Code CLI uses your local `claude` login — no ANTHROPIC_API_KEY needed.",
    )
    personalizer = {
        "Claude Code CLI (no API key)": "claude_cli",
        "Claude API key": "claude",
        "Plain template (no AI)": "template",
    }[mode]

    st.divider()
    b1, b2 = st.columns(2)
    preview_clicked = b1.button("🔍 Preview (dry-run)", use_container_width=True, type="primary")
    send_clicked = b2.button("📤 Send via Gmail", use_container_width=True)

    if preview_clicked:
        try:
            with st.spinner("Finding people and drafting…"):
                res = run_engine(campaign_name, args, limit, send=False, personalizer=personalizer)
            st.success("Preview complete — nothing was sent.")
            show_result(*res)
        except Exception as e:
            st.error(f"{e}")

    if send_clicked:
        if not st.session_state.get("confirm_send"):
            st.session_state["confirm_send"] = True
            st.warning("This will send real emails via Gmail. Click **Send via Gmail** again to confirm.")
        else:
            st.session_state["confirm_send"] = False
            try:
                with st.spinner("Sending (throttled)…"):
                    res = run_engine(campaign_name, args, limit, send=True, personalizer=personalizer)
                st.success(f"Done — {res[0].sent} sent.")
                show_result(*res)
            except Exception as e:
                st.error(f"{e}")

    st.divider()
    with st.expander("📊 Status for this campaign"):
        with Store(db_path()) as store:
            counts = store.counts_by_status(campaign_name)
        st.write(counts or "No prospects recorded yet.")


if __name__ == "__main__":
    main()
