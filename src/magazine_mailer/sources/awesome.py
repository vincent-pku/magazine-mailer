from __future__ import annotations

import json
from datetime import date
from typing import Callable
from urllib.request import Request, urlopen

from magazine_mailer.models import Issue, MagazineSpec


API_ROOT = "https://api.github.com/repos/hehonghui/awesome-english-ebooks/contents"


class SourceError(RuntimeError):
    pass


class AwesomeEnglishEbooksSource:
    def __init__(
        self,
        token: str | None = None,
        opener: Callable = urlopen,
        timeout: int = 30,
    ) -> None:
        self._token = token
        self._opener = opener
        self._timeout = timeout

    def latest_issue(self, magazine: MagazineSpec) -> Issue:
        directories = self._get_json(f"{API_ROOT}/{magazine.directory}")
        issue_dirs = [item for item in directories if item.get("type") == "dir"]
        if not issue_dirs:
            raise SourceError(f"No issue directories found for {magazine.display_name}")

        latest = max(issue_dirs, key=lambda item: item["name"])
        issue_id = self._normalize_issue_id(latest["name"])
        try:
            issue_date = date.fromisoformat(issue_id.replace(".", "-"))
        except ValueError as exc:
            raise SourceError(
                f"Unrecognized issue directory {latest['name']!r} for {magazine.display_name}"
            ) from exc

        files = self._get_json(f"{API_ROOT}/{latest['path']}")
        epubs = [
            item
            for item in files
            if item.get("type") == "file"
            and str(item.get("name", "")).lower().endswith(".epub")
            and item.get("download_url")
        ]
        if not epubs:
            raise SourceError(f"No EPUB found for {magazine.display_name} {issue_id}")

        epub = sorted(epubs, key=lambda item: item["name"].lower())[0]
        return Issue(
            magazine_key=magazine.key,
            magazine_name=magazine.display_name,
            issue_id=issue_id,
            issue_date=issue_date,
            epub_url=epub["download_url"],
            filename=epub["name"],
        )

    def _get_json(self, url: str):
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "magazine-mailer",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        request = Request(url, headers=headers)
        try:
            with self._opener(request, timeout=self._timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except SourceError:
            raise
        except Exception as exc:
            raise SourceError(f"GitHub source request failed for {url}") from exc

    @staticmethod
    def _normalize_issue_id(directory_name: str) -> str:
        if directory_name.startswith("te_"):
            return directory_name[3:]
        return directory_name
