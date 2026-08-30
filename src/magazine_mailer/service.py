from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Callable, Iterable

from magazine_mailer.email_delivery import EmailDelivery
from magazine_mailer.models import MagazineSpec
from magazine_mailer.sources.base import MagazineSource
from magazine_mailer.state import (
    StateStore,
    mark_sent,
    mark_stale_alerted,
    reset_stale_alert_for_new_issue,
    should_alert_economist_stale,
)


@dataclass(slots=True)
class RunResult:
    discovered: list[str] = field(default_factory=list)
    delivered: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    stale_alerts: list[str] = field(default_factory=list)
    failures: dict[str, str] = field(default_factory=dict)
    latest: dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.failures


class MagazineMailer:
    def __init__(
        self,
        *,
        source: MagazineSource,
        state_store: StateStore,
        delivery: EmailDelivery | None,
        downloader: Callable[[str], bytes],
        validator: Callable[[bytes], None],
        magazines: Iterable[MagazineSpec],
    ) -> None:
        self._source = source
        self._state_store = state_store
        self._delivery = delivery
        self._downloader = downloader
        self._validator = validator
        self._magazines = list(magazines)

    def run(self, dry_run: bool = False, today: date | None = None) -> RunResult:
        result = RunResult()
        current_day = today or datetime.now(UTC).date()
        state = self._state_store.load()
        working_state = deepcopy(state) if dry_run else state

        for magazine in self._magazines:
            try:
                issue = self._source.latest_issue(magazine)
                result.latest[magazine.key] = issue.issue_id
            except Exception as exc:
                result.failures[magazine.key] = str(exc)
                continue

            if magazine.key == "economist":
                stale_reset = reset_stale_alert_for_new_issue(working_state, issue)
                if stale_reset and not dry_run:
                    try:
                        self._state_store.save(working_state)
                    except Exception as exc:
                        result.failures["state"] = str(exc)
                        return result

            entry = working_state["magazines"][magazine.key]
            if entry["last_sent_issue"] == issue.issue_id:
                result.skipped.append(magazine.key)
            else:
                try:
                    payload = self._downloader(issue.epub_url)
                    self._validator(payload)
                    if dry_run:
                        result.discovered.append(magazine.key)
                    else:
                        if self._delivery is None:
                            raise RuntimeError("Email delivery is not configured")
                        self._delivery.send_issue(issue, payload)
                        mark_sent(working_state, issue)
                        result.delivered.append(magazine.key)
                        try:
                            self._state_store.save(working_state)
                        except Exception as exc:
                            result.failures["state"] = str(exc)
                            return result
                except Exception as exc:
                    result.failures[magazine.key] = str(exc)

            if magazine.key == "economist" and should_alert_economist_stale(
                working_state,
                issue,
                today=current_day,
            ):
                age_days = (current_day - issue.issue_date).days
                if dry_run:
                    result.stale_alerts.append(magazine.key)
                else:
                    try:
                        if self._delivery is None:
                            raise RuntimeError("Email delivery is not configured")
                        self._delivery.send_stale_alert(issue, age_days)
                        mark_stale_alerted(working_state, issue)
                        result.stale_alerts.append(magazine.key)
                        try:
                            self._state_store.save(working_state)
                        except Exception as exc:
                            result.failures["state"] = str(exc)
                            return result
                    except Exception as exc:
                        result.failures[f"{magazine.key}:stale"] = str(exc)

        return result
