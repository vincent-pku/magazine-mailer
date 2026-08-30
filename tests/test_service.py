from datetime import date

from magazine_mailer.catalog import MAGAZINES
from magazine_mailer.models import Issue
from magazine_mailer.service import MagazineMailer
from magazine_mailer.state import StateStore


def make_issue(key, issue_id):
    spec = MAGAZINES[key]
    return Issue(
        magazine_key=key,
        magazine_name=spec.display_name,
        issue_id=issue_id,
        issue_date=date.fromisoformat(issue_id.replace(".", "-")),
        epub_url=f"https://example.test/{key}/{issue_id}.epub",
        filename=f"{key}-{issue_id}.epub",
    )


class FakeSource:
    def __init__(self, results):
        self.results = results
        self.calls = []

    def latest_issue(self, magazine):
        self.calls.append(magazine.key)
        result = self.results[magazine.key]
        if isinstance(result, Exception):
            raise result
        return result


class FakeDelivery:
    def __init__(self, fail_issue_key=None):
        self.sent = []
        self.stale_alerts = []
        self.fail_issue_key = fail_issue_key

    def send_issue(self, issue, payload):
        if issue.magazine_key == self.fail_issue_key:
            raise RuntimeError("send failed")
        self.sent.append((issue, payload))

    def send_stale_alert(self, issue, age_days):
        self.stale_alerts.append((issue, age_days))


def make_mailer(tmp_path, *, source, delivery=None, downloader=None, validator=None, keys=("economist",)):
    return MagazineMailer(
        source=source,
        state_store=StateStore(tmp_path / "state.json"),
        delivery=delivery,
        downloader=downloader or (lambda url: b"payload"),
        validator=validator or (lambda payload: None),
        magazines=[MAGAZINES[key] for key in keys],
    )


def test_duplicate_issue_is_not_downloaded_or_sent(tmp_path):
    issue = make_issue("economist", "2026.08.29")
    store = StateStore(tmp_path / "state.json")
    state = store.load()
    state["magazines"]["economist"]["last_sent_issue"] = issue.issue_id
    store.save(state)
    downloads = []
    delivery = FakeDelivery()
    mailer = MagazineMailer(
        source=FakeSource({"economist": issue}),
        state_store=store,
        delivery=delivery,
        downloader=lambda url: downloads.append(url) or b"payload",
        validator=lambda payload: None,
        magazines=[MAGAZINES["economist"]],
    )

    result = mailer.run(today=date(2026, 8, 30))

    assert result.ok
    assert result.skipped == ["economist"]
    assert downloads == []
    assert delivery.sent == []


def test_first_run_sends_current_issue_and_records_state_only_after_success(tmp_path):
    issue = make_issue("economist", "2026.08.29")
    delivery = FakeDelivery()
    validated = []
    mailer = make_mailer(
        tmp_path,
        source=FakeSource({"economist": issue}),
        delivery=delivery,
        downloader=lambda url: b"valid-epub",
        validator=lambda payload: validated.append(payload),
    )

    result = mailer.run(today=date(2026, 8, 30))

    assert result.ok
    assert result.delivered == ["economist"]
    assert validated == [b"valid-epub"]
    assert delivery.sent == [(issue, b"valid-epub")]
    state = StateStore(tmp_path / "state.json").load()
    assert state["magazines"]["economist"]["last_sent_issue"] == "2026.08.29"


def test_failed_delivery_does_not_advance_issue_state(tmp_path):
    issue = make_issue("economist", "2026.08.29")
    delivery = FakeDelivery(fail_issue_key="economist")
    mailer = make_mailer(
        tmp_path,
        source=FakeSource({"economist": issue}),
        delivery=delivery,
    )

    result = mailer.run(today=date(2026, 8, 30))

    assert not result.ok
    assert "economist" in result.failures
    state = StateStore(tmp_path / "state.json").load()
    assert state["magazines"]["economist"]["last_sent_issue"] is None


def test_dry_run_downloads_and_validates_but_never_sends_or_writes_state(tmp_path):
    issue = make_issue("economist", "2026.08.29")
    delivery = FakeDelivery()
    validated = []
    path = tmp_path / "state.json"
    mailer = MagazineMailer(
        source=FakeSource({"economist": issue}),
        state_store=StateStore(path),
        delivery=delivery,
        downloader=lambda url: b"candidate",
        validator=lambda payload: validated.append(payload),
        magazines=[MAGAZINES["economist"]],
    )

    result = mailer.run(dry_run=True, today=date(2026, 8, 30))

    assert result.ok
    assert result.discovered == ["economist"]
    assert validated == [b"candidate"]
    assert delivery.sent == []
    assert not path.exists()


def test_failure_in_one_magazine_does_not_block_another(tmp_path):
    new_yorker = make_issue("new_yorker", "2026.08.31")
    source = FakeSource(
        {
            "economist": RuntimeError("upstream unavailable"),
            "new_yorker": new_yorker,
        }
    )
    delivery = FakeDelivery()
    mailer = make_mailer(
        tmp_path,
        source=source,
        delivery=delivery,
        keys=("economist", "new_yorker"),
    )

    result = mailer.run(today=date(2026, 8, 30))

    assert not result.ok
    assert "economist" in result.failures
    assert result.delivered == ["new_yorker"]
    assert [item[0].magazine_key for item in delivery.sent] == ["new_yorker"]
    state = StateStore(tmp_path / "state.json").load()
    assert state["magazines"]["new_yorker"]["last_sent_issue"] == "2026.08.31"


def test_economist_stale_alert_is_sent_once_and_persisted(tmp_path):
    stale_issue = make_issue("economist", "2026.08.19")
    source = FakeSource({"economist": stale_issue})
    delivery = FakeDelivery()
    mailer = make_mailer(tmp_path, source=source, delivery=delivery)

    first = mailer.run(today=date(2026, 8, 30))
    second = mailer.run(today=date(2026, 8, 30))

    assert first.ok and second.ok
    assert delivery.stale_alerts == [(stale_issue, 11)]
    state = StateStore(tmp_path / "state.json").load()
    assert state["magazines"]["economist"]["stale_alerted_issue"] == "2026.08.19"
