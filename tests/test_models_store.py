from coldemails.models import Person


def test_first_name():
    assert Person(name="Jane Doe").first_name == "Jane"
    assert Person(name="").first_name == ""


def test_dedup_key_stable_and_scoped():
    a = Person(name="Jane", email="jane@acme.com")
    # Same email + campaign -> same key regardless of other fields.
    assert a.dedup_key("jobs") == Person(
        name="J.", email="JANE@acme.com", title="x"
    ).dedup_key("jobs")
    # Different campaign -> different key.
    assert a.dedup_key("jobs") != a.dedup_key("b2b")


def test_dedup_key_without_email_uses_name_and_domain():
    p = Person(name="No Email", domain="acme.com")
    assert p.dedup_key("jobs") == Person(name="No Email", domain="acme.com").dedup_key("jobs")


def test_store_upsert_is_idempotent(store, person):
    k1 = store.upsert_prospect("jobs", person)
    k2 = store.upsert_prospect("jobs", person)  # duplicate -> no-op
    assert k1 == k2
    assert len(store.list_prospects("jobs")) == 1


def test_store_status_transitions(store, person):
    key = store.upsert_prospect("jobs", person)
    assert not store.already_sent(key)
    store.save_background(key, "known recruiter")
    store.save_message(key, __import__("coldemails.models", fromlist=["Message"]).Message("S", "B"))
    store.mark_sent(key)
    assert store.already_sent(key)
    counts = store.counts_by_status("jobs")
    assert counts == {"sent": 1}
    row = store.list_prospects("jobs")[0]
    assert row["background"] == "known recruiter"
    assert row["subject"] == "S" and row["body"] == "B"


def test_store_mark_failed_and_skipped(store, person):
    key = store.upsert_prospect("jobs", person)
    store.mark_failed(key, "boom")
    assert store.counts_by_status("jobs") == {"failed": 1}
    store.mark_skipped(key, "no email")
    assert store.counts_by_status("jobs") == {"skipped": 1}
