from unittest.mock import MagicMock

import pytest

import coldemails.sources as S
from coldemails.enrich import (
    SearchEnricher,
    WebEnricher,
    _ddg_snippets,
    _html_to_text,
    get_enricher,
)
from coldemails.models import Criteria, Person


# --- sources ------------------------------------------------------------
def test_hunter_domain_search_parses(monkeypatch):
    payload = {
        "data": {
            "organization": "Acme",
            "emails": [
                {"first_name": "Jane", "last_name": "Doe", "value": "jane@acme.com", "position": "Recruiter"},
                {"value": "info@acme.com"},  # no name -> local part
            ],
        }
    }
    resp = MagicMock(status_code=200)
    resp.json.return_value = payload
    resp.raise_for_status.return_value = None
    monkeypatch.setattr(S.requests, "get", lambda *a, **k: resp)

    people = S._hunter_domain_search("key", "acme.com")
    assert [p.name for p in people] == ["Jane Doe", "info"]
    assert people[0].email == "jane@acme.com"
    assert people[0].company == "Acme"


def test_hunter_firms_requires_firm_domains(monkeypatch):
    monkeypatch.setenv("HUNTER_API_KEY", "dummy")
    src = S.HunterFirmsSource()
    with pytest.raises(ValueError, match="firm domains"):
        src.find(Criteria(domain="startup.com"))


def test_hunter_firms_iterates(monkeypatch):
    monkeypatch.setenv("HUNTER_API_KEY", "dummy")
    calls = []

    def fake(api_key, domain, limit=10, department=None, seniority=None):
        calls.append(domain)
        return [Person(name=f"P {domain}", email=f"p@{domain}", domain=domain)]

    monkeypatch.setattr(S, "_hunter_domain_search", fake)
    crit = Criteria(domain="startup.com")
    crit.extra["firm_domains"] = ["a16z.com", "sequoiacap.com"]
    people = S.HunterFirmsSource().find(crit, limit=10)
    assert calls == ["a16z.com", "sequoiacap.com"]
    assert len(people) == 2


def test_get_source_unknown():
    with pytest.raises(ValueError):
        S.get_source("nope")


# --- enrich -------------------------------------------------------------
def test_html_to_text_skips_script_style():
    html = "<style>x{}</style><h1>Acme</h1><script>bad()</script><p>Climate VC.</p>"
    assert _html_to_text(html) == "Acme Climate VC."


def test_ddg_snippets_extract():
    html = '<a class="result__snippet" href="y">Vinod invests in climate.</a>'
    assert _ddg_snippets(html) == "Vinod invests in climate."


def test_web_enricher_fallback_on_unreachable(monkeypatch):
    e = WebEnricher()
    monkeypatch.setattr(e, "_fetch_domain_text", lambda d: "")
    p = Person(name="Jo", title="Partner", company="Acme", domain="x.com")
    assert e.enrich(p).background == "Partner at Acme (x.com)"


def test_web_enricher_skips_when_background_present():
    e = WebEnricher()
    p = Person(name="Jo", background="already known")
    assert e.enrich(p).background == "already known"


def test_search_enricher_serper_parse(monkeypatch):
    e = SearchEnricher()
    e._provider = "serper"
    e._serper_key = "fake"
    e._client = None  # no Claude -> returns excerpt
    resp = MagicMock()
    resp.json.return_value = {
        "knowledgeGraph": {"description": "Founder of X."},
        "organic": [{"title": "Bio", "snippet": "Investor."}],
    }
    resp.raise_for_status.return_value = None
    monkeypatch.setattr(e._session, "post", lambda *a, **k: resp)
    p = Person(name="Marc", title="GP", company="a16z")
    bg = e.enrich(p).background
    assert "Founder of X." in bg and "Investor." in bg


def test_search_enricher_no_name_skips():
    e = SearchEnricher()
    p = Person(name="", title="GP")
    assert e.enrich(p).background is None


def test_get_enricher_none_and_unknown():
    assert get_enricher(None) is None
    with pytest.raises(ValueError):
        get_enricher("nope")
