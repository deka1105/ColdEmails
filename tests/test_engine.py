import pytest

import coldemails.engine as engine_mod
import coldemails.personalize as P
import coldemails.sources as S
from coldemails.campaigns import get_campaign
from coldemails.engine import Engine
from coldemails.models import Person


@pytest.fixture
def stub_jobs(monkeypatch):
    """Stub Hunter + Claude so the jobs pipeline runs offline."""
    monkeypatch.setenv("HUNTER_API_KEY", "dummy")
    monkeypatch.setattr(
        S,
        "_hunter_domain_search",
        lambda *a, **k: [
            Person(name="Jane", email="jane@acme.com", title="Recruiter",
                   company="Acme", domain="acme.com"),
            Person(name="No Email", title="HR", company="Acme", domain="acme.com"),
        ],
    )
    monkeypatch.setitem(P._RENDERERS, "claude", P.TemplateRenderer)


def test_jobs_dry_run(store, stub_jobs):
    res = Engine(store).run(
        "jobs", {"company": "Acme", "role": "ML Engineer", "location": "NYC"}, send=False
    )
    assert res.found == 2
    assert res.rendered == 1      # one had an email
    assert res.skipped == 1       # one had no email
    assert res.sent == 0


def test_company_name_resolved_to_domain(store, stub_jobs):
    logs = []
    Engine(store, log=logs.append).run("jobs", {"company": "Stripe", "role": "x"}, send=False)
    assert any("stripe.com" in m for m in logs)


def test_dedup_skips_already_sent(store, stub_jobs):
    key = Person(name="Jane", email="jane@acme.com", domain="acme.com").dedup_key("jobs")
    store.upsert_prospect("jobs", Person(name="Jane", email="jane@acme.com", domain="acme.com"))
    store.mark_sent(key)
    res = Engine(store).run("jobs", {"company": "Acme", "role": "x"}, send=False)
    assert res.skipped == 2       # already-sent Jane + no-email prospect
    assert res.rendered == 0


def test_needs_firms_guard(store, monkeypatch):
    monkeypatch.setenv("HUNTER_API_KEY", "dummy")
    with pytest.raises(ValueError, match="firm domains"):
        Engine(store).run("fundraising", {"domain": "startup.com"}, send=False)


def test_missing_required_field(store):
    with pytest.raises(ValueError, match="requires"):
        Engine(store).run("jobs", {"company": None, "role": None}, send=False)


def test_send_path_marks_sent(store, stub_jobs, monkeypatch):
    """send=True with a fake Gmail sender: marks sent, no real sleep/network."""
    sent = []

    class FakeSender:
        def send(self, to, msg):
            sent.append(to)

    monkeypatch.setattr(engine_mod, "GmailSender", lambda: FakeSender())
    monkeypatch.setattr(engine_mod.time, "sleep", lambda s: None)
    # Single-prospect source so no throttle sleep between sends anyway.
    monkeypatch.setattr(
        S, "_hunter_domain_search",
        lambda *a, **k: [Person(name="Jane", email="jane@acme.com", domain="acme.com")],
    )
    res = Engine(store).run("jobs", {"company": "Acme", "role": "x"}, send=True)
    assert res.sent == 1
    assert sent == ["jane@acme.com"]
    assert store.counts_by_status("jobs") == {"sent": 1}


def test_render_failure_is_isolated(store, monkeypatch):
    monkeypatch.setenv("HUNTER_API_KEY", "dummy")
    monkeypatch.setattr(
        S, "_hunter_domain_search",
        lambda *a, **k: [Person(name="Jane", email="jane@acme.com", domain="acme.com")],
    )

    class Boom(P.Personalizer):
        def render(self, *a):
            raise RuntimeError("model down")

    monkeypatch.setitem(P._RENDERERS, "claude", Boom)
    res = Engine(store).run("jobs", {"company": "Acme", "role": "x"}, send=False)
    assert res.failed == 1
    assert store.counts_by_status("jobs") == {"failed": 1}


def test_all_campaigns_have_required_keys():
    for name in ["jobs", "fundraising", "b2b", "pr"]:
        c = get_campaign(name)
        assert c["source"] and c["personalizer"]
        assert "prompt" in c and "fallback_subject" in c
