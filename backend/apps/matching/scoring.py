"""Compatibility and gap scoring. Pure functions over pre-loaded data so a 5,000-student batch
needs a fixed number of queries. The formula is an implementation choice (docs/scoring-policy.md):

    credit_i       = min(credited_level_i / required_level_i, 1)
    compatibility  = Σ credit_i × weight_i / Σ weight_i × 100

where credited_level counts verified evidence fully and unverified evidence at the configured
multiplier, and a student skill satisfies a requirement when it is the required skill or lies
below it in the taxonomy (React satisfies "Frontend Framework").
"""

from apps.readiness.policy import credited_level
from apps.taxonomy.models import Level

from .models import GapKind, Impact


def _level_label(level):
    return Level(int(level)).label


def score_requirement(requirement, claims_by_skill, satisfying_ids, depth_of, multiplier):
    """Best evidence for one requirement. `claims_by_skill` maps skill id -> claim for one student."""
    best = None
    for skill_id in satisfying_ids:
        claim = claims_by_skill.get(skill_id)
        if claim is None:
            continue
        credited = credited_level(claim.level, claim.verified_level, multiplier)
        if best is None or credited > best[0]:
            best = (credited, claim)
    required = max(requirement.required_level, 1)
    if best is None:
        return {
            "skill_id": requirement.skill_id,
            "skill": requirement.skill.name,
            "required_level": required,
            "weight": requirement.weight,
            "is_mandatory": requirement.is_mandatory,
            "match": "none",
            "matched_skill": None,
            "level": 0,
            "verified_level": 0,
            "credit": 0.0,
        }
    credited, claim = best
    exact = claim.skill_id == requirement.skill_id
    return {
        "skill_id": requirement.skill_id,
        "skill": requirement.skill.name,
        "required_level": required,
        "weight": requirement.weight,
        "is_mandatory": requirement.is_mandatory,
        "match": "exact" if exact else "taxonomy",
        "matched_skill": claim.skill.name,
        "taxonomy_depth": depth_of.get(claim.skill_id, 0),
        "level": claim.level,
        "verified_level": claim.verified_level,
        "credit": round(min(credited / required, 1.0), 4),
    }


def compatibility(breakdown):
    total = sum(r["weight"] for r in breakdown)
    if not total:
        return 0.0
    return 100 * sum(r["credit"] * r["weight"] for r in breakdown) / total


def technical_explanation(breakdown, score, multiplier):
    return {
        "summary": f"Skill match against this drive's {len(breakdown)} requirement(s), weighted by importance "
        f"(unverified evidence counts at {float(multiplier):.0%}).",
        "inputs": [
            {
                "skill": r["skill"],
                "required": _level_label(r["required_level"]),
                "current": _level_label(r["level"]),
                "via": r["matched_skill"],
                "credit": r["credit"],
                "weight": r["weight"],
            }
            for r in breakdown
        ],
        "missing": None if breakdown else "This drive has no skill requirements yet.",
    }


def _impact_label(score, mandatory):
    order = [Impact.LOW, Impact.MEDIUM, Impact.HIGH]
    idx = 2 if score >= 2 else 1 if score >= 0.75 else 0
    if mandatory:
        idx = min(idx + 1, 2)
    return order[idx]


def suggested_action(kind, skill, current, verified, required, examples):
    req, cur = _level_label(required), _level_label(current)
    if kind == GapKind.MISSING:
        options = f" (for example {', '.join(examples)})" if examples else ""
        return (
            f"Learn {skill}{options} to {req} level: work through the fundamentals, then use it in a "
            f"project and add that project as evidence."
        )
    if kind == GapKind.BELOW_LEVEL:
        return (
            f"Take {skill} from {cur} to {req}: practise beyond the basics, apply it in a larger project "
            f"or take an institutional assessment, and record the result as evidence."
        )
    return (
        f"Your {skill} evidence supports {cur}, but only {_level_label(verified)} is verified. Ask your "
        f"mentor to verify it, or take an institutional assessment."
    )


def gaps(breakdown, examples_by_skill):
    """Ranked, actionable gaps from a compatibility breakdown (highest impact first)."""
    items = []
    for r in breakdown:
        if r["credit"] >= 1.0:
            continue
        if r["match"] == "none":
            kind = GapKind.MISSING
        elif r["level"] < r["required_level"]:
            kind = GapKind.BELOW_LEVEL
        else:
            kind = GapKind.UNVERIFIED
        score = r["weight"] * (1 - r["credit"]) * (1.5 if r["is_mandatory"] else 1.0)
        items.append(
            {
                "skill_id": r["skill_id"],
                "skill": r["skill"],
                "kind": kind,
                "current_level": r["level"],
                "verified_level": r["verified_level"],
                "required_level": r["required_level"],
                "is_mandatory": r["is_mandatory"],
                "weight": r["weight"],
                "impact_score": round(score, 3),
                "impact": _impact_label(score, r["is_mandatory"]),
                "suggested_action": suggested_action(
                    kind,
                    r["skill"],
                    r["level"],
                    r["verified_level"],
                    r["required_level"],
                    examples_by_skill.get(r["skill_id"], []),
                ),
            }
        )
    items.sort(key=lambda g: (-g["impact_score"], -g["is_mandatory"], g["skill"]))
    for i, g in enumerate(items, start=1):
        g["rank"] = i
    return items
