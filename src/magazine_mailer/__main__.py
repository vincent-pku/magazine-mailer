from __future__ import annotations

import argparse
import os
from functools import partial

from magazine_mailer.catalog import MAGAZINES
from magazine_mailer.email_delivery import EmailDelivery, SmtpConfig, SmtpConfigError
from magazine_mailer.epub import download_epub, validate_epub
from magazine_mailer.service import MagazineMailer, RunResult
from magazine_mailer.sources.awesome import AwesomeEnglishEbooksSource
from magazine_mailer.state import StateStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Email newly published magazine EPUBs.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Discover, download, and validate without email or state changes.",
    )
    return parser


def issue_status(key: str, result: RunResult) -> str:
    if key in result.failures:
        return "failed"
    if key in (result.discovered + result.delivered):
        return "new"
    return "unchanged"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    token = os.getenv("GITHUB_TOKEN") or None
    source = AwesomeEnglishEbooksSource(token=token)
    state_store = StateStore(os.getenv("STATE_PATH", "state/state.json"))

    delivery = None
    if not args.dry_run:
        try:
            delivery = EmailDelivery(SmtpConfig.from_env())
        except SmtpConfigError as exc:
            print(f"CONFIGURATION ERROR: {exc}")
            return 2

    mailer = MagazineMailer(
        source=source,
        state_store=state_store,
        delivery=delivery,
        downloader=partial(download_epub, token=token),
        validator=validate_epub,
        magazines=MAGAZINES.values(),
    )
    result = mailer.run(dry_run=args.dry_run)

    for key, issue_id in result.latest.items():
        print(f"{key}: {issue_id} ({issue_status(key, result)})")
    for key in result.stale_alerts:
        print(f"{key}: stale-source alert {'would be sent' if args.dry_run else 'sent'}")
    for key, message in result.failures.items():
        print(f"ERROR {key}: {message}")

    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
