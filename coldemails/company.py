"""Resolve a company name to a web domain.

For the jobs campaign the user gives a company *name*; Hunter needs a *domain*.
Resolution order:

1. Input already looks like a domain -> normalize and return it.
2. Clearbit's free autocomplete API (no key needed) -> best-match domain.
3. Naive slug fallback (``Acme Inc`` -> ``acmeinc.com``).

Set ``COLDEMAILS_NO_NETWORK_RESOLVE=1`` to skip the network lookup (tests, CI).
"""

from __future__ import annotations

import re

import requests

from .config import env

CLEARBIT_AUTOCOMPLETE = "https://autocomplete.clearbit.com/v1/companies/suggest"
RESOLVE_TIMEOUT = 8

_cache: dict[str, str] = {}


def _slug(company: str) -> str:
    # Drop common legal suffixes so "Acme Inc." -> acme.com, not acmeinc.com.
    c = re.sub(
        r"\b(inc|incorporated|llc|ltd|limited|gmbh|corp|corporation|co|plc|sa|ag)\.?$",
        "",
        company.strip().lower(),
    ).strip()
    return re.sub(r"[^a-z0-9]", "", c) or re.sub(r"[^a-z0-9]", "", company.lower())


def _clearbit_lookup(company: str) -> str | None:
    """Best-match domain from Clearbit autocomplete; None on any failure."""
    try:
        resp = requests.get(
            CLEARBIT_AUTOCOMPLETE, params={"query": company}, timeout=RESOLVE_TIMEOUT
        )
        resp.raise_for_status()
        results = resp.json()
    except (requests.RequestException, ValueError):
        return None
    if not isinstance(results, list):
        return None

    target = company.strip().lower()
    # Prefer an exact name match; otherwise take the top suggestion.
    for r in results:
        if (r.get("name") or "").strip().lower() == target and r.get("domain"):
            return r["domain"]
    for r in results:
        if r.get("domain"):
            return r["domain"]
    return None


def resolve(company: str) -> str:
    """Best-effort company-name -> domain. Returns a bare domain like 'stripe.com'.

    If the input already looks like a domain, it is returned normalized.
    """
    c = company.strip().lower()
    if "." in c and " " not in c:
        return c.removeprefix("http://").removeprefix("https://").rstrip("/")

    if c in _cache:
        return _cache[c]

    domain = None
    if not env("COLDEMAILS_NO_NETWORK_RESOLVE"):
        domain = _clearbit_lookup(company)
    domain = domain or f"{_slug(company)}.com"
    _cache[c] = domain
    return domain
