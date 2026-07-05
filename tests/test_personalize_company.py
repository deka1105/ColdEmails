from coldemails import company
from coldemails.models import Criteria, Person
from coldemails.personalize import (
    TemplateRenderer,
    _fields,
    _fill,
    get_personalizer,
)


def test_company_resolve():
    assert company.resolve("Stripe") == "stripe.com"
    assert company.resolve("stripe.com") == "stripe.com"
    assert company.resolve("https://Stripe.com/") == "stripe.com"
    # Legal suffixes are stripped before slugging.
    assert company.resolve("Foo Bar Inc") == "foobar.com"
    assert company.resolve("Acme GmbH") == "acme.com"


def test_company_resolve_clearbit(monkeypatch):
    company._cache.clear()
    monkeypatch.delenv("COLDEMAILS_NO_NETWORK_RESOLVE", raising=False)

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return [
                {"name": "Notion Labs", "domain": "notionlabs.com"},
                {"name": "Notion", "domain": "notion.so"},
            ]

    monkeypatch.setattr(company.requests, "get", lambda *a, **k: FakeResp())
    # Exact name match wins over the top suggestion.
    assert company.resolve("Notion") == "notion.so"
    company._cache.clear()
    assert company.resolve("Not On The List") == "notionlabs.com"
    company._cache.clear()


def test_company_resolve_clearbit_failure_falls_back(monkeypatch):
    import requests as req

    company._cache.clear()
    monkeypatch.delenv("COLDEMAILS_NO_NETWORK_RESOLVE", raising=False)

    def boom(*a, **k):
        raise req.ConnectionError("offline")

    monkeypatch.setattr(company.requests, "get", boom)
    assert company.resolve("Some Startup") == "somestartup.com"
    company._cache.clear()


def test_fill_leaves_unknown_placeholders_empty():
    assert _fill("Hi {name}, {unknown}", {"name": "Jo"}) == "Hi Jo, "


def test_fields_separates_firm_and_startup_domain():
    person = Person(name="Ann", title="GP", company="a16z", domain="a16z.com")
    criteria = Criteria(domain="mystartup.com", location="SF")
    f = _fields(person, criteria, {})
    assert f["firm"] == "a16z"
    assert f["startup_domain"] == "mystartup.com"
    assert f["domain"] == "a16z.com"  # prospect's own domain


def test_template_renderer_fills_prompt_and_subject():
    campaign = {
        "prompt": "To {name} about {role} at {company}",
        "fallback_subject": "Re: {role}",
    }
    person = Person(name="Jane", company="Acme")
    criteria = Criteria(role="ML Engineer")
    msg = TemplateRenderer().render(person, criteria, campaign)
    assert msg.subject == "Re: ML Engineer"
    assert msg.body == "To Jane about ML Engineer at Acme"


def test_get_personalizer_unknown():
    import pytest

    with pytest.raises(ValueError):
        get_personalizer("nope")


def test_parse_email_with_subject_line():
    from coldemails.personalize import _parse_email

    msg = _parse_email("Subject: Quick intro\n\nHi Jane,\nbody here.", "fallback")
    assert msg.subject == "Quick intro"
    assert msg.body == "Hi Jane,\nbody here."


def test_parse_email_without_subject_uses_fallback():
    from coldemails.personalize import _parse_email

    msg = _parse_email("Hi Jane, just the body.", "fallback")
    assert msg.subject == "fallback"
    assert msg.body == "Hi Jane, just the body."


def test_parse_email_empty_subject_or_body_degrades_gracefully():
    from coldemails.personalize import _parse_email

    msg = _parse_email("Subject: \n\nBody.", "fb")
    assert msg.subject == "fb"
    msg2 = _parse_email("Subject: Only a subject", "fb")
    assert msg2.subject == "fb"  # no body after the subject line
    assert msg2.body == "Subject: Only a subject"


def test_claude_cli_renderer(monkeypatch):
    import subprocess

    import coldemails.personalize as pmod

    monkeypatch.setattr(pmod.shutil, "which", lambda _: "/usr/local/bin/claude")

    captured = {}

    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(
            cmd, 0, stdout="Subject: A real subject\n\nHi Jane, quick note.", stderr=""
        )

    monkeypatch.setattr(pmod.subprocess, "run", fake_run)

    r = pmod.ClaudeCLIRenderer()
    campaign = {"prompt": "Email {name}", "fallback_subject": "Re: {name}"}
    msg = r.render(Person(name="Jane"), Criteria(), campaign)
    assert msg.body == "Hi Jane, quick note."
    assert msg.subject == "A real subject"
    assert "-p" in captured["cmd"] and "--model" in captured["cmd"]


def test_claude_cli_renderer_missing_binary(monkeypatch):
    import pytest

    import coldemails.personalize as pmod

    monkeypatch.setattr(pmod.shutil, "which", lambda _: None)
    with pytest.raises(RuntimeError, match="not found on PATH"):
        pmod.ClaudeCLIRenderer()
