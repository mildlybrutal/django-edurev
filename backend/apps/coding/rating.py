"""Explainable coding-activity ratings (0-100). Implementation choice, documented in
docs/scoring-policy.md §9; nothing here comes from the P06 specification.

Each rating is a weighted sum of saturating components, so one huge number (stars, problem count)
cannot dominate, and every component is reported with its value, cap and contribution.
"""

import math

from apps.taxonomy.models import Level


def _component(key, label, value, cap, weight, display=None):
    share = min(1.0, max(0.0, value / cap)) if cap else 0.0
    return {
        "key": key,
        "label": label,
        "value": display if display is not None else value,
        "cap": cap,
        "weight": weight,
        "points": round(100 * weight * share, 1),
    }


def github_rating(stats):
    """Recent activity, original work, breadth and recognition."""
    stars_log = math.log10(1 + stats.get("stars", 0))
    parts = [
        _component("activity", "Push events in the last 90 days", stats.get("recent_push_events", 0), 30, 0.35),
        _component("original", "Original (non-fork) repositories", stats.get("original_repos", 0), 10, 0.25),
        _component("breadth", "Languages across repositories", len(stats.get("languages", {})), 5, 0.20),
        _component("maintained", "Repositories pushed in the last 90 days", stats.get("repos_pushed_90d", 0), 5, 0.10),
        _component("stars", "Stars received (log scale)", stars_log, 2, 0.10, display=stats.get("stars", 0)),
    ]
    score = round(sum(p["points"] for p in parts), 2)
    return score, {
        "summary": "Public GitHub activity: recent pushes, original repositories, language breadth, maintenance "
        "and stars. Each part saturates at its cap.",
        "components": parts,
    }


def leetcode_rating(stats):
    """Problem-solving volume weighted by difficulty, plus contest performance when present."""
    weighted = stats.get("solved_easy", 0) + 2 * stats.get("solved_medium", 0) + 3 * stats.get("solved_hard", 0)
    rating = stats.get("contest_rating")
    contest_value = max(0, (rating or 0) - 1200)
    if rating:
        parts = [
            _component("solved", "Solved, weighted easy×1 · medium×2 · hard×3", weighted, 600, 0.70),
            _component("contest", "Contest rating above 1200", contest_value, 1000, 0.30, display=rating),
        ]
    else:
        parts = [_component("solved", "Solved, weighted easy×1 · medium×2 · hard×3", weighted, 600, 1.0)]
    score = round(sum(p["points"] for p in parts), 2)
    return score, {
        "summary": "LeetCode problem solving (unofficial public data): difficulty-weighted solved count"
        + (" and contest rating." if rating else "; no contest history."),
        "components": parts,
    }


def codeforces_rating(stats):
    """Distinct problems solved, harder problems solved, and contest rating when the user is rated."""
    rating = stats.get("rating")
    solved = _component("solved", "Distinct problems solved", stats.get("solved_total", 0), 300, 0.45)
    hard = _component("hard", "Problems rated 1600+ solved", stats.get("solved_1600_plus", 0), 50, 0.20)
    if rating:
        parts = [
            solved,
            hard,
            _component("contest", "Contest rating above 800", max(0, rating - 800), 1200, 0.35, display=rating),
        ]
    else:
        solved = _component("solved", "Distinct problems solved", stats.get("solved_total", 0), 300, 0.70)
        hard = _component("hard", "Problems rated 1600+ solved", stats.get("solved_1600_plus", 0), 50, 0.30)
        parts = [solved, hard]
    score = round(sum(p["points"] for p in parts), 2)
    return score, {
        "summary": "Codeforces problem solving (official public API): distinct problems solved, problems rated "
        "1600 or more" + (", and contest rating." if rating else "; not yet rated in contests."),
        "components": parts,
    }


def leetcode_dsa_level(stats):
    """Level a student may *claim* for DSA from a solved-problem count (LeetCode or Codeforces).
    Evidence rules still cap unverified external evidence (Beginner by default), so this never
    becomes expertise without verification."""
    solved = stats.get("solved_total", 0)
    if solved >= 500:
        return Level.EXPERT
    if solved >= 200:
        return Level.ADVANCED
    if solved >= 50:
        return Level.INTERMEDIATE
    return Level.BEGINNER


def github_language_levels(stats):
    """{language: claimed level} from how many original repositories use it."""
    return {
        lang: (Level.INTERMEDIATE if count >= 3 else Level.BEGINNER)
        for lang, count in stats.get("languages", {}).items()
    }
