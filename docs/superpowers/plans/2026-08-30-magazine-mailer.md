# Magazine Mailer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a tested Python application and GitHub Actions workflow that detects and emails new EPUB issues from `hehonghui/awesome-english-ebooks` exactly once.

**Architecture:** A source adapter produces normalized `Issue` objects; a reusable EPUB validator, JSON state store, and SMTP delivery adapter are orchestrated by a service layer. GitHub Actions runs tests, performs discovery/delivery, and commits state changes back to `main` only after successful non-dry runs.

**Tech Stack:** Python 3.12, Python standard library, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-30-magazine-mailer-design.md`

## Global Constraints

- V1 source is only `hehonghui/awesome-english-ebooks`.
- Supported magazines are Economist, New Yorker, Atlantic, and Wired.
- EPUB is the only delivery format.
- No Docker, database, Calibre, AI summaries, publisher-site scraping, or historical backfill.
- First real run sends only the current latest issue for each magazine.
- Economist stale threshold is strictly more than 10 days.
- Delivery state advances only after successful SMTP delivery.
- Dry-run performs discovery and reporting but sends no mail and writes no state.

---

### Task 1: Package foundation and source adapter

**Files:**
- Create: `pyproject.toml`
- Create: `src/magazine_mailer/__init__.py`
- Create: `src/magazine_mailer/models.py`
- Create: `src/magazine_mailer/catalog.py`
- Create: `src/magazine_mailer/sources/__init__.py`
- Create: `src/magazine_mailer/sources/base.py`
- Create: `src/magazine_mailer/sources/awesome.py`
- Test: `tests/test_awesome_source.py`

**Interfaces:**
- Produces `MagazineSpec`, `Issue`, `MAGAZINES`, `MagazineSource`, `AwesomeEnglishEbooksSource.latest_issue(spec)`.

- [ ] **Step 1: Write failing source tests** covering newest directory selection, Economist prefix normalization, EPUB preference, GitHub token header, and missing EPUB failure.
- [ ] **Step 2: Run `python -m pytest tests/test_awesome_source.py -q`** and verify failure because package/source code does not exist.
- [ ] **Step 3: Implement minimal package/model/catalog/source code** using `urllib.request` and JSON responses. `Issue.issue_id` is normalized to `YYYY.MM.DD` for all four magazines; `Issue.issue_date` is a `date`.
- [ ] **Step 4: Re-run source tests** and verify all pass.
- [ ] **Step 5: Run full test suite** and verify green.
- [ ] **Step 6: Commit** with `feat: add magazine source adapter`.

### Task 2: EPUB download and structural validation

**Files:**
- Create: `src/magazine_mailer/epub.py`
- Test: `tests/test_epub.py`

**Interfaces:**
- Produces `download_epub(url, token=None) -> bytes` and `validate_epub(payload: bytes) -> None` raising `EpubValidationError` on invalid content.

- [ ] **Step 1: Write failing tests** for minimum size, ZIP validity, mimetype, container path, OPF presence, three-content-document minimum, and token-aware download headers.
- [ ] **Step 2: Run `python -m pytest tests/test_epub.py -q`** and confirm RED for missing implementation.
- [ ] **Step 3: Implement minimal validator/downloader** with `zipfile`, `xml.etree.ElementTree`, and `urllib.request`.
- [ ] **Step 4: Re-run EPUB tests** and verify green.
- [ ] **Step 5: Run full suite** and verify green.
- [ ] **Step 6: Commit** with `feat: validate downloaded epubs`.

### Task 3: Persistent state and stale-alert rules

**Files:**
- Create: `src/magazine_mailer/state.py`
- Create: `state/state.json`
- Test: `tests/test_state.py`
- Test: `tests/test_stale.py`

**Interfaces:**
- Produces `StateStore.load()`, `StateStore.save(state)`, `mark_sent`, `should_alert_economist_stale`, and `mark_stale_alerted`.

- [ ] **Step 1: Write failing state tests** for schema initialization, materializing all magazines, atomic JSON writes, sent timestamps, and no accidental mutation of defaults.
- [ ] **Step 2: Write failing stale tests** proving 10 days is not stale, 11 days is stale, same-issue alerts are suppressed, and a newer issue clears suppression.
- [ ] **Step 3: Run `python -m pytest tests/test_state.py tests/test_stale.py -q`** and verify RED.
- [ ] **Step 4: Implement minimal state/stale logic** using UTC ISO-8601 timestamps and temp-file `os.replace` atomic persistence.
- [ ] **Step 5: Re-run focused and full tests** and verify green.
- [ ] **Step 6: Commit** with `feat: persist delivery state`.

### Task 4: SMTP delivery adapter

**Files:**
- Create: `src/magazine_mailer/email_delivery.py`
- Test: `tests/test_email_delivery.py`

**Interfaces:**
- Produces `SmtpConfig.from_env()`, `EmailDelivery.send_issue(issue, payload)`, and `EmailDelivery.send_stale_alert(issue, age_days)`.

- [ ] **Step 1: Write failing tests** for required environment variables, Gmail-friendly defaults, MIME attachment filename/type, issue subject, stale-alert subject/body, STARTTLS/login/send sequence, and absence of secret values in exceptions.
- [ ] **Step 2: Run `python -m pytest tests/test_email_delivery.py -q`** and verify RED.
- [ ] **Step 3: Implement minimal SMTP adapter** with `smtplib.SMTP` and `email.message.EmailMessage`.
- [ ] **Step 4: Re-run focused and full tests** and verify green.
- [ ] **Step 5: Commit** with `feat: deliver magazine email`.

### Task 5: Orchestration and CLI

**Files:**
- Create: `src/magazine_mailer/service.py`
- Create: `src/magazine_mailer/__main__.py`
- Test: `tests/test_service.py`

**Interfaces:**
- Produces `MagazineMailer.run(dry_run: bool, today: date | None = None) -> RunResult` and CLI `python -m magazine_mailer [--dry-run]`.

- [ ] **Step 1: Write failing service tests** for duplicate suppression, first-run current issue delivery, state update only after send, dry-run no send/no state mutation, per-magazine failure isolation, final failure result, and one-time Economist stale alert.
- [ ] **Step 2: Run `python -m pytest tests/test_service.py -q`** and verify RED.
- [ ] **Step 3: Implement minimal orchestration and CLI**, constructing production dependencies from environment only when not dry-running.
- [ ] **Step 4: Re-run focused and full tests** and verify green.
- [ ] **Step 5: Commit** with `feat: orchestrate magazine delivery`.

### Task 6: GitHub Actions, documentation, and live verification

**Files:**
- Create: `.github/workflows/deliver.yml`
- Create: `README.md`
- Create: `.gitignore`
- Test: `tests/test_workflow_contract.py`

**Interfaces:**
- Workflow supports scheduled real runs and manual `dry_run=true|false` execution.

- [ ] **Step 1: Write failing workflow-contract tests** asserting schedule `17 */6 * * *`, `workflow_dispatch` dry-run default true, Python 3.12, `contents: write`, tests-before-run, automatic `GITHUB_TOKEN`, SMTP secret wiring, concurrency, and state-only commit behavior.
- [ ] **Step 2: Run `python -m pytest tests/test_workflow_contract.py -q`** and verify RED because workflow is absent.
- [ ] **Step 3: Implement workflow, README, and `.gitignore`**. Scheduled runs pass no `--dry-run`; manual runs add `--dry-run` only when input is true. State commit runs only for successful non-dry execution and only when `state/state.json` changed.
- [ ] **Step 4: Re-run full tests** and verify green.
- [ ] **Step 5: Run `python -m magazine_mailer --dry-run` against live upstream** and verify all four latest issues are discovered without email or state mutation.
- [ ] **Step 6: Run `python -m compileall -q src`** and verify success.
- [ ] **Step 7: Commit** with `ci: automate magazine delivery`.

### Task 7: Final verification and remote publication

**Files:**
- No production-file changes expected unless verification finds a defect.

**Interfaces:**
- Produces a clean `main` branch ready to push, then a GitHub repository and runnable Actions workflow when remote write access is available.

- [ ] **Step 1: Run `python -m pytest -q`** and record exact pass count.
- [ ] **Step 2: Run live `--dry-run` again** and confirm discovered issue IDs match current upstream.
- [ ] **Step 3: Run `git status --short` and `git log --oneline -n 10`** and confirm clean history.
- [ ] **Step 4: Attempt GitHub repository creation/push using the connected GitHub capability; if unavailable, test for an authenticated local Git/CLI credential without exposing secrets.**
- [ ] **Step 5: Once remote exists, trigger a manual dry run and verify the Action reaches the application step without SMTP Secrets.**
- [ ] **Step 6: For real delivery, require only `MAIL_USERNAME`, `MAIL_PASSWORD`, and `MAIL_TO` repository Secrets; do not request or expose them in source code or logs.**
