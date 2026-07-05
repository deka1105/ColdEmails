"""Smoke test for the Streamlit app's engine wiring (skipped if streamlit absent)."""

import pytest

pytest.importorskip("streamlit")

import coldemails.sources as S
from coldemails.models import Person


def test_run_engine_wires_pipeline(monkeypatch, tmp_path):
    monkeypatch.setenv("HUNTER_API_KEY", "dummy")
    monkeypatch.setenv("COLDEMAILS_DB", str(tmp_path / "app.db"))
    monkeypatch.setattr(
        S,
        "_hunter_domain_search",
        lambda *a, **k: [
            Person(name="Jane", email="jane@acme.com", title="Recruiter",
                   company="Acme", domain="acme.com")
        ],
    )
    import app

    result, logs, rows = app.run_engine(
        "jobs",
        {"company": "Acme", "role": "ML Engineer", "location": "NYC"},
        limit=5,
        send=False,
        personalizer="template",  # no Anthropic key needed
    )
    assert result.found == 1 and result.rendered == 1
    assert len(rows) == 1 and rows[0]["subject"]
    assert logs  # engine produced log output
