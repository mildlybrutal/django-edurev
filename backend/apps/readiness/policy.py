"""Scoring primitives shared by readiness and matching. Pure functions, no database access."""

from decimal import Decimal

MAX_LEVEL = 4


def credited_level(level, verified_level, unverified_multiplier):
    """Level credited for scoring: the verified part counts fully, the part supported only by
    unverified evidence counts at `unverified_multiplier`."""
    verified_part = min(verified_level, level)
    return verified_part + float(unverified_multiplier) * (level - verified_part)


def weighted_overall(scores, weights):
    total_weight = sum(weights.values())
    if total_weight == 0:
        return 0.0
    return sum(scores[d] * weights[d] for d in weights) / total_weight


def q2(value):
    return Decimal(str(round(float(value), 2)))
