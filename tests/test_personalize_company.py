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
    assert company.resolve("Foo Bar Inc") == "foobarinc.com"


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


def test_claude_cli_renderer(monkeypatch):
    import subprocess

    import coldemails.personalize as pmod

    monkeypatch.setattr(pmod.shutil, "which", lambda _: "/usr/local/bin/claude")

    captured = {}

    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="Hi Jane, quick note.", stderr="")

    monkeypatch.setattr(pmod.subprocess, "run", fake_run)

    r = pmod.ClaudeCLIRenderer()
    campaign = {"prompt": "Email {name}", "fallback_subject": "Re: {name}"}
    msg = r.render(Person(name="Jane"), Criteria(), campaign)
    assert msg.body == "Hi Jane, quick note."
    assert msg.subject == "Re: Jane"
    assert "-p" in captured["cmd"] and "--model" in captured["cmd"]


def test_claude_cli_renderer_missing_binary(monkeypatch):
    import pytest

    import coldemails.personalize as pmod

    monkeypatch.setattr(pmod.shutil, "which", lambda _: None)
    with pytest.raises(RuntimeError, match="not found on PATH"):
        pmod.ClaudeCLIRenderer()
