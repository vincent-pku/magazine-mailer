import json
from datetime import UTC, date, datetime

from magazine_mailer.catalog import MAGAZINES
from magazine_mailer.models import Issue
from magazine_mailer.state import StateStore, mark_sent


def make_issue(key="economist", issue_id="2026.08.29"):
    spec = MAGAZINES[key]
    return Issue(
        magazine_key=key,
        magazine_name=spec.display_name,
        issue_id=issue_id,
        issue_date=date.fromisoformat(issue_id.replace(".", "-")),
        epub_url="https://example.test/issue.epub",
        filename="issue.epub",
    )


def test_load_initializes_schema_and_all_magazines(tmp_path):
    store = StateStore(tmp_path / "state.json")

    state = store.load()

    assert state["schema_version"] == 1
    assert set(state["magazines"]) == set(MAGAZINES)
    for item in state["magazines"].values():
        assert item == {
            "last_sent_issue": None,
            "last_sent_at": None,
            "stale_alerted_issue": None,
        }


def test_load_materializes_magazines_missing_from_existing_state(tmp_path):
    path = tmp_path / "state.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "magazines": {
                    "economist": {
                        "last_sent_issue": "2026.08.22",
                        "last_sent_at": "2026-08-22T10:00:00+00:00",
                        "stale_alerted_issue": None,
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    state = StateStore(path).load()

    assert state["magazines"]["economist"]["last_sent_issue"] == "2026.08.22"
    assert set(state["magazines"]) == set(MAGAZINES)


def test_save_replaces_state_atomically(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    store = StateStore(path)
    state = store.load()
    calls = []

    import magazine_mailer.state as state_module

    real_replace = state_module.os.replace

    def recording_replace(source, destination):
        calls.append((source, destination))
        return real_replace(source, destination)

    monkeypatch.setattr(state_module.os, "replace", recording_replace)

    store.save(state)

    assert len(calls) == 1
    assert calls[0][1] == path
    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == 1
    assert list(tmp_path.glob("*.tmp")) == []


def test_mark_sent_records_issue_and_utc_timestamp():
    state = StateStore.default_state()
    issue = make_issue()
    sent_at = datetime(2026, 8, 30, 3, 4, 5, tzinfo=UTC)

    mark_sent(state, issue, sent_at=sent_at)

    entry = state["magazines"]["economist"]
    assert entry["last_sent_issue"] == "2026.08.29"
    assert entry["last_sent_at"] == "2026-08-30T03:04:05+00:00"
