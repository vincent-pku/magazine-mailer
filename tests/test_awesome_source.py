import json
from datetime import date

import pytest

from magazine_mailer.catalog import MAGAZINES
from magazine_mailer.sources.awesome import AwesomeEnglishEbooksSource, SourceError


class FakeResponse:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class SequenceOpener:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.requests = []

    def __call__(self, request, timeout=30):
        self.requests.append((request, timeout))
        return FakeResponse(self.payloads.pop(0))


def test_latest_issue_selects_newest_directory_and_epub():
    opener = SequenceOpener(
        [
            [
                {"type": "dir", "name": "2026.08.24", "path": "02_new_yorker/2026.08.24"},
                {"type": "dir", "name": "2026.08.31", "path": "02_new_yorker/2026.08.31"},
                {"type": "file", "name": "README.md", "path": "02_new_yorker/README.md"},
            ],
            [
                {"type": "file", "name": "issue.pdf", "download_url": "https://example.test/issue.pdf"},
                {"type": "file", "name": "new_yorker.2026.08.31.epub", "download_url": "https://example.test/issue.epub"},
            ],
        ]
    )
    source = AwesomeEnglishEbooksSource(opener=opener)

    issue = source.latest_issue(MAGAZINES["new_yorker"])

    assert issue.issue_id == "2026.08.31"
    assert issue.issue_date == date(2026, 8, 31)
    assert issue.filename == "new_yorker.2026.08.31.epub"
    assert issue.epub_url == "https://example.test/issue.epub"


def test_economist_issue_id_strips_te_prefix():
    opener = SequenceOpener(
        [
            [{"type": "dir", "name": "te_2026.08.29", "path": "01_economist/te_2026.08.29"}],
            [{"type": "file", "name": "TheEconomist.2026.08.29.epub", "download_url": "https://example.test/e.epub"}],
        ]
    )
    source = AwesomeEnglishEbooksSource(opener=opener)

    issue = source.latest_issue(MAGAZINES["economist"])

    assert issue.issue_id == "2026.08.29"
    assert issue.issue_date == date(2026, 8, 29)


def test_source_adds_bearer_token_to_github_api_requests():
    opener = SequenceOpener(
        [
            [{"type": "dir", "name": "2026.08.02", "path": "04_atlantic/2026.08.02"}],
            [{"type": "file", "name": "Atlantic_2026.08.02.epub", "download_url": "https://example.test/a.epub"}],
        ]
    )
    source = AwesomeEnglishEbooksSource(token="secret-token", opener=opener)

    source.latest_issue(MAGAZINES["atlantic"])

    assert len(opener.requests) == 2
    assert all(req.get_header("Authorization") == "Bearer secret-token" for req, _ in opener.requests)


def test_source_omits_authorization_header_without_token():
    opener = SequenceOpener(
        [
            [{"type": "dir", "name": "2026.08.02", "path": "05_wired/2026.08.02"}],
            [{"type": "file", "name": "wired_2026.08.02.epub", "download_url": "https://example.test/w.epub"}],
        ]
    )
    source = AwesomeEnglishEbooksSource(opener=opener)

    source.latest_issue(MAGAZINES["wired"])

    assert all(req.get_header("Authorization") is None for req, _ in opener.requests)


def test_latest_issue_raises_when_newest_directory_has_no_epub():
    opener = SequenceOpener(
        [
            [{"type": "dir", "name": "2026.08.02", "path": "05_wired/2026.08.02"}],
            [{"type": "file", "name": "README.md", "download_url": "https://example.test/readme"}],
        ]
    )
    source = AwesomeEnglishEbooksSource(opener=opener)

    with pytest.raises(SourceError, match="EPUB"):
        source.latest_issue(MAGAZINES["wired"])
