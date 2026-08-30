from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from magazine_mailer.catalog import MAGAZINES
from magazine_mailer.models import Issue


SCHEMA_VERSION = 1


class StateError(RuntimeError):
    pass


def _blank_magazine_state() -> dict[str, str | None]:
    return {
        "last_sent_issue": None,
        "last_sent_at": None,
        "stale_alerted_issue": None,
    }


class StateStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    @staticmethod
    def default_state() -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "magazines": {key: _blank_magazine_state() for key in MAGAZINES},
        }

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return self.default_state()

        try:
            state = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StateError(f"Unable to read state file {self.path}") from exc

        if state.get("schema_version") != SCHEMA_VERSION:
            raise StateError(
                f"Unsupported state schema version: {state.get('schema_version')!r}"
            )

        magazine_state = state.setdefault("magazines", {})
        for key in MAGAZINES:
            entry = magazine_state.setdefault(key, _blank_magazine_state())
            defaults = _blank_magazine_state()
            for field, value in defaults.items():
                entry.setdefault(field, value)
        return state

    def save(self, state: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temp_path = Path(handle.name)
                json.dump(state, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self.path)
            temp_path = None
        except OSError as exc:
            raise StateError(f"Unable to save state file {self.path}") from exc
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)


def mark_sent(
    state: dict[str, Any],
    issue: Issue,
    sent_at: datetime | None = None,
) -> None:
    timestamp = sent_at or datetime.now(UTC)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    timestamp = timestamp.astimezone(UTC)
    entry = state["magazines"][issue.magazine_key]
    entry["last_sent_issue"] = issue.issue_id
    entry["last_sent_at"] = timestamp.isoformat()


def should_alert_economist_stale(
    state: dict[str, Any],
    issue: Issue,
    today: date,
) -> bool:
    if issue.magazine_key != "economist":
        return False
    threshold = MAGAZINES["economist"].stale_after_days
    if threshold is None:
        return False
    age_days = (today - issue.issue_date).days
    already_alerted = state["magazines"]["economist"]["stale_alerted_issue"]
    return age_days > threshold and already_alerted != issue.issue_id


def mark_stale_alerted(state: dict[str, Any], issue: Issue) -> None:
    state["magazines"]["economist"]["stale_alerted_issue"] = issue.issue_id


def reset_stale_alert_for_new_issue(state: dict[str, Any], issue: Issue) -> bool:
    if issue.magazine_key != "economist":
        return False
    entry = state["magazines"]["economist"]
    alerted_issue = entry["stale_alerted_issue"]
    if alerted_issue is not None and issue.issue_id > alerted_issue:
        entry["stale_alerted_issue"] = None
        return True
    return False
