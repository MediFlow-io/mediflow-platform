#!/usr/bin/env python3
"""Who is working on what in MediFlow.

Reads everyone's areas and tasks from .github/team.toml, adds live GitHub activity
(open PRs, branches without a PR, assigned issues, CI and review state) and
produces a Markdown report that flags what needs attention.

Usage (Python 3.11+, standard library only):
    GITHUB_TOKEN=$(gh auth token) python scripts/team_status.py              # print report
    GITHUB_TOKEN=$(gh auth token) python scripts/team_status.py --update-issue
    python scripts/team_status.py --check-config                             # validate team.toml

The scheduled workflow .github/workflows/team-status.yml runs it with --update-issue,
keeping a single "Team status" issue up to date.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tomllib
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

DEFAULT_REPO = "MediFlow-io/mediflow-platform"
CONFIG_PATH = Path(__file__).resolve().parent.parent / ".github" / "team.toml"
ISSUE_LABEL = "team-status"
ISSUE_TITLE = "📋 Team status: who is working on what"
API = "https://api.github.com"


# ----------------------------------------------------------------------------- config

def load_config(path: Path = CONFIG_PATH) -> dict:
    with open(path, "rb") as handle:
        config = tomllib.load(handle)
    errors = validate_config(config)
    if errors:
        raise SystemExit("team.toml is invalid:\n  - " + "\n  - ".join(errors))
    return config


def validate_config(config: dict) -> list[str]:
    errors = []
    areas = config.get("areas", {})
    members = config.get("member", [])
    logins = [m.get("github", "") for m in members]
    if not members:
        errors.append("no [[member]] entries")
    if len(set(map(str.lower, logins))) != len(logins):
        errors.append("duplicate github usernames")
    if config.get("maintainer") not in logins:
        errors.append("maintainer must also be listed as a [[member]]")
    for member in members:
        if not member.get("github"):
            errors.append("a member is missing 'github'")
        for area in member.get("areas", []):
            if area not in areas:
                errors.append(f"@{member.get('github')}: unknown area '{area}'")
    for key, area in areas.items():
        if not area.get("paths"):
            errors.append(f"area '{key}' has no paths")
    return errors


def areas_for_paths(paths: list[str], areas: dict) -> list[str]:
    hits = set()
    for path in paths:
        for key, area in areas.items():
            if any(path == p or path.startswith(p) for p in area["paths"]):
                hits.add(key)
    return sorted(hits)


# ----------------------------------------------------------------------------- data

@dataclass
class PullRequest:
    number: int
    title: str
    author: str
    url: str
    head: str
    draft: bool
    created_at: datetime
    updated_at: datetime
    areas: list[str] = field(default_factory=list)
    checks: str = "none"        # passing | failing | running | none
    review: str = "awaiting review"  # approved | changes requested | awaiting review


@dataclass
class Branch:
    name: str
    author: str
    date: datetime


@dataclass
class Issue:
    number: int
    title: str
    url: str
    assignees: list[str]
    updated_at: datetime


@dataclass
class RepoActivity:
    prs: list[PullRequest]
    branches: list[Branch]
    issues: list[Issue]
    main_commits: list[Branch] = field(default_factory=list)  # recent commits on main (name = sha)


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class GitHub:
    def __init__(self, repo: str, token: str):
        self.repo, self.token = repo, token

    def request(self, method: str, url: str, body: dict | None = None):
        if not url.startswith("http"):
            url = f"{API}/repos/{self.repo}{url}"
        req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body else None, headers={
            "Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "mediflow-team-status"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            link = resp.headers.get("Link", "")
            return json.loads(resp.read() or "null"), link

    def get_all(self, url: str) -> list:
        items, sep = [], "&" if "?" in url else "?"
        url = f"{url}{sep}per_page=100"
        while url:
            page, link = self.request("GET", url)
            items.extend(page)
            match = re.search(r'<([^>]+)>;\s*rel="next"', link)
            url = match.group(1) if match else None
        return items


def summarize_checks(runs: list[dict]) -> str:
    if not runs:
        return "none"
    if any(r.get("conclusion") in ("failure", "cancelled", "timed_out", "action_required") for r in runs):
        return "failing"
    if any(r.get("status") != "completed" for r in runs):
        return "running"
    return "passing"


def summarize_reviews(reviews: list[dict]) -> str:
    latest: dict[str, str] = {}
    for review in reviews:  # API returns them oldest first
        if review.get("state") in ("APPROVED", "CHANGES_REQUESTED", "DISMISSED"):
            latest[review["user"]["login"]] = review["state"]
    states = set(latest.values())
    if "CHANGES_REQUESTED" in states:
        return "changes requested"
    if "APPROVED" in states:
        return "approved"
    return "awaiting review"


def collect(gh: GitHub, areas: dict) -> RepoActivity:
    prs = []
    for raw in gh.get_all("/pulls?state=open"):
        files = [f["filename"] for f in gh.get_all(f"/pulls/{raw['number']}/files")]
        runs, _ = gh.request("GET", f"/commits/{raw['head']['sha']}/check-runs?per_page=100")
        prs.append(PullRequest(
            number=raw["number"], title=raw["title"], author=raw["user"]["login"], url=raw["html_url"],
            head=raw["head"]["ref"], draft=raw.get("draft", False),
            created_at=parse_time(raw["created_at"]), updated_at=parse_time(raw["updated_at"]),
            areas=areas_for_paths(files, areas), checks=summarize_checks(runs.get("check_runs", [])),
            review=summarize_reviews(gh.get_all(f"/pulls/{raw['number']}/reviews"))))

    branches = []
    for raw in gh.get_all("/branches"):
        if raw["name"] == "main":
            continue
        commit, _ = gh.request("GET", f"/commits/{raw['commit']['sha']}")
        login = (commit.get("author") or {}).get("login") or (commit.get("committer") or {}).get("login")
        if login:
            # Author date = when the work was written (survives rebases and migrations).
            branches.append(Branch(raw["name"], login, parse_time(commit["commit"]["author"]["date"])))

    issues = [Issue(i["number"], i["title"], i["html_url"], [a["login"] for a in i.get("assignees", [])],
                    parse_time(i["updated_at"]))
              for i in gh.get_all("/issues?state=open") if "pull_request" not in i]
    since = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(days=30)
    main_commits = [Branch(c["sha"][:7], c["author"]["login"], parse_time(c["commit"]["committer"]["date"]))
                    for c in gh.get_all(f"/commits?sha=main&since={since.isoformat().replace('+00:00', 'Z')}")
                    if c.get("author")]
    return RepoActivity(prs, branches, issues, main_commits)


# ----------------------------------------------------------------------------- report

def days_ago(when: datetime, now: datetime) -> int:
    return max(0, (now - when).days)


def human_age(when: datetime | None, now: datetime) -> str:
    if when is None:
        return "never"
    days = days_ago(when, now)
    return "today" if days == 0 else "1 day ago" if days == 1 else f"{days} days ago"


def build_report(config: dict, activity: RepoActivity, now: datetime) -> str:
    areas, members = config["areas"], config["member"]
    stale_days, wait_days = config.get("stale_days", 7), config.get("pr_wait_days", 3)
    known = {m["github"].lower() for m in members}
    pr_heads = {pr.head for pr in activity.prs}

    def mine(items, attr):
        return lambda login: [x for x in items if getattr(x, attr).lower() == login.lower()]
    prs_of, branches_of = mine(activity.prs, "author"), mine(activity.branches, "author")

    def issues_of(login):
        return [i for i in activity.issues if login.lower() in (a.lower() for a in i.assignees)]

    rows, details, attention = [], [], []
    for m in members:
        login = m["github"]
        prs, issues = prs_of(login), issues_of(login)
        lone_branches = [b for b in branches_of(login) if b.name not in pr_heads]
        merged = [c.date for c in activity.main_commits if c.author.lower() == login.lower()]
        dates = [p.updated_at for p in prs] + [b.date for b in branches_of(login)] + [i.updated_at for i in issues] + merged
        last = max(dates) if dates else None

        flags = []
        if not m.get("task"):
            flags.append("no task set")
        if not m.get("areas"):
            flags.append("no area")
        if last is None or days_ago(last, now) >= stale_days:
            flags.append(f"inactive {stale_days}+ days" if last else "no activity yet")
        if lone_branches:
            flags.append(f"{len(lone_branches)} branch(es) without PR")
        area_names = ", ".join(areas[a]["title"] for a in m.get("areas", [])) or "-"
        rows.append(f"| @{login} | {area_names} | {m.get('task') or '-'} | {len(prs)} | {len(lone_branches)} "
                    f"| {human_age(last, now)} | {'⚠️ ' + '; '.join(flags) if flags else '✅'} |")

        lines = [f"### @{login}" + (f" · {m['role']}" if m.get("role") else ""),
                 f"**Task:** {m.get('task') or '_not set: edit `.github/team.toml`_'}"]
        for pr in prs:
            lines.append(f"- PR [#{pr.number}]({pr.url}) {pr.title} · {', '.join(pr.areas) or 'no area'} · "
                         f"CI {pr.checks} · {pr.review}{' · draft' if pr.draft else ''} · opened {human_age(pr.created_at, now)}")
        for b in lone_branches:
            lines.append(f"- Branch `{b.name}` · last commit {human_age(b.date, now)} · **no PR yet**")
        for i in issues:
            lines.append(f"- Issue [#{i.number}]({i.url}) {i.title}")
        if not (prs or lone_branches or issues):
            lines.append("- _No open PRs, branches or assigned issues._")
        details.append("\n".join(lines))

    for pr in sorted(activity.prs, key=lambda p: p.created_at):
        ref = f"[#{pr.number}]({pr.url}) {pr.title} (@{pr.author})"
        if pr.draft:
            continue
        if pr.checks == "failing":
            attention.append(f"🔴 CI failing: {ref}")
        elif pr.review == "changes requested":
            attention.append(f"🟠 Changes requested: {ref}")
        elif pr.checks == "passing":
            attention.append(f"🟢 Ready for @{config['maintainer']} to merge: {ref}")
        if days_ago(pr.created_at, now) >= wait_days:
            attention.append(f"⏳ Open {days_ago(pr.created_at, now)} days: {ref}")

    owned = {a for m in members for a in m.get("areas", [])}
    for key in sorted(set(areas) - owned):
        attention.append(f"👤 Nobody owns area **{areas[key]['title']}**")
    outsiders = sorted({x.author for x in [*activity.prs, *activity.branches] if x.author.lower() not in known})
    for login in outsiders:
        attention.append(f"❔ @{login} has activity but isn't in `.github/team.toml`")

    lone_total = sum(1 for b in activity.branches if b.name not in pr_heads)
    return "\n".join([
        "# 📋 MediFlow team status", "",
        f"_Updated {now:%Y-%m-%d %H:%M} UTC · {len(activity.prs)} open PRs · "
        f"{lone_total} branches without a PR · generated by `scripts/team_status.py`_", "",
        "## Needs attention", "",
        *([f"- {a}" for a in attention] or ["- Nothing. 🎉"]), "",
        "## Overview", "",
        "| Member | Areas | Current task | Open PRs | Branches w/o PR | Last activity | Status |",
        "|---|---|---|:-:|:-:|---|---|",
        *rows, "",
        "## Details", "",
        "\n\n".join(details), "",
        "---",
        "_To change your task or areas, edit `.github/team.toml` in a PR. "
        "Branch names: `<github-username>/<area>-<topic>`._",
    ])


# ----------------------------------------------------------------------------- issue

def upsert_issue(gh: GitHub, body: str) -> str:
    try:
        gh.request("POST", "/labels", {"name": ISSUE_LABEL, "color": "0e8a16",
                                       "description": "Auto-updated team status report"})
    except urllib.error.HTTPError as error:
        if error.code != 422:  # 422 = label already exists
            raise
    existing = gh.get_all(f"/issues?state=open&labels={ISSUE_LABEL}")
    if existing:
        issue, _ = gh.request("PATCH", f"/issues/{existing[0]['number']}", {"body": body})
    else:
        issue, _ = gh.request("POST", "/issues", {"title": ISSUE_TITLE, "body": body, "labels": [ISSUE_LABEL]})
    return issue["html_url"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", default=os.getenv("GITHUB_REPOSITORY", DEFAULT_REPO))
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    parser.add_argument("--update-issue", action="store_true", help="create/update the Team status issue")
    parser.add_argument("--check-config", action="store_true", help="only validate team.toml")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    if args.check_config:
        print(f"team.toml OK: {len(config['member'])} members, {len(config['areas'])} areas")
        return 0

    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if not token:
        print("Set GITHUB_TOKEN (for example: GITHUB_TOKEN=$(gh auth token) python scripts/team_status.py)",
              file=sys.stderr)
        return 2
    gh = GitHub(args.repo, token)
    report = build_report(config, collect(gh, config["areas"]), datetime.now(timezone.utc))

    if summary := os.getenv("GITHUB_STEP_SUMMARY"):
        Path(summary).write_text(report, encoding="utf-8")
    if args.update_issue:
        print(f"Updated {upsert_issue(gh, report)}")
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
