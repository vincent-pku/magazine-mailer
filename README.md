# Magazine Mailer

Automatically detects new EPUB issues in [`hehonghui/awesome-english-ebooks`](https://github.com/hehonghui/awesome-english-ebooks), validates them, and emails each new issue once.

## Supported magazines

- The Economist
- The New Yorker
- The Atlantic
- Wired

V1 intentionally uses `awesome-english-ebooks` as the only content source. The source adapter is isolated so a self-hosted scraper can be added later without rewriting delivery, state, validation, or scheduling.

## How it works

1. GitHub Actions runs every six hours.
2. The source adapter checks the latest issue directory for each magazine.
3. Already delivered issue IDs are skipped.
4. New EPUBs are downloaded and structurally validated.
5. Valid EPUBs are sent by SMTP, one magazine per email.
6. Only successful deliveries are written to `state/state.json`.
7. The Action commits that state file back to `main`.

The Economist also has a stale-source check. If the newest detected issue is more than 10 days old, one warning email is sent for that stale issue. The same warning is not repeated until a newer issue appears.

## GitHub repository setup

The workflow needs three repository Secrets for real delivery:

| Secret | Purpose |
| --- | --- |
| `MAIL_USERNAME` | SMTP username and From address, for example a Gmail address |
| `MAIL_PASSWORD` | SMTP password or Gmail App Password |
| `MAIL_TO` | Destination email address |

Defaults are `smtp.gmail.com` and port `587`. To use a different SMTP provider, optionally define repository Variables `SMTP_HOST` and `SMTP_PORT`.

Do not commit account passwords or app passwords to this repository.

## First verification run

The manual workflow defaults to `dry_run=true`. A dry run:

- checks all four upstream magazine directories;
- downloads any issue that is new relative to the committed state;
- validates the EPUB structure;
- sends no email;
- makes no state changes.

This lets the GitHub Action be verified before email Secrets are configured.

After the three email Secrets exist, run the workflow with `dry_run=false` once. Because the initial state is empty, that first real run sends only the current latest issue of each magazine. It does not backfill old issues.

Scheduled runs are always real delivery runs.

## Local development

Python 3.12 or newer is required.

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[test]'
python -m pytest -q
python -m magazine_mailer --dry-run
```

A real local send uses environment variables rather than checked-in credentials:

```bash
export MAIL_USERNAME='your-account@example.com'
export MAIL_PASSWORD='your-app-password'
export MAIL_TO='destination@example.com'
python -m magazine_mailer
```

## State guarantees

`state/state.json` is the durable duplicate-suppression record. A magazine's `last_sent_issue` changes only after SMTP reports a successful send. A failed source request, download, EPUB validation, or email send therefore remains retryable on the next run.

GitHub Actions uses a single concurrency group so two scheduled/manual runs cannot race the state update. The workflow only stages `state/state.json` when it creates an automated state commit.

## Project layout

```text
src/magazine_mailer/
├── catalog.py            # magazine configuration
├── models.py             # normalized issue/source models
├── epub.py               # download and EPUB structural validation
├── email_delivery.py     # SMTP delivery
├── state.py              # durable JSON state and stale alert rules
├── service.py            # orchestration
└── sources/
    ├── base.py           # source protocol
    └── awesome.py        # current upstream adapter

state/state.json
.github/workflows/deliver.yml
```

## Future fallback source

If `awesome-english-ebooks` stops updating, add another implementation of the `MagazineSource` protocol under `src/magazine_mailer/sources/`. The rest of the application does not depend on GitHub directory naming or on that repository's internal layout.
