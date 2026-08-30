from __future__ import annotations

from io import BytesIO
from time import sleep
from typing import Callable
from urllib.request import Request, urlopen
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile


MIN_EPUB_BYTES = 50 * 1024


class EpubValidationError(ValueError):
    pass


class EpubDownloadError(RuntimeError):
    pass


def download_epub(
    url: str,
    token: str | None = None,
    opener: Callable = urlopen,
    timeout: int = 60,
    retries: int = 3,
    retry_delay: float = 1.0,
) -> bytes:
    headers = {"User-Agent": "magazine-mailer"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers)
    attempts = max(1, retries)
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            with opener(request, timeout=timeout) as response:
                return response.read()
        except Exception as exc:
            last_exc = exc
            if attempt + 1 < attempts and retry_delay > 0:
                sleep(retry_delay)
    raise EpubDownloadError(f"EPUB download failed for {url}") from last_exc


def validate_epub(payload: bytes) -> None:
    if len(payload) < MIN_EPUB_BYTES:
        raise EpubValidationError(
            f"EPUB is too small: {len(payload)} bytes (minimum {MIN_EPUB_BYTES})"
        )

    try:
        archive = ZipFile(BytesIO(payload))
    except BadZipFile as exc:
        raise EpubValidationError("EPUB payload is not a valid ZIP archive") from exc

    with archive:
        names = set(archive.namelist())
        try:
            mimetype = archive.read("mimetype").decode("utf-8").strip()
        except KeyError as exc:
            raise EpubValidationError("EPUB mimetype file is missing") from exc
        if mimetype != "application/epub+zip":
            raise EpubValidationError(f"Unexpected EPUB mimetype: {mimetype!r}")

        try:
            container_bytes = archive.read("META-INF/container.xml")
        except KeyError as exc:
            raise EpubValidationError("EPUB META-INF/container.xml is missing") from exc

        try:
            root = ElementTree.fromstring(container_bytes)
        except ElementTree.ParseError as exc:
            raise EpubValidationError("EPUB container.xml is not valid XML") from exc

        namespace = {"c": "urn:oasis:names:tc:opendocument:xmlns:container"}
        rootfile = root.find(".//c:rootfile", namespace)
        opf_path = rootfile.get("full-path") if rootfile is not None else None
        if not opf_path or opf_path not in names:
            raise EpubValidationError("Referenced EPUB OPF package is missing")

        content_documents = [
            name for name in names if name.lower().endswith((".html", ".xhtml"))
        ]
        if len(content_documents) < 3:
            raise EpubValidationError(
                f"EPUB has too few content documents: {len(content_documents)}"
            )
