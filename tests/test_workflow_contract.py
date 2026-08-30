from pathlib import Path


WORKFLOW = Path(".github/workflows/deliver.yml")


def workflow_text():
    return WORKFLOW.read_text(encoding="utf-8")


def test_workflow_has_schedule_and_safe_manual_dry_run_default():
    text = workflow_text()

    assert "cron: '17 */6 * * *'" in text
    assert "workflow_dispatch:" in text
    assert "dry_run:" in text
    assert "default: true" in text
    assert "type: boolean" in text


def test_workflow_uses_python_312_and_runs_tests_before_application():
    text = workflow_text()

    assert "python-version: '3.12'" in text
    test_index = text.index("python -m pytest -q")
    app_index = text.index("python -m magazine_mailer")
    assert test_index < app_index


def test_workflow_has_write_permission_and_concurrency_guard():
    text = workflow_text()

    assert "permissions:" in text
    assert "contents: write" in text
    assert "concurrency:" in text
    assert "group: magazine-mailer" in text
    assert "cancel-in-progress: false" in text


def test_workflow_wires_github_token_and_smtp_secrets():
    text = workflow_text()

    assert "GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}" in text
    assert "MAIL_USERNAME: ${{ secrets.MAIL_USERNAME }}" in text
    assert "MAIL_PASSWORD: ${{ secrets.MAIL_PASSWORD }}" in text
    assert "MAIL_TO: ${{ secrets.MAIL_TO }}" in text


def test_workflow_commits_only_state_file_after_non_dry_success():
    text = workflow_text()

    assert "inputs.dry_run == false" in text
    assert "git diff --quiet -- state/state.json" in text
    assert "git add state/state.json" in text
    assert "git add ." not in text
    assert 'git commit -m "chore: update magazine delivery state"' in text
    assert "git push origin HEAD:main" in text
