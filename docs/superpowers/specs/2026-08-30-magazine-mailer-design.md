# Magazine Mailer Design

## Goal

Build a small serverless automation that detects newly published magazine EPUBs in `hehonghui/awesome-english-ebooks`, validates them, emails them once, and persists delivery state in the project repository.

## Scope

V1 supports four magazines from one source only:

- The Economist → `01_economist`
- The New Yorker → `02_new_yorker`
- The Atlantic → `04_atlantic`
- Wired → `05_wired`

The source boundary must be replaceable later so an independent scraper can be added without changing delivery, state, validation, or scheduling logic.

## Architecture

The application is a Python package with four focused boundaries:

1. **Source adapter** — queries the GitHub Contents API for the newest issue directory and chooses the preferred `.epub` asset.
2. **EPUB validator** — downloads a candidate and rejects structurally invalid or implausibly empty EPUBs before delivery.
3. **State store** — reads/writes `state/state.json`, records last delivered issue per magazine, and records stale-alert suppression state.
4. **Email delivery** — sends one email per newly detected magazine issue using SMTP; the EPUB is attached.

`main.py` orchestrates these boundaries. The GitHub Actions workflow runs it every six hours and can also be invoked manually in dry-run mode.

## Source model

Each magazine is configured with:

- stable key (`economist`, `new_yorker`, `atlantic`, `wired`)
- display name
- upstream directory
- expected issue cadence metadata

`AwesomeEnglishEbooksSource` implements a common `MagazineSource` protocol. It uses `https://api.github.com/repos/hehonghui/awesome-english-ebooks/contents/...` and sends `Authorization: Bearer <GITHUB_TOKEN>` when a token is available. Local execution remains possible without a token.

The adapter selects the lexicographically newest issue directory because the upstream naming scheme embeds sortable issue dates. It then selects `.epub` over other formats.

## Delivery semantics

For each magazine:

1. discover latest issue;
2. compare with `last_sent_issue`;
3. if unchanged, do nothing;
4. if new, download the EPUB;
5. validate EPUB structure;
6. send one email with that EPUB attached;
7. only after successful SMTP delivery, persist the issue as sent.

A failed download, validation, or SMTP operation must not advance delivery state.

The first non-dry run on an empty state file sends the current latest issue for each configured magazine. Older historical issues are not backfilled.

## EPUB validation

A candidate is accepted only if all of these hold:

- HTTP download succeeds;
- payload is at least 50 KiB;
- ZIP archive opens successfully;
- root `mimetype` exists and equals `application/epub+zip`;
- `META-INF/container.xml` exists;
- its referenced OPF package exists;
- the archive contains at least three HTML/XHTML content documents.

These checks are intentionally structural rather than publication-specific so the validator remains reusable if the content source changes later.

## State

`state/state.json` is versioned in Git and has this shape:

```json
{
  "schema_version": 1,
  "magazines": {
    "economist": {
      "last_sent_issue": null,
      "last_sent_at": null,
      "stale_alerted_issue": null
    }
  }
}
```

All four magazines are materialized when the file is first loaded. Writes are atomic.

After a successful scheduled/manual non-dry run, the Action commits `state/state.json` back to `main` only when it changed. The workflow has `contents: write` permission and uses a concurrency group so two runs cannot race state updates.

The workflow is schedule/manual only; state commits do not recursively trigger a run.

## Economist stale alert

The latest Economist issue date is parsed from its upstream issue-directory name. If it is more than 10 days old, the run sends a single stale-source alert email.

The state field `stale_alerted_issue` suppresses repeated alerts for the same stale issue. It is reset to `null` when a newer Economist issue appears.

Dry-run mode reports the stale condition but sends no email and changes no state.

## Email configuration

V1 targets ordinary SMTP with Gmail-friendly defaults:

- `SMTP_HOST` defaults to `smtp.gmail.com`
- `SMTP_PORT` defaults to `587`
- `MAIL_USERNAME` is the SMTP username/from address
- `MAIL_PASSWORD` is the SMTP/app password
- `MAIL_TO` is the destination address

Only the three account-specific values are required as GitHub Secrets. Host/port may be overridden with repository variables later without code changes.

## GitHub Actions

Workflow behavior:

- Python 3.12
- `workflow_dispatch` input `dry_run` (default `true`)
- schedule every six hours at minute 17
- `GITHUB_TOKEN` passed automatically to the source adapter
- installs the package and runs tests before the application
- scheduled runs are real delivery runs
- manual runs can be dry runs before email Secrets exist
- non-dry successful runs commit changed state back to `main`

## Error handling

The process exits non-zero when a candidate issue cannot be safely processed. It prints concise per-magazine diagnostics without printing secrets.

A failure in one magazine must not prevent the other magazines from being evaluated. The final process exit status is non-zero if any magazine encountered a processing failure.

## Testing

Tests cover:

- newest issue and EPUB selection from GitHub API payloads;
- authenticated and unauthenticated source requests;
- EPUB structural validation and rejection paths;
- state initialization and atomic update semantics;
- duplicate suppression;
- first-run behavior;
- stale Economist calculation and alert suppression;
- SMTP message construction and attachment behavior without contacting a real SMTP server;
- orchestration behavior when one magazine fails and others succeed.

Integration verification additionally runs a live source discovery against the public upstream in dry-run mode, with no email delivery and no state mutation.

## Non-goals for V1

- scraping publisher websites directly;
- Calibre integration;
- PDF/MOBI delivery;
- AI summaries;
- databases;
- Docker or long-running servers;
- backfilling historical issues.
