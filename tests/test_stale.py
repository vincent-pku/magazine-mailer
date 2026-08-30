from datetime import date

from magazine_mailer.catalog import MAGAZINES
from magazine_mailer.models import Issue
from magazine_mailer.state import (
    StateStore,
    mark_stale_alerted,
    reset_stale_alert_for_new_issue,
    should_alert_economist_stale,
)


def issue(issue_id):
    spec = MAGAZINES["economist"]
    return Issue(
        magazine_key="economist",
        magazine_name=spec.display_name,
        issue_id=issue_id,
        issue_date=date.fromisoformat(issue_id.replace(".", "-")),
        epub_url="https://example.test/e.epub",
        filename="e.epub",
    )


def test_economist_is_not_stale_at_exactly_ten_days():
    state = StateStore.default_state()

    assert not should_alert_economist_stale(
        state,
        issue("2026.08.20"),
        today=date(2026, 8, 30),
    )


def test_economist_is_stale_after_eleven_days():
    state = StateStore.default_state()

    assert should_alert_economist_stale(
        state,
        issue("2026.08.19"),
        today=date(2026, 8, 30),
    )


def test_stale_alert_is_suppressed_for_same_issue_after_marking():
    state = StateStore.default_state()
    old_issue = issue("2026.08.19")

    mark_stale_alerted(state, old_issue)

    assert not should_alert_economist_stale(
        state,
        old_issue,
        today=date(2026, 8, 30),
    )


def test_newer_issue_clears_previous_stale_alert_suppression():
    state = StateStore.default_state()
    old_issue = issue("2026.08.19")
    new_issue = issue("2026.08.29")
    mark_stale_alerted(state, old_issue)

    changed = reset_stale_alert_for_new_issue(state, new_issue)

    assert changed is True
    assert state["magazines"]["economist"]["stale_alerted_issue"] is None
