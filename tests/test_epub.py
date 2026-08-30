from io import BytesIO
from zipfile import ZIP_STORED, ZipFile

import pytest

from magazine_mailer.epub import EpubDownloadError, EpubValidationError, download_epub, validate_epub


def make_epub(
    *,
    mimetype="application/epub+zip",
    include_container=True,
    include_opf=True,
    content_docs=3,
    padding=60_000,
):
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_STORED) as archive:
        archive.writestr("mimetype", mimetype)
        if include_container:
            archive.writestr(
                "META-INF/container.xml",
                """<?xml version="1.0"?>
<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">
  <rootfiles>
    <rootfile full-path="EPUB/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>""",
            )
        if include_opf:
            archive.writestr(
                "EPUB/content.opf",
                """<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>Test</dc:title></metadata>
</package>""",
            )
        for index in range(content_docs):
            archive.writestr(f"EPUB/chapter-{index}.xhtml", f"<html><body>chapter {index}</body></html>")
        if padding:
            archive.writestr("EPUB/padding.bin", b"x" * padding)
    return buffer.getvalue()


def test_validate_epub_accepts_structurally_valid_payload():
    validate_epub(make_epub())


def test_validate_epub_rejects_payload_below_minimum_size():
    with pytest.raises(EpubValidationError, match="too small"):
        validate_epub(make_epub(padding=0))


def test_validate_epub_rejects_non_zip_payload():
    with pytest.raises(EpubValidationError, match="ZIP"):
        validate_epub(b"x" * 60_000)


def test_validate_epub_rejects_wrong_mimetype():
    with pytest.raises(EpubValidationError, match="mimetype"):
        validate_epub(make_epub(mimetype="application/zip"))


def test_validate_epub_requires_container_xml():
    with pytest.raises(EpubValidationError, match="container.xml"):
        validate_epub(make_epub(include_container=False))


def test_validate_epub_requires_referenced_opf():
    with pytest.raises(EpubValidationError, match="OPF"):
        validate_epub(make_epub(include_opf=False))


def test_validate_epub_requires_at_least_three_content_documents():
    with pytest.raises(EpubValidationError, match="content documents"):
        validate_epub(make_epub(content_docs=2))


class BinaryResponse:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return self.payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_download_epub_uses_bearer_token_when_available():
    requests = []
    payload = make_epub()

    def opener(request, timeout=60):
        requests.append((request, timeout))
        return BinaryResponse(payload)

    result = download_epub("https://example.test/issue.epub", token="token-123", opener=opener)

    assert result == payload
    assert requests[0][0].get_header("Authorization") == "Bearer token-123"


def test_download_epub_retries_transient_failures_before_succeeding():
    attempts = []
    payload = make_epub()

    def opener(request, timeout=60):
        attempts.append(request.full_url)
        if len(attempts) < 3:
            raise TimeoutError("temporary network timeout")
        return BinaryResponse(payload)

    result = download_epub(
        "https://example.test/issue.epub",
        opener=opener,
        retries=3,
        retry_delay=0,
    )

    assert result == payload
    assert len(attempts) == 3


def test_download_epub_raises_after_retry_budget_is_exhausted():
    attempts = []

    def opener(request, timeout=60):
        attempts.append(request.full_url)
        raise TimeoutError("still unavailable")

    with pytest.raises(EpubDownloadError, match="EPUB download failed"):
        download_epub(
            "https://example.test/issue.epub",
            opener=opener,
            retries=2,
            retry_delay=0,
        )

    assert len(attempts) == 2
