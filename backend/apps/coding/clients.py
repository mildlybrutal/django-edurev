"""Fetch public coding activity. Only three fixed hosts are ever contacted (no user-supplied URLs,
so no SSRF surface), with short timeouts. Standard library only.

- GitHub: the official REST API (unauthenticated 60 requests/hour; GITHUB_TOKEN raises the limit).
- LeetCode: its public GraphQL endpoint. This is **unofficial**: it may change or rate-limit without
  notice, and the UI labels LeetCode figures as coming from an unofficial source.
- Codeforces: its official public API (https://codeforces.com/apiHelp). It allows roughly one call
  every two seconds per client, so the calls for one profile are spaced out.
"""

import json
import re
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta

from django.conf import settings

GITHUB_API = "https://api.github.com"
LEETCODE_GRAPHQL = "https://leetcode.com/graphql"
CODEFORCES_API = "https://codeforces.com/api"
CODEFORCES_CALL_GAP = 2.1  # seconds between calls (the API's published limit is 1 call / 2 s)
TIMEOUT = 10
USER_AGENT = "placement-readiness/1.0 (+institutional placement platform)"

GITHUB_USERNAME = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
LEETCODE_USERNAME = re.compile(r"^[A-Za-z0-9_-]{1,30}$")
CODEFORCES_HANDLE = re.compile(r"^[A-Za-z0-9_.-]{3,24}$")


class ProfileNotFound(Exception):  # noqa: N818
    pass


class FetchError(Exception):
    pass


def _request(url, *, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:  # noqa: S310 - fixed https hosts only
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise ProfileNotFound from exc
        raise FetchError(f"HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise FetchError(str(exc)[:200]) from exc


def _github_headers():
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    token = getattr(settings, "GITHUB_TOKEN", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def fetch_github(username, now=None):
    """Public profile, owned repositories and recent public events, reduced to the stats the rating uses."""
    if not GITHUB_USERNAME.match(username):
        raise ProfileNotFound
    now = now or datetime.now(UTC)
    headers = _github_headers()
    user = _request(f"{GITHUB_API}/users/{username}", headers=headers)
    repos = _request(f"{GITHUB_API}/users/{username}/repos?per_page=100&sort=pushed&type=owner", headers=headers)
    try:
        events = _request(f"{GITHUB_API}/users/{username}/events/public?per_page=100", headers=headers)
    except FetchError:
        events = []
    since = now - timedelta(days=90)
    own = [r for r in repos if not r.get("fork")]
    languages = {}
    for r in own:
        if r.get("language"):
            languages[r["language"]] = languages.get(r["language"], 0) + 1
    recent_pushes = sum(
        1
        for e in events
        if e.get("type") == "PushEvent" and _parse(e.get("created_at")) and _parse(e["created_at"]) >= since
    )
    active_repos = sum(1 for r in own if _parse(r.get("pushed_at")) and _parse(r["pushed_at"]) >= since)
    return {
        "username": user.get("login", username),
        "profile_url": user.get("html_url", f"https://github.com/{username}"),
        "public_repos": user.get("public_repos", 0),
        "original_repos": len(own),
        "stars": sum(r.get("stargazers_count", 0) for r in own),
        "followers": user.get("followers", 0),
        "languages": dict(sorted(languages.items(), key=lambda kv: -kv[1])),
        "recent_push_events": recent_pushes,
        "repos_pushed_90d": active_repos,
        "account_created": user.get("created_at"),
        "top_repos": [
            {
                "name": r["name"],
                "language": r.get("language"),
                "stars": r.get("stargazers_count", 0),
                "pushed_at": r.get("pushed_at"),
                "url": r.get("html_url"),
            }
            for r in sorted(own, key=lambda r: (-r.get("stargazers_count", 0), r.get("pushed_at") or ""))[:5]
        ],
    }


LEETCODE_QUERY = """
query profile($username: String!) {
  matchedUser(username: $username) {
    username
    profile { ranking }
    submitStatsGlobal { acSubmissionNum { difficulty count } }
  }
  userContestRanking(username: $username) { rating attendedContestsCount topPercentage }
}
"""


def fetch_leetcode(username):
    """Solved counts by difficulty and contest rating from LeetCode's public (unofficial) GraphQL."""
    if not LEETCODE_USERNAME.match(username):
        raise ProfileNotFound
    body = json.dumps({"query": LEETCODE_QUERY, "variables": {"username": username}}).encode()
    data = _request(
        LEETCODE_GRAPHQL,
        data=body,
        headers={"Content-Type": "application/json", "Referer": f"https://leetcode.com/u/{username}/"},
    )
    payload = data.get("data") or {}
    user = payload.get("matchedUser")
    if not user:
        raise ProfileNotFound
    solved = {row["difficulty"].lower(): row["count"] for row in user["submitStatsGlobal"]["acSubmissionNum"]}
    contest = payload.get("userContestRanking") or {}
    return {
        "username": user["username"],
        "profile_url": f"https://leetcode.com/u/{user['username']}/",
        "solved_easy": solved.get("easy", 0),
        "solved_medium": solved.get("medium", 0),
        "solved_hard": solved.get("hard", 0),
        "solved_total": solved.get("all", 0),
        "ranking": (user.get("profile") or {}).get("ranking"),
        "contest_rating": round(contest["rating"]) if contest.get("rating") else None,
        "contests_attended": contest.get("attendedContestsCount") or 0,
        "contest_top_percentage": contest.get("topPercentage"),
        "source": "leetcode.com public GraphQL (unofficial)",
    }


def _codeforces(method, **params):
    """Call one Codeforces API method. It answers HTTP 400 with status FAILED for an unknown handle."""
    query = "&".join(f"{k}={v}" for k, v in params.items())
    try:
        data = _request(f"{CODEFORCES_API}/{method}?{query}")
    except FetchError as exc:
        if "HTTP 400" in str(exc):
            raise ProfileNotFound from exc
        raise
    if data.get("status") != "OK":
        comment = str(data.get("comment", ""))
        if "not found" in comment:
            raise ProfileNotFound
        raise FetchError(comment[:200] or "Codeforces API error")
    return data["result"]


def fetch_codeforces(handle, pause=time.sleep):
    """Rating, rank, contest count and distinct solved problems (by problem rating) from the
    official Codeforces API."""
    if not CODEFORCES_HANDLE.match(handle):
        raise ProfileNotFound
    users = _codeforces("user.info", handles=handle)
    if not users:
        raise ProfileNotFound
    user = users[0]
    pause(CODEFORCES_CALL_GAP)
    contests = _codeforces("user.rating", handle=handle)
    pause(CODEFORCES_CALL_GAP)
    submissions = _codeforces("user.status", handle=handle)
    solved = {}
    for sub in submissions:
        if sub.get("verdict") != "OK":
            continue
        problem = sub.get("problem") or {}
        key = (problem.get("contestId"), problem.get("problemsetName"), problem.get("index"), problem.get("name"))
        solved[key] = problem.get("rating")
    rated = [r for r in solved.values() if r]
    real_handle = user.get("handle", handle)
    return {
        "username": real_handle,
        "profile_url": f"https://codeforces.com/profile/{real_handle}",
        "rating": user.get("rating"),
        "max_rating": user.get("maxRating"),
        "rank": user.get("rank"),
        "max_rank": user.get("maxRank"),
        "contests_attended": len(contests),
        "solved_total": len(solved),
        "solved_1600_plus": sum(1 for r in rated if r >= 1600),
        "median_solved_rating": sorted(rated)[len(rated) // 2] if rated else None,
        "source": "codeforces.com official API",
    }


def _parse(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
