"""Eligibility: hard criteria only. Never consults skills or readiness (P06 §2)."""

from decimal import Decimal, InvalidOperation

from .models import RuleType


class RuleValueError(ValueError):
    pass


def validate_rule_value(rule_type, value):
    """Normalise and validate a rule value; raises RuleValueError."""
    if rule_type == RuleType.MIN_CGPA:
        try:
            number = Decimal(str(value))
        except (InvalidOperation, TypeError) as exc:
            raise RuleValueError("Minimum CGPA must be a number.") from exc
        if not Decimal("0") <= number <= Decimal("10"):
            raise RuleValueError("Minimum CGPA must be between 0 and 10.")
        return float(number)
    if rule_type == RuleType.MAX_ACTIVE_BACKLOGS:
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise RuleValueError("Maximum active backlogs must be a non-negative whole number.")
        return value
    if rule_type == RuleType.DEPARTMENT_IN:
        if not isinstance(value, list) or not value or not all(isinstance(v, str) and v.strip() for v in value):
            raise RuleValueError("List at least one department code.")
        return sorted({v.strip().upper() for v in value})
    if rule_type == RuleType.GRADUATION_YEAR_IN:
        if not isinstance(value, list) or not value or not all(isinstance(v, int) for v in value):
            raise RuleValueError("List at least one graduation year.")
        return sorted(set(value))
    raise RuleValueError("Unknown rule type.")


def evaluate(student, rules):
    """Return (is_eligible, reasons). Every rule is reported, passed or not, so the student sees
    exactly which criteria they meet and miss."""
    reasons = []
    for rule in rules:
        if rule.rule_type == RuleType.MIN_CGPA:
            passed = float(student.cgpa) >= float(rule.value)
            reasons.append(
                {
                    "rule": rule.rule_type,
                    "passed": passed,
                    "required": f"CGPA ≥ {rule.value}",
                    "actual": f"{student.cgpa}",
                    "message": "CGPA requirement met" if passed else f"CGPA {student.cgpa} is below {rule.value}",
                }
            )
        elif rule.rule_type == RuleType.MAX_ACTIVE_BACKLOGS:
            passed = student.active_backlogs <= int(rule.value)
            reasons.append(
                {
                    "rule": rule.rule_type,
                    "passed": passed,
                    "required": "No active backlogs"
                    if int(rule.value) == 0
                    else f"At most {rule.value} active backlogs",
                    "actual": str(student.active_backlogs),
                    "message": "Backlog requirement met"
                    if passed
                    else f"{student.active_backlogs} active backlog(s); at most {rule.value} allowed",
                }
            )
        elif rule.rule_type == RuleType.DEPARTMENT_IN:
            code = student.department.code.upper()
            passed = code in rule.value
            reasons.append(
                {
                    "rule": rule.rule_type,
                    "passed": passed,
                    "required": ", ".join(rule.value),
                    "actual": code,
                    "message": "Department requirement met" if passed else f"{code} is not an eligible department",
                }
            )
        elif rule.rule_type == RuleType.GRADUATION_YEAR_IN:
            passed = student.graduation_year in rule.value
            reasons.append(
                {
                    "rule": rule.rule_type,
                    "passed": passed,
                    "required": ", ".join(map(str, rule.value)),
                    "actual": str(student.graduation_year),
                    "message": "Batch requirement met"
                    if passed
                    else f"Graduation year {student.graduation_year} is not eligible",
                }
            )
    return all(r["passed"] for r in reasons), reasons
