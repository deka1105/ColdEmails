"""Attachment support: MIME building, dry-run display, engine wiring."""

import pytest

from coldemails.gmail import ConsoleSender, build_mime
from coldemails.models import Message


@pytest.fixture
def pdf(tmp_path):
    p = tmp_path / "resume.pdf"
    p.write_bytes(b"%PDF-1.4 fake")
    return str(p)


def test_build_mime_plain_text_without_attachments():
    mime = build_mime("Me <me@x.com>", "you@y.com", Message("Hi", "Body"))
    assert not mime.is_multipart()
    assert mime["Subject"] == "Hi"
    assert mime["To"] == "you@y.com"


def test_build_mime_with_attachment(pdf):
    msg = Message("Hi", "Body", attachments=[pdf])
    mime = build_mime("Me <me@x.com>", "you@y.com", msg)
    assert mime.is_multipart()
    parts = mime.get_payload()
    assert parts[0].get_payload() == "Body"
    att = parts[1]
    assert att.get_filename() == "resume.pdf"
    assert att.get_content_type() == "application/pdf"
    assert att.get_payload(decode=True) == b"%PDF-1.4 fake"


def test_console_sender_lists_attachments(pdf, capsys):
    ConsoleSender().send("you@y.com", Message("Hi", "Body", attachments=[pdf]))
    out = capsys.readouterr().out
    assert "Attachments: resume.pdf" in out


def test_engine_attaches_to_rendered_messages(monkeypatch, store, person, pdf):
    import coldemails.sources as S
    from coldemails.engine import Engine
    from coldemails.gmail import ConsoleSender as CS

    monkeypatch.setenv("HUNTER_API_KEY", "dummy")
    monkeypatch.setattr(S, "_hunter_domain_search", lambda *a, **k: [person])

    sent: list[Message] = []
    monkeypatch.setattr(CS, "send", lambda self, to, msg: sent.append(msg))

    engine = Engine(store)
    res = engine.run(
        "jobs", {"company": "Acme", "role": "ML Engineer"},
        limit=1, send=False, personalizer="template", attachments=[pdf],
    )
    assert res.rendered == 1
    assert sent[0].attachments == [pdf]


def test_engine_rejects_missing_attachment(store):
    from coldemails.engine import Engine

    with pytest.raises(ValueError, match="Attachment not found"):
        Engine(store).run(
            "jobs", {"company": "Acme", "role": "X"},
            personalizer="template", attachments=["/no/such/file.pdf"],
        )


def test_cli_test_send(monkeypatch, pdf, capsys):
    import coldemails.cli as cli
    from coldemails.gmail import GmailSender

    monkeypatch.setenv("SENDER_EMAIL", "me@example.com")
    sent = {}

    def fake_send(self, to, msg):
        sent["to"], sent["msg"] = to, msg

    monkeypatch.setattr(GmailSender, "__init__", lambda self: None)
    monkeypatch.setattr(GmailSender, "send", fake_send)
    assert cli.main(["test-send", "--attach", pdf]) == 0
    assert sent["to"] == "me@example.com"
    assert sent["msg"].attachments == [pdf]
    assert "Gmail is configured" in sent["msg"].subject


def test_cli_attach_flag_parses(monkeypatch, tmp_path, pdf):
    import coldemails.cli as cli
    from coldemails.engine import RunResult

    monkeypatch.setenv("COLDEMAILS_DB", str(tmp_path / "a.db"))
    captured = {}

    def fake_run(self, campaign, args, limit=10, send=False, personalizer=None, attachments=None):
        captured["attachments"] = attachments
        return RunResult()

    monkeypatch.setattr(cli.Engine, "run", fake_run)
    assert cli.main([
        "preview", "--campaign", "jobs", "--company", "Acme",
        "--role", "X", "--attach", pdf, "--attach", pdf,
    ]) == 0
    assert captured["attachments"] == [pdf, pdf]
