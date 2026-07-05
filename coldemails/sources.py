"""Prospect data sources: turn search criteria into people with emails.

Kept as a single flat module (interface + implementations + registry) so new
providers slot in without touching the engine — just add a class and register
it in ``_SOURCES``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import requests

from .config import env
from .models import Criteria, Person

HUNTER_BASE = "https://api.hunter.io/v2"


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


_SOURCES: dict[str, type[ProspectSource]] = {
    "hunter": HunterSource,
    "hunter_firms": HunterFirmsSource,
}


def get_source(name: str) -> ProspectSource:
    if name not in _SOURCES:
        raise ValueError(
            f"Unknown prospect source '{name}'. Available: {', '.join(_SOURCES)}"
        )
    return _SOURCES[name]()
