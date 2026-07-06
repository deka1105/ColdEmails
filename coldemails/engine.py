"""Pipeline orchestration: find -> enrich -> personalize -> send + track.

The engine is campaign-agnostic. It reads a campaign config and drives the
swappable pieces (source, enricher, personalizer, sender), persisting every
step so runs are idempotent and dedup'd.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Callable, Optional

from . import company
from .campaigns import get_campaign
from .enrich import get_enricher
from .gmail import ConsoleSender, GmailSender, Sender
from .models import Criteria, Person
from .personalize import get_personalizer
from .sources import get_source
from .store import Store

Log = Callable[[str], None]


@dataclass
class RunResult:
    found: int = 0
    rendered: int = 0
    sent: int = 0
    skipped: int = 0
    failed: int = 0


class Engine:
    def __init__(self, store: Store, log: Optional[Log] = None):
        self.store = store
        self.log = log or (lambda m: None)

    def _build_criteria(self, campaign_name: str, campaign: dict, args: dict) -> Criteria:
        c = Criteria(
            company=args.get("company"),
            role=args.get("role"),
            location=args.get("location"),
            domain=args.get("domain"),
        )
        # Jobs campaign takes a company name; resolve to a domain for Hunter.
        if not c.domain and c.company:
            c.domain = company.resolve(c.company)
            self.log(f"Resolved company '{c.company}' -> domain '{c.domain}'")
        # Merge campaign targeting (department/seniority) into criteria.extra.
        c.extra.update(campaign.get("targeting", {}))
        c.extra["domain"] = c.domain

        # Campaigns that target a list of firm domains (e.g. fundraising).
        firms = args.get("firms") or []
        if firms:
            c.extra["firm_domains"] = firms

        missing = [f for f in campaign.get("requires", []) if not getattr(c, f, None)]
        if missing:
            raise ValueError(
                f"Campaign '{campaign_name}' requires: {', '.join(missing)}"
            )
        if campaign.get("needs_firms") and not firms:
            raise ValueError(
                f"Campaign '{campaign_name}' needs target firm domains. "
                "Pass --firms \"a16z.com,sequoiacap.com\" or --firms-file <path>."
            )
        return c

    def run(
        self,
        campaign_name: str,
        args: dict,
        limit: int = 10,
        send: bool = False,
        personalizer: str | None = None,
        attachments: list[str] | None = None,
    ) -> RunResult:
        """Run the pipeline. ``send=False`` is a dry-run (renders, never sends).

        ``personalizer`` overrides the campaign's default renderer — e.g. pass
        "template" to draft without an LLM / API key. ``attachments`` are local
        file paths attached to every email in the run (falls back to the
        campaign's optional ``attachments`` default).
        """
        campaign = get_campaign(campaign_name)
        criteria = self._build_criteria(campaign_name, campaign, args)

        attachments = list(attachments or campaign.get("attachments") or [])
        for path in attachments:
            if not os.path.isfile(path):
                raise ValueError(f"Attachment not found: {path}")

        source = get_source(campaign["source"])
        enricher = get_enricher(campaign.get("enrich"))
        personalizer = get_personalizer(personalizer or campaign["personalizer"])
        sender: Sender = GmailSender() if send else ConsoleSender()
        throttle = campaign.get("throttle_seconds", 30)

        result = RunResult()
        people = source.find(criteria, limit=limit)
        self.log(f"Found {len(people)} prospect(s).")

        for i, person in enumerate(people):
            key = person.dedup_key(campaign_name)
            if self.store.already_sent(key):
                self.log(f"Skip (already sent): {person.name} <{person.email}>")
                result.skipped += 1
                continue

            self.store.upsert_prospect(campaign_name, person)
            result.found += 1

            if not person.email:
                self.store.mark_skipped(key, "no email found")
                result.skipped += 1
                self.log(f"Skip (no email): {person.name}")
                continue

            if enricher:
                person = enricher.enrich(person)
                if person.background:
                    self.store.save_background(key, person.background)

            try:
                msg = personalizer.render(person, criteria, campaign)
                msg.attachments = attachments
                self.store.save_message(key, msg)
                result.rendered += 1
            except Exception as e:  # personalization failure shouldn't crash the run
                self.store.mark_failed(key, f"render: {e}")
                result.failed += 1
                self.log(f"Render failed for {person.name}: {e}")
                continue

            if not send:
                sender.send(person.email, msg)  # ConsoleSender prints the preview
                continue

            try:
                sender.send(person.email, msg)
                self.store.mark_sent(key)
                result.sent += 1
                self.log(f"Sent to {person.name} <{person.email}>")
            except Exception as e:
                self.store.mark_failed(key, f"send: {e}")
                result.failed += 1
                self.log(f"Send failed for {person.name}: {e}")

            # Pace real sends to protect deliverability; skip on the last one.
            if send and i < len(people) - 1:
                time.sleep(throttle)

        return result
