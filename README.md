# ColdEmails

Multi-purpose outreach automation. Give it search criteria; it finds the right
people, discovers their emails, researches their background, writes a
personalized message with AI, and sends it via Gmail — paced, de-duplicated,
and tracked.

```
input criteria → find people → find email → research → personalize → send + track
```

One engine, many use cases. Each use case is a **campaign** (config) that only
changes *who you target* and *what you personalize on*. Everything else — email
finding, drafting, throttling, dedup, tracking — is shared.

---

## Contents

- [Use cases](#use-cases)
- [Install](#install)
- [Configuration (.env)](#configuration-env)
- [Personalization / draft modes](#personalization--draft-modes)
- [Command line](#command-line)
- [Web UI](#web-ui)
- [Discovering VC / angel firms](#discovering-vc--angel-firms)
- [Sending email (Gmail)](#sending-email-gmail)
- [Campaigns](#campaigns)
- [Architecture](#architecture)
- [Development & tests](#development--tests)
- [Status & limitations](#status--limitations)

---

## Use cases

| Campaign | Input | Targets | Personalized on |
|---|---|---|---|
| **jobs** | company + role + location | recruiters / hiring managers | the role + your fit |
| **fundraising** | your domain + target firm domains | VCs / angel investors | their thesis / background |
| **b2b** | target company + your offer (`--role`) | decision-makers | their likely pain point |
| **pr** | publication domain + story angle (`--role`) | journalists / editors | their beat |
| **podcast** | show domain + your topic (`--role`) | show producers / hosts | the show + episode angles |
| **partnerships** | target company + proposal (`--role`) | BD / execs | mutual benefit |
| **recruiting** | candidate's company + open role (`--role`) | senior technical people | their profile fit |

The same engine extends to backlinks, creator collabs, user interviews, and
more — each is just another config entry.

---

## Install

Requires Python 3.10+.

```bash
git clone https://github.com/deka1105/ColdEmails.git
cd ColdEmails

python -m venv .venv && source .venv/bin/activate

pip install -e .            # core
pip install -e ".[ui]"     # + Streamlit web UI
pip install -e ".[dev]"    # + pytest for tests
```

This installs the `coldemails` command.

---

## Configuration (.env)

Copy `.env.example` to `.env` and fill what you need. `.env` is gitignored — keep
your keys there; the app and CLI load it automatically.

```ini
# Required to find people + emails
HUNTER_API_KEY=your_hunter_key

# Optional — only needed for the "Claude API key" draft mode.
# Leave blank to use the Claude Code CLI mode (default, no key).
ANTHROPIC_API_KEY=
# Optional model for the Claude Code CLI draft mode:
# COLDEMAILS_CLAUDE_CLI_MODEL=claude-haiku-4-5-20251001

# Optional — search enrichment / live firm discovery
SERPER_API_KEY=

# Required to actually send
SENDER_NAME=Your Name
SENDER_EMAIL=you@gmail.com
GMAIL_CREDENTIALS_FILE=credentials.json
GMAIL_TOKEN_FILE=token.json

COLDEMAILS_DB=coldemails.db
```

Minimum to get useful output: just `HUNTER_API_KEY` (drafting works via the
Claude Code CLI without any Anthropic key).

---

## Personalization / draft modes

Three ways to write the email body, selectable per run:

| Mode | Flag / UI | Needs | Notes |
|---|---|---|---|
| **Claude Code CLI** | `--draft claude_cli` (default) | local `claude` login | No API key; uses your Claude Code subscription |
| **Claude API** | `--draft claude` | `ANTHROPIC_API_KEY` | Uses the Anthropic SDK |
| **Template** | `--draft template` | nothing | Deterministic fill, no AI |

---

## Command line

```bash
coldemails campaigns                    # list campaigns
coldemails preview --campaign ... [...]  # dry-run: find + draft, never sends
coldemails send    --campaign ... [...]  # find, draft, and send via Gmail
coldemails status  [--campaign ...]      # counts by status
coldemails export  [--campaign ...] [--out file.csv]   # CSV of prospects+drafts
coldemails discover-firms [...]          # find VC/angel firm domains
```

Common options for `preview` / `send`:

```
--company     --role      --location    --domain
--firms "a,b" --firms-file path.txt      # target firm domains (fundraising)
--limit N                                # max prospects (default 10)
--draft {claude_cli,claude,template}     # copy renderer (default claude_cli)
```

Examples:

```bash
# Job outreach (dry-run) — drafts with Claude Code CLI, no API key
coldemails preview --campaign jobs --company Stripe --role "ML Engineer" --location Berlin

# Fundraising — target specific VC firms
coldemails preview --campaign fundraising --domain mystartup.com --location SF \
    --firms "a16z.com,sequoiacap.com"

# B2B sales — offer goes in --role
coldemails preview --campaign b2b --company Acme --role "observability tooling" --location NYC

# When happy, send (throttled) — test with your own address first
coldemails send --campaign jobs --company Stripe --role "ML Engineer"
```

`preview` is a **dry-run**: it finds people and prints the drafted emails but
never sends. Runs are idempotent — an already-sent prospect is skipped on re-run.

---

## Web UI

For non-technical use, a Streamlit app wraps the whole engine:

```bash
pip install -e ".[ui]"
streamlit run app.py         # opens http://localhost:8501
```

From the browser you: pick a campaign, fill inputs, choose a **Draft mode**,
**Preview** (dry-run), **Send** (two-click confirm), and view status.

Credentials are **not** entered in the UI — the sidebar shows a read-only ✅/—
status for each setting, all read from `.env`. Manage keys via `.env`, then
(re)start the app so it picks them up.

---

## Discovering VC / angel firms

Fundraising targets investors at their *firm* domains. If you don't know them,
discover by sector / stage / location from a built-in catalog (US / EU / Asia),
optionally expanded with live search (`SERPER_API_KEY`):

```bash
coldemails discover-firms --sector climate --location EU
coldemails discover-firms --sector ai --stage seed
coldemails discover-firms --sector fintech --search     # live search
```

It prints matching firms and a ready-to-paste comma list for `--firms`. In the
web UI, the fundraising flow has a **"Discover VC / angel firms"** panel that
auto-fills the target list from your selection.

---

## Sending email (Gmail)

1. In Google Cloud, create an **OAuth client (Desktop app)** for the Gmail API and
   download the client secret JSON.
2. Point `GMAIL_CREDENTIALS_FILE` at it and set `SENDER_NAME` / `SENDER_EMAIL`.
3. The first `send` opens a browser consent and caches a token at
   `GMAIL_TOKEN_FILE`.
4. Sends are throttled (30–45s apart) to protect deliverability. **Test by
   sending one email to yourself before any real campaign.**

---

## Campaigns

Campaigns are defined in `coldemails/campaigns.py` as config: which prospect
source, targeting filters, whether to enrich, the personalization prompt, and
throttle. Add a new use case by adding an entry — no engine changes. Fundraising
sets `needs_firms` so it requires `--firms`.

---

## Architecture

Swappable interfaces around a fixed engine:

- **ProspectSource** — criteria → people + emails. `HunterSource` (one domain)
  and `HunterFirmsSource` (many firm domains). *(`coldemails/sources.py`)*
- **Enricher** — research background. `WebEnricher` (fetch the org's pages) and
  `SearchEnricher` (Serper/DDG person search). *(`coldemails/enrich.py`)*
- **Personalizer** — `ClaudeCLIRenderer`, `ClaudeRenderer`, `TemplateRenderer`.
  *(`coldemails/personalize.py`)*
- **Sender** — `GmailSender` (throttled) and `ConsoleSender` (dry-run).
  *(`coldemails/gmail.py`)*
- **Store** — SQLite persistence, status tracking, dedup. *(`coldemails/store.py`)*
- **Engine** — orchestrates find → enrich → personalize → send + track.
  *(`coldemails/engine.py`)*

---

## Development & tests

```bash
pip install -e ".[dev]"
pytest
```

The suite stubs the network (Hunter, Serper, Clearbit) and the LLM, so it runs
offline with no credentials.

### Docker (web UI)

```bash
docker build -t coldemails .
docker run --rm -p 8501:8501 --env-file .env -v $(pwd)/data:/data coldemails
```

Inside a container the Claude Code CLI login isn't available — set
`ANTHROPIC_API_KEY` and use the "Claude API key" draft mode (or "template").

---

## Status & limitations

v1 ships the engine plus four campaigns (jobs, fundraising, b2b, pr), a CLI, a
Streamlit UI, VC firm discovery, and an offline test suite.

- Sending requires Gmail OAuth (one-time browser consent).
- The Claude Code CLI draft mode needs the `claude` binary installed and logged
  in on the machine running the app.
- The VC firm catalog tags are approximate (a starter seed, not investment
  research) — edit `firmfinder.py` freely.
- DuckDuckGo blocks automated search; use `SERPER_API_KEY` for reliable
  enrichment / firm discovery.
- Keep volume low and copy genuine — this is for legitimate 1:1 outreach.
