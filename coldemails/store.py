"""SQLite persistence: prospects, rendered messages, send status, dedup.

The store makes runs idempotent. Every prospect gets a stable ``dedup_key``
(see :meth:`Person.dedup_key`); we never send to the same key twice.
"""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Optional

from .models import Message, Person

SCHEMA = """
CREATE TABLE IF NOT EXISTS prospects (
    dedup_key   TEXT PRIMARY KEY,
    campaign    TEXT NOT NULL,
    name        TEXT,
    email       TEXT,
    title       TEXT,
    company     TEXT,
    domain      TEXT,
    background  TEXT,
    raw         TEXT,
    subject     TEXT,
    body        TEXT,
    status      TEXT NOT NULL DEFAULT 'found',  -- found|previewed|sent|failed|skipped
    error       TEXT,
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_prospects_campaign ON prospects(campaign);
CREATE INDEX IF NOT EXISTS idx_prospects_status ON prospects(status);
"""


class Store:
    def __init__(self, path: str = "coldemails.db"):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # --- dedup -----------------------------------------------------------
    def already_seen(self, dedup_key: str) -> bool:
        cur = self.conn.execute(
            "SELECT 1 FROM prospects WHERE dedup_key = ?", (dedup_key,)
        )
        return cur.fetchone() is not None

    def already_sent(self, dedup_key: str) -> bool:
        cur = self.conn.execute(
            "SELECT 1 FROM prospects WHERE dedup_key = ? AND status = 'sent'",
            (dedup_key,),
        )
        return cur.fetchone() is not None

    # --- writes ----------------------------------------------------------
    def upsert_prospect(self, campaign: str, person: Person) -> str:
        """Insert a newly found prospect; ignore if the key already exists."""
        key = person.dedup_key(campaign)
        now = time.time()
        self.conn.execute(
            """
            INSERT INTO prospects
                (dedup_key, campaign, name, email, title, company, domain,
                 background, raw, status, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?, 'found', ?, ?)
            ON CONFLICT(dedup_key) DO NOTHING
            """,
            (
                key, campaign, person.name, person.email, person.title,
                person.company, person.domain, person.background,
                json.dumps(person.raw), now, now,
            ),
        )
        self.conn.commit()
        return key

    def save_background(self, dedup_key: str, background: str) -> None:
        self.conn.execute(
            "UPDATE prospects SET background = ?, updated_at = ? WHERE dedup_key = ?",
            (background, time.time(), dedup_key),
        )
        self.conn.commit()

    def save_message(self, dedup_key: str, msg: Message) -> None:
        self.conn.execute(
            """UPDATE prospects
               SET subject = ?, body = ?, status = 'previewed', updated_at = ?
               WHERE dedup_key = ?""",
            (msg.subject, msg.body, time.time(), dedup_key),
        )
        self.conn.commit()

    def mark_sent(self, dedup_key: str) -> None:
        self._set_status(dedup_key, "sent")

    def mark_failed(self, dedup_key: str, error: str) -> None:
        self._set_status(dedup_key, "failed", error)

    def mark_skipped(self, dedup_key: str, reason: str) -> None:
        self._set_status(dedup_key, "skipped", reason)

    def _set_status(self, dedup_key: str, status: str, error: Optional[str] = None) -> None:
        self.conn.execute(
            "UPDATE prospects SET status = ?, error = ?, updated_at = ? WHERE dedup_key = ?",
            (status, error, time.time(), dedup_key),
        )
        self.conn.commit()

    # --- reads -----------------------------------------------------------
    def counts_by_status(self, campaign: Optional[str] = None) -> dict[str, int]:
        if campaign:
            rows = self.conn.execute(
                "SELECT status, COUNT(*) c FROM prospects WHERE campaign = ? GROUP BY status",
                (campaign,),
            )
        else:
            rows = self.conn.execute(
                "SELECT status, COUNT(*) c FROM prospects GROUP BY status"
            )
        return {r["status"]: r["c"] for r in rows}

    def list_prospects(self, campaign: Optional[str] = None) -> list[sqlite3.Row]:
        if campaign:
            rows = self.conn.execute(
                "SELECT * FROM prospects WHERE campaign = ? ORDER BY created_at",
                (campaign,),
            )
        else:
            rows = self.conn.execute("SELECT * FROM prospects ORDER BY created_at")
        return list(rows)
