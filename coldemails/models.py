"""Core data types shared across the engine."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Person:
    """A discovered prospect and (optionally) their email."""

    name: str
    email: Optional[str] = None
    title: Optional[str] = None
    company: Optional[str] = None
    domain: Optional[str] = None
    # Freeform provider payload + background gathered by an Enricher.
    raw: dict[str, Any] = field(default_factory=dict)
    background: Optional[str] = None

    @property
    def first_name(self) -> str:
        return (self.name or "").strip().split(" ")[0] if self.name else ""

    def dedup_key(self, campaign: str) -> str:
        """Stable key so re-runs never email the same person twice."""
        basis = (self.email or f"{self.name}|{self.domain}").strip().lower()
        return hashlib.sha256(f"{campaign}:{basis}".encode()).hexdigest()


@dataclass
class Message:
    """A rendered email ready to send."""

    subject: str
    body: str


@dataclass
class Criteria:
    """Campaign input. Only the fields a given campaign needs are populated."""

    company: Optional[str] = None
    role: Optional[str] = None
    location: Optional[str] = None
    domain: Optional[str] = None
    extra: dict[str, Any] = field(default_factory=dict)
