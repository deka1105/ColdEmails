"""Command-line entry point.

Commands:
  preview  — dry-run: find people, render emails, print them (never sends)
  send     — run the pipeline and actually send via Gmail (throttled)
  status   — show counts by status for a campaign
  campaigns— list available campaigns
"""

from __future__ import annotations

import argparse
import sys

from .campaigns import CAMPAIGNS
from .config import env
from .engine import Engine
from .store import Store


def _add_criteria_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--campaign", required=True, help="campaign name (e.g. jobs)")
    p.add_argument("--company")
    p.add_argument("--role")
    p.add_argument("--location")
    p.add_argument("--domain")
    p.add_argument("--firms", help="comma-separated target firm domains (e.g. fundraising)")
    p.add_argument("--firms-file", help="file with one firm domain per line")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument(
        "--attach", action="append", default=[], metavar="FILE",
        help="attach a file to every email (repeatable, e.g. --attach resume.pdf)",
    )
    p.add_argument(
        "--draft",
        choices=["claude_cli", "claude", "template"],
        default="claude_cli",
        help="copy renderer: claude_cli (local Claude Code login, no API key, "
        "default), claude (ANTHROPIC_API_KEY), or template (no AI)",
    )


def _firms(a: argparse.Namespace) -> list[str]:
    firms: list[str] = []
    if a.firms:
        firms += [d.strip() for d in a.firms.split(",") if d.strip()]
    if a.firms_file:
        with open(a.firms_file) as f:
            firms += [line.strip() for line in f if line.strip() and not line.startswith("#")]
    return firms


def _criteria(a: argparse.Namespace) -> dict:
    return {
        "company": a.company,
        "role": a.role,
        "location": a.location,
        "domain": a.domain,
        "firms": _firms(a),
    }


def _run(a: argparse.Namespace, send: bool) -> int:
    with Store(env("COLDEMAILS_DB", "coldemails.db")) as store:
        engine = Engine(store, log=lambda m: print(m, file=sys.stderr))
        res = engine.run(
            a.campaign, _criteria(a), limit=a.limit, send=send,
            personalizer=a.draft, attachments=a.attach,
        )
    verb = "SENT" if send else "PREVIEW"
    print(
        f"\n[{verb}] found={res.found} rendered={res.rendered} "
        f"sent={res.sent} skipped={res.skipped} failed={res.failed}"
    )
    return 0


def _status(a: argparse.Namespace) -> int:
    with Store(env("COLDEMAILS_DB", "coldemails.db")) as store:
        counts = store.counts_by_status(a.campaign)
    if not counts:
        print("No prospects recorded yet.")
        return 0
    for status, n in sorted(counts.items()):
        print(f"{status:>10}: {n}")
    return 0


def _campaigns(_a: argparse.Namespace) -> int:
    for name, cfg in CAMPAIGNS.items():
        print(f"{name:>12}  requires={cfg.get('requires')}  source={cfg['source']}")
    return 0


def _export(a: argparse.Namespace) -> int:
    import csv

    with Store(env("COLDEMAILS_DB", "coldemails.db")) as store:
        rows = store.list_prospects(a.campaign)
    if not rows:
        print("No prospects recorded yet.")
        return 0
    cols = [
        "campaign", "name", "email", "title", "company", "domain",
        "status", "subject", "body", "background", "error",
    ]
    out = open(a.out, "w", newline="") if a.out else sys.stdout
    try:
        w = csv.writer(out)
        w.writerow(cols)
        for r in rows:
            w.writerow([r[c] for c in cols])
    finally:
        if a.out:
            out.close()
            print(f"Wrote {len(rows)} row(s) to {a.out}", file=sys.stderr)
    return 0


def _test_send(a: argparse.Namespace) -> int:
    """Send one test email (default: to yourself) to verify Gmail OAuth end-to-end."""
    from .gmail import GmailSender
    from .models import Message

    to = a.to or env("SENDER_EMAIL", required=True)
    msg = Message(
        subject="ColdEmails test — Gmail is configured",
        body=(
            "This is a test email from ColdEmails.\n\n"
            "If you're reading it, Gmail OAuth, sending, and MIME assembly "
            "all work. You're ready for real campaigns.\n"
        ),
        attachments=a.attach or [],
    )
    print(f"Sending test email to {to} ...", file=sys.stderr)
    GmailSender().send(to, msg)
    print(f"Sent. Check {to}'s inbox.")
    return 0


def _discover_firms(a: argparse.Namespace) -> int:
    from .firmfinder import discover

    firms = discover(
        sector=a.sector, stage=a.stage, location=a.location,
        limit=a.limit, use_search=a.search,
    )
    if not firms:
        print("No firms matched. Try a broader --sector or add --search.")
        return 0
    for f in firms:
        tags = ",".join(f.focus)
        print(f"{f.domain:<28} {f.name}  [{tags}] ({f.source})")
    print("\nComma-separated domains for --firms:")
    print(",".join(f.domain for f in firms))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="coldemails", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_prev = sub.add_parser("preview", help="dry-run: render emails without sending")
    _add_criteria_args(p_prev)
    p_prev.set_defaults(func=lambda a: _run(a, send=False))

    p_send = sub.add_parser("send", help="find, personalize, and send via Gmail")
    _add_criteria_args(p_send)
    p_send.set_defaults(func=lambda a: _run(a, send=True))

    p_stat = sub.add_parser("status", help="show counts by status")
    p_stat.add_argument("--campaign")
    p_stat.set_defaults(func=_status)

    p_camp = sub.add_parser("campaigns", help="list available campaigns")
    p_camp.set_defaults(func=_campaigns)

    p_exp = sub.add_parser("export", help="export prospects + drafts as CSV")
    p_exp.add_argument("--campaign")
    p_exp.add_argument("--out", help="output file (default: stdout)")
    p_exp.set_defaults(func=_export)

    p_disc = sub.add_parser("discover-firms", help="find VC/angel firm domains")
    p_disc.add_argument("--sector", help="e.g. climate, fintech, ai")
    p_disc.add_argument("--stage", help="e.g. seed, early, growth")
    p_disc.add_argument("--location")
    p_disc.add_argument("--limit", type=int, default=20)
    p_disc.add_argument("--search", action="store_true", help="also search live (needs SERPER_API_KEY)")
    p_disc.set_defaults(func=_discover_firms)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
