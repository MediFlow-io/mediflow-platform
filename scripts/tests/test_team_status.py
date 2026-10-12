import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import team_status as ts  # noqa: E402

NOW = datetime(2026, 10, 12, 12, tzinfo=timezone.utc)
AREAS = {"web": {"title": "Web", "paths": ["apps/web/"]},
         "api": {"title": "API", "paths": ["apps/core-api/"]},
         "docs": {"title": "Docs", "paths": ["docs/", "README.md"]}}
CONFIG = {"maintainer": "lead", "stale_days": 7, "pr_wait_days": 3, "areas": AREAS, "member": [
    {"github": "lead", "role": "Lead", "areas": ["api"], "task": "Auth"},
    {"github": "amy", "areas": ["web"], "task": "Dashboard"},
    {"github": "idle", "areas": [], "task": ""},
]}


def pr(number, author, *, days=1, checks="passing", review="awaiting review", draft=False, head=None):
    when = NOW - timedelta(days=days)
    return ts.PullRequest(number, f"PR {number}", author, f"https://x/{number}", head or f"{author}/b{number}",
                          draft, when, when, ["web"], checks, review)


def test_real_config_is_valid():
    config = ts.load_config()
    assert config["maintainer"] == "gifted-g1"
    assert not ts.validate_config(config)


def test_validate_config_catches_mistakes():
    bad = {"maintainer": "ghost", "areas": {"a": {"paths": []}},
           "member": [{"github": "x", "areas": ["nope"]}, {"github": "X"}]}
    errors = "\n".join(ts.validate_config(bad))
    assert "duplicate" in errors and "maintainer" in errors and "unknown area 'nope'" in errors and "no paths" in errors


def test_areas_for_paths():
    assert ts.areas_for_paths(["apps/web/src/App.jsx", "README.md"], AREAS) == ["docs", "web"]
    assert ts.areas_for_paths(["scripts/x.py"], AREAS) == []


def test_check_and_review_summaries():
    assert ts.summarize_checks([]) == "none"
    assert ts.summarize_checks([{"status": "completed", "conclusion": "success"},
                                {"status": "completed", "conclusion": "failure"}]) == "failing"
    assert ts.summarize_checks([{"status": "in_progress", "conclusion": None}]) == "running"
    assert ts.summarize_checks([{"status": "completed", "conclusion": "skipped"}]) == "passing"
    reviews = [{"user": {"login": "a"}, "state": "CHANGES_REQUESTED"}, {"user": {"login": "a"}, "state": "APPROVED"}]
    assert ts.summarize_reviews(reviews) == "approved"  # latest review per person wins
    assert ts.summarize_reviews([{"user": {"login": "a"}, "state": "COMMENTED"}]) == "awaiting review"


def test_report_shows_work_and_flags():
    activity = ts.RepoActivity(
        prs=[pr(1, "amy"), pr(2, "amy", checks="failing", days=5), pr(3, "stranger")],
        branches=[ts.Branch("amy/b1", "amy", NOW), ts.Branch("lead/wip", "lead", NOW - timedelta(days=2))],
        issues=[ts.Issue(9, "Fix login", "https://x/9", ["lead"], NOW)])
    report = ts.build_report(CONFIG, activity, NOW)

    assert "🟢 Ready for @lead to merge: [#1]" in report
    assert "🔴 CI failing: [#2]" in report
    assert "⏳ Open 5 days: [#2]" in report
    assert "Branch `lead/wip`" in report and "no PR yet" in report      # branch without PR is surfaced
    assert "Branch `amy/b1`" not in report                                # it has PR #1
    assert "Issue [#9](https://x/9) Fix login" in report
    assert "@idle | - | - | 0 | 0 | never | ⚠️ no task set; no area; no activity yet |" in report
    assert "Nobody owns area **Docs**" in report
    assert "@stranger has activity but isn't in" in report


def test_inactive_member_is_flagged():
    activity = ts.RepoActivity([], [ts.Branch("amy/old", "amy", NOW - timedelta(days=10))], [])
    assert "inactive 7+ days" in ts.build_report(CONFIG, activity, NOW)


def test_commits_on_main_count_as_activity():
    activity = ts.RepoActivity([], [], [], main_commits=[ts.Branch("abc1234", "lead", NOW - timedelta(days=1))])
    assert "| @lead | API | Auth | 0 | 0 | 1 day ago | ✅ |" in ts.build_report(CONFIG, activity, NOW)


def test_draft_prs_are_not_offered_for_merge():
    report = ts.build_report(CONFIG, ts.RepoActivity([pr(4, "amy", draft=True)], [], []), NOW)
    assert "Ready for @lead to merge" not in report
    assert "draft" in report


def test_cli_requires_token(monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    assert ts.main([]) == 2
    assert ts.main(["--check-config"]) == 0
