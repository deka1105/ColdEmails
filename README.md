# ColdEmails

Multi-purpose outreach automation. Give it search criteria; it finds the right
people, discovers their emails, researches their background, writes a
personalized message with AI, and sends it via Gmail — paced, de-duplicated,
and tracked.

## How it works

    input criteria → find people → find email → research → personalize → send + track

One engine, many use cases. Each use case is a "campaign" plugin/config that
only changes *who you target* and *what you personalize on*.

## Use cases

- **Job outreach** — company + role + location → hiring managers / recruiters
- **Fundraising** — domain + location → VCs / angel investors (message tailored
  to each investor's background & thesis)
- ...and the same engine extends to B2B sales, PR/media, podcast booking,
  partnerships, backlinks, creator collabs, recruiting, and user interviews.

## Architecture

- **ProspectSource** — find people + emails (Hunter.io; pluggable)
- **Enricher** — research background for personalization
- **Personalizer** — template or Claude-generated copy
- **Sender** — Gmail API delivery, throttled
- **Store** — SQLite tracking + dedup (never email anyone twice)

## Web UI (no CLI needed)

A Streamlit app wraps the whole engine for non-technical use:

    pip install -e ".[ui]"
    streamlit run app.py

From the browser you can enter API keys, pick a campaign, fill inputs, **Preview**
(dry-run) the drafted emails, **Send** via Gmail (with a confirm step), and view
status. Pick a **Draft mode**: *Claude Code CLI* (uses your local `claude` login
— no API key needed), *Claude API key*, or *Plain template* (no AI at all).

For fundraising, a **"Discover VC / angel firms"** panel finds firm domains by
sector/stage/location (curated catalog, plus optional live search) so you don't
need to know them — pick from the results and they auto-fill the target list.
The same is available on the CLI:

    coldemails discover-firms --sector climate --stage seed
    coldemails discover-firms --sector ai --search   # live search (needs SERPER_API_KEY)

## Command line

Commands:

    coldemails campaigns                 # list available campaigns
    coldemails preview  --campaign ...   # dry-run: find + render, never sends
    coldemails send     --campaign ...   # find, personalize, send via Gmail
    coldemails status   --campaign ...   # counts by status

Examples:

    coldemails preview --campaign jobs --company Stripe --role "ML Engineer" --location Berlin
    coldemails preview --campaign fundraising --domain mystartup.com --location SF \
        --firms "a16z.com,sequoiacap.com"

## Development

    pip install -e ".[dev]"
    pytest                # runs the offline test suite (no API keys needed)

Tests stub the network (Hunter, Serper) and the LLM, so they run without
credentials.

## Live run checklist

The offline suite proves the logic; the following need real credentials in
`.env` (see `.env.example`) and are verified by running against live services:

1. `HUNTER_API_KEY` — real prospect/email discovery
2. `ANTHROPIC_API_KEY` — Claude-written copy (`ClaudeRenderer`)
3. `SERPER_API_KEY` — reliable search enrichment (DuckDuckGo blocks bots)
4. Gmail OAuth — put the OAuth client secret at `GMAIL_CREDENTIALS_FILE`; the
   first `send` opens a browser consent and caches a token. Test by sending one
   email to yourself before any real campaign.

## Status

Early development. v1 ships the engine plus four campaigns (jobs, fundraising,
b2b, pr), all covered by an offline test suite. Live integrations require the
credentials above.
