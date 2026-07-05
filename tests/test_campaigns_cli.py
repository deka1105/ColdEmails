"""Campaign config sanity + CLI export."""

from coldemails.campaigns import CAMPAIGNS, get_campaign
from coldemails.cli import main
from coldemails.models import Message
from coldemails.store import Store


def test_all_campaigns_have_required_shape():
    assert set(CAMPAIGNS) >= {
        "jobs", "fundraising", "b2b", "pr", "podcast", "partnerships", "recruiting"
    }
    for name, cfg in CAMPAIGNS.items():
        assert cfg["source"] in {"hunter", "hunter_firms"}, name
        assert cfg["personalizer"], name
        assert cfg["prompt"], name
        assert cfg["fallback_subject"], name
        assert isinstance(cfg.get("requires", []), list), name


def test_get_campaign_unknown():
    import pytest

    with pytest.raises(KeyError):
        get_campaign("nope")


def test_cli_export_csv(tmp_path, monkeypatch, person):
    db = tmp_path / "e.db"
    monkeypatch.setenv("COLDEMAILS_DB", str(db))
    with Store(str(db)) as store:
        key = store.upsert_prospect("jobs", person)
        store.save_message(key, Message(subject="Hi", body="Body,\nwith comma"))

    out = tmp_path / "out.csv"
    assert main(["export", "--campaign", "jobs", "--out", str(out)]) == 0

    import csv

    rows = list(csv.DictReader(out.open()))
    assert len(rows) == 1
    assert rows[0]["email"] == "jane@acme.com"
    assert rows[0]["subject"] == "Hi"
    assert rows[0]["status"] == "previewed"


def test_cli_export_empty_db(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("COLDEMAILS_DB", str(tmp_path / "empty.db"))
    assert main(["export"]) == 0
    assert "No prospects" in capsys.readouterr().out
