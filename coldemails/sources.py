"""Prospect data sources: turn search criteria into people with emails.

Kept as a single flat module (interface + implementations + registry) so new
providers slot in without touching the engine — just add a class and register
it in ``_SOURCES``.
"""

from __future__ import annotations

import csv
import os
import re
import unicodedata
from abc import ABC, abstractmethod

import requests

from . import company as company_resolver
from . import emailcheck
from .config import env
from .models import Criteria, Person

HUNTER_BASE = "https://api.hunter.io/v2"

# Common corporate email patterns, ranked roughly by real-world frequency.
# Tokens: {first} {last} {f}=first initial {l}=last initial. Order matters —
# the first pattern is the primary guess, the rest are alternates for export.
_PATTERNS = [
    "{first}.{last}",
    "{first}",
    "{f}{last}",
    "{first}{last}",
    "{first}_{last}",
    "{f}.{last}",
    "{last}",
    "{last}{f}",
    "{first}{l}",
]


class ProspectSource(ABC):
    """A provider that finds prospects for given criteria.

    Implementations must not raise on empty results — return ``[]`` instead.
    """

    name: str = "base"

    @abstractmethod
    def find(self, criteria: Criteria, limit: int = 10) -> list[Person]:
        ...


class HunterSource(ProspectSource):
    """Hunter.io Domain Search: domain -> people + verified emails.

    Requires ``HUNTER_API_KEY``. Optionally filters by department/seniority so
    a campaign can target e.g. recruiters (HR) or executives (investors reach
    out to founders, so we target executive seniority on the startup domain).
    """

    name = "hunter"

    def __init__(self) -> None:
        self.api_key = env("HUNTER_API_KEY", required=True)

    def find(self, criteria: Criteria, limit: int = 10) -> list[Person]:
        domain = criteria.domain or criteria.extra.get("domain")
        if not domain:
            raise ValueError("HunterSource requires a resolved 'domain' in criteria")
        return _hunter_domain_search(
            self.api_key,
            domain,
            limit=limit,
            department=criteria.extra.get("department"),
            seniority=criteria.extra.get("seniority"),
        )


