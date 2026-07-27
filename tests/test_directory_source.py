"""Offline tests for the CSV-directory prospect source.

No network: conftest sets COLDEMAILS_NO_NETWORK_RESOLVE=1, so company->domain
resolution falls back to a slug and has_mx() returns None (guesses kept).
"""

from __future__ import annotations

import pytest

from coldemails.engine import Engine
from coldemails.models import Criteria
from coldemails.sources import DirectorySource, get_source


DIRECTORY = """\
name,domain,company,title,notes,email
# a comment row, skipped
Jane Doe,acme.com,Acme,Head of Payments,"spoke at a conf",
Alan Kim,,Beta Labs,Professor,"2026 paper on transformers",
Priya Nair,gamma.com,Gamma,Partner,,priya@gamma.com
,,,,,
"""


@pytest.fixture
def dir_csv(tmp_path):
    p = tmp_path / "directory.csv"
    p.write_text(DIRECTORY, encoding="utf-8")
    return str(p)


def _crit(path):
    c = Criteria()
    c.extra["directory"] = path
    return c


def test_directory_registered():
    assert isinstance(get_source("directory"), DirectorySource)


def test_directory_reads_rows_and_infers_emails(dir_csv):
    people = get_source("directory").find(_crit(dir_csv), limit=10)
    # Comment row and the empty trailing row are skipped -> 3 people.
    assert [p.name for p in people] == ["Jane Doe", "Alan Kim", "Priya Nair"]
    # Inferred from name + domain.
    assert people[0].email == "jane.doe@acme.com"
    # Explicit email column wins over inference.
    assert people[2].email == "priya@gamma.com"


def test_directory_carries_notes_as_background(dir_csv):
    people = get_source("directory").find(_crit(dir_csv), limit=10)
    assert people[0].background == "spoke at a conf"
    assert people[0].title == "Head of Payments"


def test_directory_resolves_company_when_domain_blank(dir_csv):
    # Alan Kim has no domain; company 'Beta Labs' -> slug fallback (offline).
    people = get_source("directory").find(_crit(dir_csv), limit=10)
    alan = people[1]
    assert alan.domain == "betalabs.com"
    assert alan.email == "alan.kim@betalabs.com"


def test_directory_respects_limit(dir_csv):
    assert len(get_source("directory").find(_crit(dir_csv), limit=2)) == 2


def test_directory_missing_file_errors():
    c = Criteria()
    c.extra["directory"] = "/no/such/directory.csv"
    with pytest.raises(ValueError, match="not found"):
        get_source("directory").find(c)


def test_engine_directory_campaign_dry_run(store, dir_csv):
    engine = Engine(store)
    res = engine.run(
        "directory",
        {"role": "loved your work", "directory": dir_csv},
        limit=10,
        send=False,
        personalizer="template",
    )
    assert res.found == 3
    assert res.rendered == 3
    assert res.sent == 0
    # Notes were persisted as background.
    rows = {r["name"]: r for r in store.list_prospects("directory")}
    assert rows["Jane Doe"]["background"] == "spoke at a conf"
