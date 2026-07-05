from unittest.mock import MagicMock

import coldemails.firmfinder as F


def test_domain_of_strips_www_and_path():
    assert F._domain_of("https://www.a16z.com/portfolio") == "a16z.com"
    assert F._domain_of("http://sequoiacap.com") == "sequoiacap.com"


def test_curated_filters_by_sector():
    domains = [f.domain for f in F.discover_curated(sector="climate")]
    assert "khoslaventures.com" in domains
    assert "lowercarbon.com" in domains
    # A pure-SaaS firm shouldn't show up for climate.
    assert "insightpartners.com" not in domains


def test_curated_limit():
    assert len(F.discover_curated(limit=3)) == 3


def test_curated_covers_eu_and_asia():
    regions = {f.location for f in F.CURATED}
    assert {"US", "EU", "Asia"} <= regions
    assert F.discover_curated(location="EU", limit=99)
    assert F.discover_curated(location="Asia", limit=99)
    # Region + sector filter narrows correctly.
    eu_fintech = [f.domain for f in F.discover_curated(sector="fintech", location="EU")]
    assert "balderton.com" in eu_fintech
    assert all(f.location == "EU" for f in F.discover_curated(location="EU", limit=99))


def test_search_returns_empty_without_key(monkeypatch):
    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    assert F.discover_search(sector="ai") == []


def test_search_extracts_and_skips_aggregators(monkeypatch):
    monkeypatch.setenv("SERPER_API_KEY", "fake")
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {
        "organic": [
            {"title": "Foo Ventures - Home", "link": "https://www.fooventures.com/"},
            {"title": "Crunchbase list", "link": "https://crunchbase.com/x"},  # skipped
            {"title": "Bar Capital | VC", "link": "https://barcapital.vc/team"},
            {"title": "dup", "link": "https://fooventures.com/about"},  # dup domain
        ]
    }
    monkeypatch.setattr(F.requests, "post", lambda *a, **k: resp)
    firms = F.discover_search(sector="ai")
    domains = [f.domain for f in firms]
    assert domains == ["fooventures.com", "barcapital.vc"]
    assert firms[0].name == "Foo Ventures"  # title cleaned at ' - '
    assert firms[0].source == "search"


def test_discover_dedupes_curated_and_search(monkeypatch):
    monkeypatch.setenv("SERPER_API_KEY", "fake")
    # Search returns one existing curated domain + one new -> only new is added.
    monkeypatch.setattr(
        F, "discover_search",
        lambda *a, **k: [F.Firm("A16Z", "a16z.com", source="search"),
                         F.Firm("New VC", "newvc.com", source="search")],
    )
    firms = F.discover(sector="ai", limit=50, use_search=True)
    domains = [f.domain for f in firms]
    assert domains.count("a16z.com") == 1
    assert "newvc.com" in domains
