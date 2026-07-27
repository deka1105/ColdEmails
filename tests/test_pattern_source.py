"""Offline tests for the keyless 'pattern' prospect source + emailcheck.

No network: conftest sets COLDEMAILS_NO_NETWORK_RESOLVE=1, so has_mx() returns
None and PatternSource keeps its guesses (never blocks on unknown DNS).
"""

from __future__ import annotations

import pytest

from coldemails import emailcheck
from coldemails.engine import Engine
from coldemails.models import Criteria
from coldemails.sources import PatternSource, get_source, guess_emails


# --- pattern guessing ------------------------------------------------------

def test_guess_emails_default_ranking():
    guesses = guess_emails("Jane Doe", "acme.com")
    assert guesses[0] == "jane.doe@acme.com"  # most common corporate pattern
    assert "jdoe@acme.com" in guesses
    assert "jane@acme.com" in guesses
    # No duplicates, all at the right domain.
    assert len(guesses) == len(set(guesses))
    assert all(g.endswith("@acme.com") for g in guesses)


def test_guess_emails_pattern_hint_leads():
    guesses = guess_emails("Jane Doe", "acme.com", pattern="{f}{last}")
    assert guesses[0] == "jdoe@acme.com"  # hint wins the primary slot


def test_guess_emails_single_name_skips_last_patterns():
    guesses = guess_emails("Cher", "acme.com")
    assert guesses == ["cher@acme.com"]  # {first}.{last} etc. need a last name


def test_guess_emails_strips_accents_and_punct():
    guesses = guess_emails("José O'Brien-Smith", "acme.com")
    assert guesses[0] == "jose.obriensmith@acme.com"


def test_guess_emails_empty_name():
    assert guess_emails("", "acme.com") == []


# --- PatternSource ---------------------------------------------------------

def test_pattern_source_builds_people():
    src = get_source("pattern")
    assert isinstance(src, PatternSource)
    crit = Criteria(domain="acme.com")
    crit.extra["names"] = ["Jane Doe", "John Smith"]
    people = src.find(crit, limit=10)
    assert [p.name for p in people] == ["Jane Doe", "John Smith"]
    assert people[0].email == "jane.doe@acme.com"
    assert people[0].raw["source"] == "pattern"
    assert "j.doe@acme.com" in people[0].raw["email_candidates"] or \
        "jdoe@acme.com" in people[0].raw["email_candidates"]


def test_pattern_source_respects_limit():
    src = get_source("pattern")
    crit = Criteria(domain="acme.com")
    crit.extra["names"] = ["A B", "C D", "E F"]
    assert len(src.find(crit, limit=2)) == 2


def test_pattern_source_requires_domain():
    src = get_source("pattern")
    crit = Criteria()
    crit.extra["names"] = ["Jane Doe"]
    with pytest.raises(ValueError, match="domain"):
        src.find(crit)


def test_pattern_source_requires_names():
    src = get_source("pattern")
    crit = Criteria(domain="acme.com")
    with pytest.raises(ValueError, match="names"):
        src.find(crit)


def test_pattern_source_registered():
    assert isinstance(get_source("pattern"), PatternSource)


# --- emailcheck ------------------------------------------------------------

@pytest.mark.parametrize("email,ok", [
    ("jane.doe@acme.com", True),
    ("j@x.io", True),
    ("no-at-sign.com", False),
    ("two@@acme.com", False),
    ("missing@tld", False),
    ("", False),
    (None, False),
])
def test_valid_syntax(email, ok):
    assert emailcheck.valid_syntax(email) is ok


def test_has_mx_offline_returns_none():
    # COLDEMAILS_NO_NETWORK_RESOLVE=1 in conftest -> unknown, never touches DNS.
    assert emailcheck.has_mx("acme.com") is None


def test_validate_unknown_mx_is_mid_confidence():
    report = emailcheck.validate("jane.doe@acme.com")
    assert report["syntax"] is True
    assert report["mx"] is None
    assert report["confidence"] == 50
    assert report["deliverable"] is None


def test_validate_bad_syntax_zero_confidence():
    report = emailcheck.validate("not-an-email")
    assert report["syntax"] is False
    assert report["confidence"] == 0
    assert report["deliverable"] is False


# --- engine wiring (dry-run, template renderer, no network) ----------------

def test_engine_direct_campaign_dry_run(store):
    engine = Engine(store)
    res = engine.run(
        "direct",
        {"domain": "acme.com", "role": "loved your talk",
         "names": ["Jane Doe", "John Smith"]},
        limit=10,
        send=False,
        personalizer="template",
    )
    assert res.found == 2
    assert res.rendered == 2
    assert res.sent == 0


def test_engine_source_override_on_existing_campaign(store):
    # 'jobs' normally uses Hunter; override to the keyless pattern source.
    engine = Engine(store)
    res = engine.run(
        "jobs",
        {"company": "acme.com", "role": "ML Engineer",
         "source": "pattern", "names": ["Jane Doe"]},
        limit=5,
        send=False,
        personalizer="template",
    )
    assert res.found == 1
    assert res.rendered == 1


def test_engine_pattern_without_names_errors(store):
    engine = Engine(store)
    with pytest.raises(ValueError, match="names"):
        engine.run(
            "direct", {"domain": "acme.com"}, send=False, personalizer="template",
        )
