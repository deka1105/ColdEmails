"""Discover VC / angel firm domains so users don't have to know them.

Two sources, combined and de-duplicated by domain:
- A curated starter catalog of well-known firms tagged by focus/stage. Reliable,
  offline, editable. Not exhaustive — a seed to get going.
- Optional live search (Serper) that extracts firm domains from result links,
  skipping aggregators (Crunchbase, LinkedIn, news, etc.).

The result is a list of ``Firm`` whose ``.domain`` feeds the ``hunter_firms``
prospect source used by the fundraising campaign.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse

import requests

from .config import env

SERPER_URL = "https://google.serper.dev/search"
FETCH_TIMEOUT = 12

# Domains that show up in searches but aren't a firm's own site.
_SKIP_DOMAINS = {
    "crunchbase.com", "linkedin.com", "twitter.com", "x.com", "wikipedia.org",
    "medium.com", "forbes.com", "techcrunch.com", "reddit.com", "youtube.com",
    "facebook.com", "github.com", "cbinsights.com", "pitchbook.com",
    "signal.nfx.com", "nfx.com", "failory.com", "visible.vc", "openvc.app",
    "google.com", "bing.com",
}


@dataclass
class Firm:
    name: str
    domain: str
    focus: list[str] = field(default_factory=list)
    stage: str = ""
    location: str = ""
    source: str = "curated"


# Starter catalog — extend freely. Tags are approximate; treat as a seed.
CURATED: list[Firm] = [
    Firm("Andreessen Horowitz", "a16z.com", ["generalist", "ai", "crypto", "consumer"], "multi", "US"),
    Firm("Sequoia Capital", "sequoiacap.com", ["generalist", "saas", "consumer"], "multi", "US"),
    Firm("Greylock", "greylock.com", ["generalist", "enterprise", "ai"], "early", "US"),
    Firm("Accel", "accel.com", ["generalist", "saas", "fintech"], "multi", "US"),
    Firm("Benchmark", "benchmark.com", ["generalist", "consumer", "enterprise"], "early", "US"),
    Firm("Kleiner Perkins", "kpcb.com", ["generalist", "healthcare", "climate"], "multi", "US"),
    Firm("Lightspeed", "lsvp.com", ["generalist", "enterprise", "consumer"], "multi", "US"),
    Firm("First Round", "firstround.com", ["generalist", "saas"], "seed", "US"),
    Firm("Founders Fund", "foundersfund.com", ["deeptech", "generalist"], "multi", "US"),
    Firm("Index Ventures", "indexventures.com", ["generalist", "fintech", "saas"], "multi", "EU"),
    Firm("Bessemer Venture Partners", "bvp.com", ["saas", "cloud", "healthcare"], "multi", "US"),
    Firm("General Catalyst", "generalcatalyst.com", ["generalist", "healthcare", "fintech"], "multi", "US"),
    Firm("Khosla Ventures", "khoslaventures.com", ["deeptech", "climate", "ai", "biotech"], "early", "US"),
    Firm("NEA", "nea.com", ["generalist", "healthcare", "enterprise"], "multi", "US"),
    Firm("Insight Partners", "insightpartners.com", ["saas", "growth"], "growth", "US"),
    Firm("Battery Ventures", "battery.com", ["enterprise", "saas"], "multi", "US"),
    Firm("Redpoint", "redpoint.com", ["saas", "fintech", "consumer"], "early", "US"),
    Firm("Initialized Capital", "initialized.com", ["generalist", "consumer"], "seed", "US"),
    Firm("Craft Ventures", "craftventures.com", ["saas", "marketplace"], "early", "US"),
    Firm("Uncork Capital", "uncorkcapital.com", ["generalist", "saas"], "seed", "US"),
    Firm("Lowercarbon Capital", "lowercarbon.com", ["climate", "deeptech"], "multi", "US"),
    Firm("Y Combinator", "ycombinator.com", ["generalist", "seed"], "seed", "US"),
    # --- Europe ---
    Firm("Atomico", "atomico.com", ["generalist", "growth", "ai"], "growth", "EU"),
    Firm("Balderton Capital", "balderton.com", ["generalist", "saas", "fintech"], "early", "EU"),
    Firm("Northzone", "northzone.com", ["generalist", "consumer", "fintech"], "multi", "EU"),
    Firm("Creandum", "creandum.com", ["generalist", "saas", "consumer"], "early", "EU"),
    Firm("Seedcamp", "seedcamp.com", ["generalist", "fintech", "saas"], "seed", "EU"),
    Firm("Earlybird Venture Capital", "earlybird.com", ["generalist", "deeptech"], "early", "EU"),
    Firm("HV Capital", "hvcapital.com", ["generalist", "consumer"], "multi", "EU"),
    Firm("Lakestar", "lakestar.com", ["generalist", "fintech", "deeptech"], "multi", "EU"),
    Firm("Cherry Ventures", "cherry.vc", ["generalist", "saas"], "seed", "EU"),
    Firm("LocalGlobe", "localglobe.vc", ["generalist", "fintech"], "seed", "EU"),
    Firm("Speedinvest", "speedinvest.com", ["generalist", "fintech", "saas"], "seed", "EU"),
    Firm("Partech", "partech.com", ["generalist", "saas", "fintech"], "multi", "EU"),
    Firm("Sofinnova Partners", "sofinnovapartners.com", ["biotech", "healthcare", "climate"], "multi", "EU"),
    # --- Asia ---
    Firm("Peak XV Partners", "peakxv.com", ["generalist", "saas", "consumer"], "multi", "Asia"),
    Firm("GGV Capital", "ggvc.com", ["generalist", "consumer", "enterprise"], "multi", "Asia"),
    Firm("Qiming Venture Partners", "qimingvc.com", ["generalist", "healthcare", "deeptech"], "multi", "Asia"),
    Firm("HongShan", "hongshan.com", ["generalist", "consumer", "ai"], "multi", "Asia"),
    Firm("ZhenFund", "zhenfund.com", ["generalist", "consumer"], "seed", "Asia"),
    Firm("Shunwei Capital", "shunwei.com", ["generalist", "deeptech", "ai"], "early", "Asia"),
    Firm("Vertex Ventures", "vertexventures.com", ["generalist", "saas", "fintech"], "early", "Asia"),
    Firm("Golden Gate Ventures", "goldengate.vc", ["generalist", "consumer"], "early", "Asia"),
    Firm("Jungle Ventures", "jungle-ventures.com", ["generalist", "saas"], "early", "Asia"),
    Firm("East Ventures", "east.vc", ["generalist", "consumer"], "seed", "Asia"),
    Firm("Gobi Partners", "gobivc.com", ["generalist", "consumer"], "early", "Asia"),
    Firm("JAFCO", "jafco.co.jp", ["generalist", "deeptech"], "multi", "Asia"),
    Firm("500 Global", "500.co", ["generalist", "seed"], "seed", "Asia"),
]


def _matches(firm: Firm, sector: str | None, stage: str | None, location: str | None) -> bool:
    if sector:
        s = sector.lower()
        if not any(s in tag for tag in firm.focus) and s not in firm.name.lower():
            return False
    if stage and stage.lower() not in firm.stage.lower() and firm.stage != "multi":
        return False
    if location and location.lower() not in firm.location.lower():
        return False
    return True


def discover_curated(
    sector: str | None = None,
    stage: str | None = None,
    location: str | None = None,
    limit: int = 20,
) -> list[Firm]:
    hits = [f for f in CURATED if _matches(f, sector, stage, location)]
    return hits[:limit]


def _domain_of(url: str) -> str:
    netloc = urlparse(url).netloc.lower()
    return netloc[4:] if netloc.startswith("www.") else netloc


def discover_search(
    sector: str | None = None,
    stage: str | None = None,
    location: str | None = None,
    limit: int = 20,
) -> list[Firm]:
    """Find firm domains via Serper. Returns [] if no key or on error."""
    key = env("SERPER_API_KEY")
    if not key:
        return []
    query = " ".join(
        p for p in ["top venture capital firms", sector, stage, location] if p
    )
    try:
        resp = requests.post(
            SERPER_URL,
            headers={"X-API-KEY": key, "Content-Type": "application/json"},
            json={"q": query, "num": 10},
            timeout=FETCH_TIMEOUT,
        )
        resp.raise_for_status()
        organic = resp.json().get("organic", [])
    except requests.RequestException:
        return []

    seen: set[str] = set()
    firms: list[Firm] = []
    for r in organic:
        domain = _domain_of(r.get("link", ""))
        if not domain or domain in _SKIP_DOMAINS or domain in seen:
            continue
        seen.add(domain)
        firms.append(
            Firm(
                name=r.get("title", domain).split(" - ")[0].split(" | ")[0].strip(),
                domain=domain,
                focus=[sector] if sector else [],
                location=location or "",
                source="search",
            )
        )
        if len(firms) >= limit:
            break
    return firms


def discover(
    sector: str | None = None,
    stage: str | None = None,
    location: str | None = None,
    limit: int = 20,
    use_search: bool = False,
) -> list[Firm]:
    """Curated matches first, then optional search expansion, de-duped by domain."""
    firms = discover_curated(sector, stage, location, limit=limit)
    seen = {f.domain for f in firms}
    if use_search:
        for f in discover_search(sector, stage, location, limit=limit):
            if f.domain not in seen:
                seen.add(f.domain)
                firms.append(f)
    return firms[:limit]
