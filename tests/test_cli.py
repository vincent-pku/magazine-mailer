from magazine_mailer.__main__ import issue_status
from magazine_mailer.service import RunResult


def test_issue_status_reports_failed_instead_of_unchanged():
    result = RunResult(
        latest={"wired": "2026.08.02"},
        failures={"wired": "download failed"},
    )

    assert issue_status("wired", result) == "failed"


def test_issue_status_distinguishes_new_and_unchanged():
    discovered = RunResult(
        latest={"economist": "2026.08.29"},
        discovered=["economist"],
    )
    unchanged = RunResult(
        latest={"economist": "2026.08.29"},
        skipped=["economist"],
    )

    assert issue_status("economist", discovered) == "new"
    assert issue_status("economist", unchanged) == "unchanged"
