"""Bulk student import from an Excel sheet (placement cell, e.g. an ERP/SIS extract). Rows are
matched on registration number: new numbers create accounts, known numbers update the academic
record. Every row is validated first and nothing is written unless all rows are valid."""

from decimal import Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction

from apps.accounts.roles import Role
from apps.core.excel import read_rows

from . import services
from .models import Department, StudentProfile
from .validators import validate_registration_number

REQUIRED_COLUMNS = ["registration_number"]
COLUMNS = [
    ("registration_number", "8-digit university registration number (required)"),
    ("email", "Institutional email (required for new students)"),
    ("first_name", "Required for new students"),
    ("last_name", ""),
    ("department", "Department code, e.g. CSE (required for new students)"),
    ("graduation_year", "e.g. 2027 (required for new students)"),
    ("cgpa", "0–10 (required for new students)"),
    ("active_backlogs", "Defaults to 0"),
    ("mentor_email", "Email of a faculty mentor (optional)"),
]
EXAMPLE = {
    "registration_number": "12345678",
    "email": "student@your-institution.edu",
    "first_name": "First",
    "last_name": "Last",
    "department": "CSE",
    "graduation_year": 2027,
    "cgpa": 8.1,
    "active_backlogs": 0,
    "mentor_email": "",
}


def _text(row, key):
    value = row.get(key)
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).strip()


def _parse(row, *, departments, mentors, existing):
    """Returns (roll_number, changes, new_fields) or raises ValueError with a row message."""
    roll = _text(row, "registration_number")
    try:
        validate_registration_number(roll)
    except ValidationError:
        raise ValueError("Registration number must be exactly 8 digits.") from None
    changes = {}
    if dept := _text(row, "department"):
        if dept.upper() not in departments:
            raise ValueError(f"Unknown department '{dept}'.")
        changes["department"] = departments[dept.upper()]
    if year := _text(row, "graduation_year"):
        if not year.isdigit() or not 2000 <= int(year) <= 2100:
            raise ValueError("Graduation year must be between 2000 and 2100.")
        changes["graduation_year"] = int(year)
    if cgpa := _text(row, "cgpa"):
        try:
            value = Decimal(cgpa).quantize(Decimal("0.01"))
        except InvalidOperation:
            raise ValueError("CGPA must be a number.") from None
        if not 0 <= value <= 10:
            raise ValueError("CGPA must be between 0 and 10.")
        changes["cgpa"] = value
    if backlogs := _text(row, "active_backlogs"):
        if not backlogs.isdigit():
            raise ValueError("Active backlogs must be a whole number.")
        changes["active_backlogs"] = int(backlogs)
    if mentor := _text(row, "mentor_email").lower():
        if mentor not in mentors:
            raise ValueError(f"No faculty member with email '{mentor}'.")
        changes["mentor"] = mentors[mentor]
    new = None
    if roll not in existing:
        email = _text(row, "email").lower()
        first = _text(row, "first_name")
        missing = [
            c
            for c, ok in [
                ("email", email),
                ("first_name", first),
                ("department", "department" in changes),
                ("graduation_year", "graduation_year" in changes),
                ("cgpa", "cgpa" in changes),
            ]
            if not ok
        ]
        if missing:
            raise ValueError(f"New student needs: {', '.join(missing)}.")
        try:
            validate_email(email)
        except ValidationError:
            raise ValueError("Email is not valid.") from None
        new = {"email": email, "first_name": first, "last_name": _text(row, "last_name")}
    return roll, changes, new


def import_students(institution, uploaded, *, actor, dry_run=False):
    from apps.core.services import record_audit

    rows = read_rows(uploaded, REQUIRED_COLUMNS)
    departments = {d.code.upper(): d for d in Department.objects.filter(institution=institution)}
    User = get_user_model()
    mentors = {u.email.lower(): u for u in User.objects.filter(institution=institution, groups__name=Role.FACULTY)}
    existing = {
        s.roll_number: s
        for s in StudentProfile.objects.filter(institution=institution).select_related("department", "mentor")
    }
    taken_emails = {e.lower() for e in User.objects.values_list("email", flat=True)}
    errors, plan, seen = [], [], set()
    for number, row in rows:
        try:
            roll, changes, new = _parse(row, departments=departments, mentors=mentors, existing=existing)
            if roll in seen:
                raise ValueError("Registration number appears more than once in the file.")
            seen.add(roll)
            if new is not None:
                if new["email"] in taken_emails:
                    raise ValueError("An account with this email already exists.")
                taken_emails.add(new["email"])
            plan.append((number, roll, changes, new))
        except ValueError as exc:
            errors.append({"row": number, "registration_number": _text(row, "registration_number"), "error": str(exc)})

    created = sum(1 for *_, new in plan if new is not None)
    updated = sum(
        1
        for _, roll, changes, new in plan
        if new is None and any(getattr(existing[roll], k) != v for k, v in changes.items())
    )
    summary = {
        "rows": len(rows),
        "created": created,
        "updated": updated,
        "unchanged": len(plan) - created - updated,
        "errors": errors,
        "applied": False,
    }
    if errors or dry_run:
        return summary

    with transaction.atomic():
        for _, roll, changes, new in plan:
            if new is not None:
                services.create_student(
                    institution=institution,
                    roll_number=roll,
                    department=changes["department"],
                    graduation_year=changes["graduation_year"],
                    cgpa=changes["cgpa"],
                    active_backlogs=changes.get("active_backlogs", 0),
                    mentor=changes.get("mentor"),
                    **new,
                )
                continue
            student = existing[roll]
            diff = {k: v for k, v in changes.items() if getattr(student, k) != v}
            if diff:
                # Values from the placement cell's own records confirm the academic record.
                services.update_student(student, by_staff=True, academic_record_verified=True, **diff)
        record_audit(
            actor=actor,
            action="students.import",
            institution=institution,
            after={"created": created, "updated": updated, "rows": len(rows)},
        )
    summary["applied"] = True
    return summary
