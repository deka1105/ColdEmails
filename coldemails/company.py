"""Resolve a company name to a web domain.

For the jobs campaign the user gives a company *name*; Hunter needs a *domain*.
v1 uses Hunter's account-free ``domain-search`` heuristics via a light guess,
falling back to a naive slug. This is intentionally simple and pluggable — a
real resolver (Clearbit autocomplete, search API) can replace ``resolve``.
"""

from __future__ import annotations

import re


def resolve(company: str) -> str:
    """Best-effort company-name -> domain. Returns a bare domain like 'stripe.com'.

    If the input already looks like a domain, it is returned normalized.
    """
    c = company.strip().lower()
    if "." in c and " " not in c:
        return c.removeprefix("http://").removeprefix("https://").rstrip("/")
    slug = re.sub(r"[^a-z0-9]", "", c)
    return f"{slug}.com"