class HunterFirmsSource(ProspectSource):
    """Find people across a *list* of firm domains — one Hunter search each.

    This is what fundraising needs: investors work at their VC/angel *firm*
    domains, not at the startup's domain. The startup domain (``criteria.domain``)
    is kept only as email context; targeting runs over ``extra['firm_domains']``.
    """

    name = "hunter_firms"

    def __init__(self) -> None:
        self.api_key = env("HUNTER_API_KEY", required=True)

    def find(self, criteria: Criteria, limit: int = 10) -> list[Person]:
        firms = criteria.extra.get("firm_domains") or []
        if not firms:
            raise ValueError(
                "hunter_firms requires target firm domains. Pass --firms "
                "\"a16z.com,sequoiacap.com\" or --firms-file <path>."
            )
        # Spread the overall limit across firms (at least 1 each).
        per_firm = max(1, limit // len(firms))
        people: list[Person] = []
        for firm in firms:
            people.extend(
                _hunter_domain_search(
                    self.api_key,
                    firm,
                    limit=per_firm,
                    department=criteria.extra.get("department"),
                    seniority=criteria.extra.get("seniority"),
                )
            )
            if len(people) >= limit:
                break
        return people[:limit]


def _hunter_domain_search(
    api_key: str,
    domain: str,
    limit: int = 10,
    department: str | None = None,
    seniority: str | None = None,
) -> list[Person]:
    """One Hunter domain-search call -> people. Never raises on empty results."""
    params: dict[str, object] = {"domain": domain, "api_key": api_key, "limit": limit}
    if department:
        params["department"] = department
    if seniority:
        params["seniority"] = seniority

    resp = requests.get(f"{HUNTER_BASE}/domain-search", params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json().get("data", {})
    org = data.get("organization")

    people: list[Person] = []
    for e in data.get("emails", []):
        name = " ".join(p for p in [e.get("first_name"), e.get("last_name")] if p).strip()
        people.append(
            Person(
                name=name or (e.get("value") or "").split("@")[0],
                email=e.get("value"),
                title=e.get("position"),
                company=org,
                domain=domain,
                raw=e,
            )
        )
    return people


def _name_parts(name: str) -> dict[str, str]:
    """Split a full name into the tokens the patterns use. Lowercased, ASCII-ish."""
    # Fold accents to ASCII (José -> jose) before dropping non-letters.
    folded = unicodedata.normalize("NFKD", (name or "").strip().lower())
    folded = folded.encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^a-z\s]", "", folded)
    bits = [b for b in cleaned.split() if b]
    first = bits[0] if bits else ""
    last = bits[-1] if len(bits) > 1 else ""
    return {
        "first": first,
        "last": last,
        "f": first[:1],
        "l": last[:1],
    }


def _render_pattern(pattern: str, parts: dict[str, str]) -> str | None:
    """Fill a pattern like ``{first}.{last}`` -> ``jane.doe``.

    Returns ``None`` if the pattern needs a token the name doesn't provide
    (e.g. ``{last}`` for a single-word name), so we never emit ``jane.@dom``.
    """
    needed = re.findall(r"\{(\w+)\}", pattern)
    if any(not parts.get(tok) for tok in needed):
        return None
    local = pattern.format_map(parts)
    # Collapse stray separators from any empty edge cases.
    local = re.sub(r"[._]{2,}", ".", local).strip("._")
    return local or None


def guess_emails(name: str, domain: str, pattern: str | None = None) -> list[str]:
    """Candidate emails for ``name`` at ``domain``, best guess first.

    If ``pattern`` (a Hunter-style template such as ``{first}.{last}``) is given,
    that pattern leads; the standard ranked patterns follow as alternates. This
    is the cheap path: learn one domain's pattern from a single Hunter call, then
    infer everyone else there for free.
    """
    parts = _name_parts(name)
    if not parts["first"]:
        return []
    ordered: list[str] = []
    seen: set[str] = set()
    templates = ([pattern] if pattern else []) + _PATTERNS
    for tmpl in templates:
        local = _render_pattern(tmpl, parts)
        if not local:
            continue
        email = f"{local}@{domain}".lower()
        if email not in seen:
            seen.add(email)
            ordered.append(email)
    return ordered


class PatternSource(ProspectSource):
    """Infer emails from names + a domain — no Hunter credit, no API key.

    Input (via ``criteria.extra``): ``names`` (list of full names) and a resolved
    ``domain``. Optionally ``email_pattern`` (a ``{first}.{last}``-style hint,
    e.g. learned from one Hunter lookup) makes the primary guess exact.

    Each returned Person gets the best-guess email plus every alternate candidate
    in ``raw['email_candidates']`` and a rough confidence in ``raw['confidence']``.
    A domain with no MX records (when DNS is reachable) drops the guess to no
    email, so the engine skips it instead of drafting to a dead address.
    """

    name = "pattern"

    def find(self, criteria: Criteria, limit: int = 10) -> list[Person]:
        domain = criteria.domain or criteria.extra.get("domain")
        if not domain:
            raise ValueError("PatternSource requires a resolved 'domain' in criteria")
        names = criteria.extra.get("names") or []
        if not names:
            raise ValueError(
                "The 'pattern' source needs prospect names. Pass "
                '--names "Jane Doe,John Smith" or --names-file <path>.'
            )
        pattern = criteria.extra.get("email_pattern")
        domain_has_mx = emailcheck.has_mx(domain)  # None if unknown/offline

        people: list[Person] = []
        for raw_name in names[:limit]:
            name = raw_name.strip()
            if not name:
                continue
            candidates = guess_emails(name, domain, pattern)
            best = candidates[0] if candidates else None
            report = emailcheck.validate(best, check_mx=False) if best else {}
            # Domain-level MX result applies to every guessed address here.
            if best and domain_has_mx is False:
                best = None  # dead domain — let the engine skip it.
            people.append(
                Person(
                    name=name,
                    email=best,
                    company=criteria.company,
                    domain=domain,
                    raw={
                        "source": "pattern",
                        "email_candidates": candidates,
                        "email_pattern": pattern or (_PATTERNS[0] if candidates else None),
                        "mx": domain_has_mx,
                        "confidence": 0 if best is None else report.get("confidence", 50),
                    },
                )
            )
        return people[:limit]


_SOURCES: dict[str, type[ProspectSource]] = {
    "hunter": HunterSource,
    "hunter_firms": HunterFirmsSource,
    "pattern": PatternSource,
}


def get_source(name: str) -> ProspectSource:
    if name not in _SOURCES:
        raise ValueError(
            f"Unknown prospect source '{name}'. Available: {', '.join(_SOURCES)}"
        )
    return _SOURCES[name]()
