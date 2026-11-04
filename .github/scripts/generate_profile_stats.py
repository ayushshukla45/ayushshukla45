#!/usr/bin/env python3
"""Generate self-hosted GitHub profile SVG cards using the GitHub GraphQL API.

No third-party card-rendering service is required. The workflow's GITHUB_TOKEN
is used only to read public profile/repository/contribution data.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.sax.saxutils import escape

USERNAME = os.environ.get("GITHUB_USERNAME", "ayushshukla45")
TOKEN = os.environ.get("GITHUB_TOKEN")
OUT = Path("profile")
BG = "#0d1117"
PANEL = "#161b22"
BORDER = "#30363d"
TEXT = "#c9d1d9"
MUTED = "#8b949e"
BLUE = "#58a6ff"
GREEN = "#3fb950"
PURPLE = "#bc8cff"

LANG_COLORS = {
    "Python": "#3572A5", "JavaScript": "#f1e05a", "TypeScript": "#3178c6",
    "C++": "#f34b7d", "C": "#555555", "Java": "#b07219", "Go": "#00ADD8",
    "Rust": "#dea584", "HTML": "#e34c26", "CSS": "#563d7c",
    "Jupyter Notebook": "#DA5B0B", "Shell": "#89e051", "Kotlin": "#A97BFF",
    "Dart": "#00B4AB", "PHP": "#4F5D95", "Ruby": "#701516",
    "Swift": "#F05138", "Vue": "#41b883",
}

def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)

def graphql(query: str, variables: dict) -> dict:
    if not TOKEN:
        fail("GITHUB_TOKEN is missing. Run this script inside the GitHub Actions workflow.")
    payload = json.dumps({"query": query, "variables": variables}).encode()
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.github+json",
            "User-Agent": "github-profile-card-generator",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:1000]
        fail(f"GitHub GraphQL API returned HTTP {exc.code}: {detail}")
    except Exception as exc:
        fail(f"Could not reach GitHub GraphQL API: {exc}")
    if body.get("errors"):
        fail("GitHub GraphQL query failed: " + json.dumps(body["errors"])[:1500])
    if not body.get("data", {}).get("user"):
        fail(f"GitHub user '{USERNAME}' was not found or is not accessible.")
    return body["data"]["user"]

def svg_start(width: int, height: int, title: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">'
        f'<title>{escape(title)}</title>'
        f'<rect width="100%" height="100%" rx="12" fill="{BG}"/>'
    )

def text(x: int, y: int, value: object, size: int = 13, color: str = TEXT,
         weight: int = 400, anchor: str = "start") -> str:
    return (f'<text x="{x}" y="{y}" fill="{color}" font-family="Segoe UI, Ubuntu, '
            f'Arial, sans-serif" font-size="{size}" font-weight="{weight}" '
            f'text-anchor="{anchor}">{escape(str(value))}</text>')

def write_svg(name: str, content: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(content + "</svg>\n", encoding="utf-8")

def render_stats(user: dict, contributions: dict) -> None:
    repo_conn = user["repositories"]
    repos = repo_conn["nodes"]
    stars = sum(r["stargazerCount"] for r in repos)
    forks = sum(r["forkCount"] for r in repos)
    commits = contributions["totalCommitContributions"]
    prs = contributions["totalPullRequestContributions"]
    issues = contributions["totalIssueContributions"]
    total = contributions["contributionCalendar"]["totalContributions"]
    followers = user["followers"]["totalCount"]

    parts = [svg_start(495, 165, f"GitHub statistics for {USERNAME}")]
    parts += [
        text(24, 29, "GitHub Statistics", 15, TEXT, 700),
        f'<line x1="24" y1="43" x2="471" y2="43" stroke="{BORDER}"/>',
    ]
    metrics = [
        (30, 82, str(repo_conn["totalCount"]), "Public repositories", BLUE),
        (265, 82, str(stars), "Stars earned", GREEN),
        (30, 124, str(commits), "Commits · last 365 days", PURPLE),
        (265, 124, str(prs + issues), "PRs & issues · last 365 days", BLUE),
    ]
    for x, y, value, label, color in metrics:
        parts.append(text(x, y, value, 23, color, 700))
        parts.append(text(x, y + 17, label, 11, MUTED))
    parts.append(text(471, 151, f"{followers} followers  ·  {forks} forks  ·  {total} contributions / 365d",
                      10, MUTED, 400, "end"))
    write_svg("stats.svg", "".join(parts))

def render_languages(repos: list[dict]) -> None:
    totals: Counter[str] = Counter()
    for repo in repos:
        lang_data = repo.get("languages") or {}
        for edge in lang_data.get("edges", []):
            node = edge.get("node") or {}
            if node.get("name"):
                totals[node["name"]] += edge.get("size", 0)

    ranked = totals.most_common(6)
    parts = [svg_start(495, 165, f"Most used programming languages for {USERNAME}")]
    parts += [
        text(24, 29, "Most Used Languages", 15, TEXT, 700),
        f'<line x1="24" y1="43" x2="471" y2="43" stroke="{BORDER}"/>',
    ]
    total_size = sum(totals.values())
    if not ranked or total_size == 0:
        parts.append(text(24, 91, "No public language data available yet", 13, MUTED))
    else:
        y = 62
        for name, amount in ranked:
            pct = amount / total_size * 100
            color = LANG_COLORS.get(name, "#8b949e")
            parts.append(text(24, y + 4, name, 11, TEXT, 600))
            parts.append(f'<rect x="150" y="{y-7}" width="250" height="10" rx="5" fill="{BORDER}"/>')
            parts.append(f'<rect x="150" y="{y-7}" width="{250*pct/100:.1f}" height="10" rx="5" fill="{color}"/>')
            parts.append(text(466, y + 4, f"{pct:.1f}%", 11, MUTED, 500, "end"))
            y += 17
    write_svg("top-langs.svg", "".join(parts))

def streak_lengths(days: list[tuple[str, int]]) -> tuple[int, int]:
    dated = [(datetime.strptime(d, "%Y-%m-%d").date(), count) for d, count in days]
    dated.sort(key=lambda item: item[0])
    longest = current_run = 0
    previous = None
    for day, count in dated:
        if count > 0:
            current_run = current_run + 1 if previous and day == previous + timedelta(days=1) else 1
            longest = max(longest, current_run)
        else:
            current_run = 0
        previous = day

    by_date = {day: count for day, count in dated}
    today = datetime.now(timezone.utc).date()
    cursor = today if by_date.get(today, 0) > 0 else today - timedelta(days=1)
    current = 0
    while by_date.get(cursor, 0) > 0:
        current += 1
        cursor -= timedelta(days=1)
    return current, longest

def render_streak(contributions: dict, days: list[tuple[str, int]]) -> None:
    total = contributions["contributionCalendar"]["totalContributions"]
    current, longest = streak_lengths(days)
    period_start = (datetime.now(timezone.utc).date() - timedelta(days=365)).strftime("%b %d, %Y")
    today_label = datetime.now(timezone.utc).strftime("%b %d")
    parts = [svg_start(1000, 180, f"GitHub contribution streak for {USERNAME}")]
    parts += [
        f'<rect x="1" y="1" width="998" height="178" rx="12" fill="{BG}" stroke="{BORDER}"/>',
        f'<line x1="333" y1="28" x2="333" y2="152" stroke="{BORDER}"/>',
        f'<line x1="667" y1="28" x2="667" y2="152" stroke="{BORDER}"/>',
        text(166, 79, total, 36, BLUE, 700, "middle"),
        text(166, 106, "Contributions", 15, TEXT, 500, "middle"),
        text(166, 132, f"{period_start} – present", 12, MUTED, 400, "middle"),
        f'<circle cx="500" cy="77" r="42" fill="none" stroke="{BORDER}" stroke-width="7"/>',
        f'<circle cx="500" cy="77" r="42" fill="none" stroke="{BLUE}" stroke-width="7" '
        f'stroke-linecap="round" stroke-dasharray="{min(current, 365)/365*263.9:.1f} 263.9" '
        f'transform="rotate(-90 500 77)"/>',
        text(500, 86, current, 27, TEXT, 700, "middle"),
        text(500, 137, "Current Streak", 15, TEXT, 700, "middle"),
        text(500, 158, today_label, 12, MUTED, 400, "middle"),
        text(834, 79, longest, 36, BLUE, 700, "middle"),
        text(834, 106, "Longest Streak", 15, TEXT, 500, "middle"),
        text(834, 132, "Last 365 days", 12, MUTED, 400, "middle"),
    ]
    write_svg("streak.svg", "".join(parts))

def main() -> None:
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=365)
    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        login
        followers { totalCount }
        repositories(
          first: 100
          ownerAffiliations: OWNER
          privacy: PUBLIC
          isFork: false
          orderBy: { field: UPDATED_AT, direction: DESC }
        ) {
          totalCount
          nodes {
            stargazerCount
            forkCount
            languages(first: 10, orderBy: { field: SIZE, direction: DESC }) {
              edges { size node { name } }
            }
          }
        }
        contributionsCollection(from: $from, to: $to) {
          totalCommitContributions
          totalPullRequestContributions
          totalIssueContributions
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays { date contributionCount }
            }
          }
        }
      }
    }
    """
    user = graphql(query, {
        "login": USERNAME,
        "from": start.isoformat().replace("+00:00", "Z"),
        "to": now.isoformat().replace("+00:00", "Z"),
    })
    contributions = user["contributionsCollection"]
    days = []
    for week in contributions["contributionCalendar"]["weeks"]:
        for day in week["contributionDays"]:
            days.append((day["date"], day["contributionCount"]))
    render_stats(user, contributions)
    render_languages(user["repositories"]["nodes"])
    render_streak(contributions, days)
    print(f"Generated profile/stats.svg, profile/top-langs.svg and profile/streak.svg for {USERNAME}.")

if __name__ == "__main__":
    main()
