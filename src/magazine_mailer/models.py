from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class MagazineSpec:
    key: str
    display_name: str
    directory: str
    stale_after_days: int | None = None


@dataclass(frozen=True, slots=True)
class Issue:
    magazine_key: str
    magazine_name: str
    issue_id: str
    issue_date: date
    epub_url: str
    filename: str
