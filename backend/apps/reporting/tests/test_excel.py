"""Excel export/import: staff-only, scoped to what each role can already see, filters applied."""

import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import Workbook, load_workbook

from apps.accounts.roles import Role
from apps.core.models import AuditLog
from apps.evidence.models import SourceType
from apps.students.models import StudentProfile
from apps.taxonomy.models import Level

pytestmark = pytest.mark.django_db
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def sheet(response):
    assert response.status_code == 200, response.content
    assert response["Content-Type"] == XLSX
    wb = load_workbook(io.BytesIO(b"".join(response.streaming_content) if response.streaming else response.content))
    rows = list(wb.worksheets[0].iter_rows(values_only=True))
    return rows[0], rows[1:]


def column(header, rows, name):
    i = header.index(name)
    return [r[i] for r in rows]


def xlsx(rows):
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return SimpleUploadedFile("students.xlsx", buf.getvalue(), XLSX)


# --- exports -------------------------------------------------------------------------------------


def test_cell_exports_students_with_filters(make_student, officer, as_user):
    make_student(name="Cse")
    make_student(name="Ece", dept="ECE")
    header, rows = sheet(as_user(officer).get("/api/v1/students/export/"))
    assert len(rows) == 2 and "Readiness % (general)" in header
    header, rows = sheet(as_user(officer).get("/api/v1/students/export/?department=ECE"))
    assert column(header, rows, "Department") == ["ECE"]
    assert AuditLog.objects.filter(action="students.export").count() == 2


def test_faculty_export_contains_only_mentees(make_student, faculty, make_user, as_user):
    mine = make_student(name="Mine")
    other_mentor = make_user(email="f2@example.test", roles=[Role.FACULTY])
    make_student(name="Theirs", mentor=other_mentor)
    header, rows = sheet(as_user(faculty).get("/api/v1/students/export/"))
    assert column(header, rows, "Registration number") == [mine.roll_number]


def test_students_and_recruiters_cannot_export(make_student, make_user, as_user):
    student = make_student()
    recruiter = make_user(email="rec@example.test", roles=[Role.RECRUITER])
    assert as_user(student.user).get("/api/v1/students/export/").status_code == 403
    assert as_user(recruiter).get("/api/v1/students/export/").status_code == 403
    assert as_user(student.user).get("/api/v1/evidence/export/").status_code == 403


def test_exported_text_cannot_run_as_formula(make_student, officer, as_user):
    student = make_student(name="=HYPERLINK(evil)")
    header, rows = sheet(as_user(officer).get("/api/v1/students/export/"))
    assert column(header, rows, "Name")[0].startswith("'=")
    assert student


def test_evidence_export_filters_by_status_and_source(make_student, faculty, taxonomy, give_evidence, as_user):
    s = make_student()
    give_evidence(s, SourceType.PROJECT, "Repo", [(taxonomy("Django"), Level.INTERMEDIATE)], verified=True)
    give_evidence(s, SourceType.CERTIFICATION, "AWS", [(taxonomy("AWS"), Level.BEGINNER)])
    header, rows = sheet(as_user(faculty).get("/api/v1/evidence/export/?source_type=certification"))
    assert column(header, rows, "Title") == ["AWS"]
    header, rows = sheet(as_user(faculty).get("/api/v1/evidence/export/?status=verified"))
    assert column(header, rows, "Title") == ["Repo"]


def test_drive_export_keeps_eligibility_and_readiness_separate(
    make_student, make_drive, taxonomy, give_evidence, officer, as_user
):
    from apps.drives.models import RuleType
    from apps.matching.services import run_drive_matching

    django = taxonomy("Django")
    drive = make_drive(requirements=[(django, Level.INTERMEDIATE, 1, True)], rules=[(RuleType.MIN_CGPA, "7.5")])
    strong = make_student(name="Strong", cgpa="6.00")
    give_evidence(strong, SourceType.PROJECT, "Repo", [(django, Level.INTERMEDIATE)], verified=True)
    make_student(name="Weak", cgpa="9.00")
    run_drive_matching(drive)

    header, rows = sheet(as_user(officer).get(f"/api/v1/drives/{drive.pk}/export/"))
    by_name = {r[header.index("Name")]: r for r in rows}
    strong_row = by_name[strong.name]
    assert strong_row[header.index("Eligibility")] == "Not eligible"
    assert strong_row[header.index("Compatibility %")] > 0
    header, rows = sheet(as_user(officer).get(f"/api/v1/drives/{drive.pk}/export/?eligible=true"))
    assert column(header, rows, "Eligibility") == ["Eligible"]
    assert "Top gaps (ranked)" in header


def test_drive_export_is_cell_only(make_drive, make_student, faculty, as_user):
    drive = make_drive()
    assert as_user(faculty).get(f"/api/v1/drives/{drive.pk}/export/").status_code == 403
    assert as_user(make_student().user).get(f"/api/v1/drives/{drive.pk}/export/").status_code == 403


# --- import --------------------------------------------------------------------------------------

HEADER = [
    "Registration Number",
    "Email",
    "First Name",
    "Last Name",
    "Department",
    "Graduation Year",
    "CGPA",
    "Active Backlogs",
    "Mentor Email",
]


def test_import_template_downloads(officer, as_user):
    header, rows = sheet(as_user(officer).get("/api/v1/students/import/"))
    # No example row in the importable sheet, so importing the template unchanged is a no-op.
    assert header[0] == "registration_number" and rows == []


def test_import_creates_and_updates_students(make_student, officer, faculty, as_user):
    existing = make_student(name="Old", cgpa="7.00")
    existing.academic_record_verified = False
    existing.save()
    upload = xlsx(
        [
            HEADER,
            ["12399001", "new@example.test", "New", "Kid", "cse", 2027, 8.4, 0, faculty.email],
            [existing.roll_number, None, None, None, None, None, "8.25", 1, None],
            [None, None, None, None, None, None, None, None, None],
        ]
    )
    dry = as_user(officer).post("/api/v1/students/import/", {"file": upload, "dry_run": "true"}, format="multipart")
    assert dry.json() == {"rows": 2, "created": 1, "updated": 1, "unchanged": 0, "errors": [], "applied": False}
    assert not StudentProfile.objects.filter(roll_number="12399001").exists()

    upload.seek(0)
    applied = as_user(officer).post("/api/v1/students/import/", {"file": upload}, format="multipart").json()
    assert applied["applied"] is True
    new = StudentProfile.objects.get(roll_number="12399001")
    assert new.mentor == faculty and new.department.code == "CSE" and str(new.cgpa) == "8.40"
    existing.refresh_from_db()
    assert str(existing.cgpa) == "8.25" and existing.active_backlogs == 1 and existing.academic_record_verified
    assert AuditLog.objects.filter(action="students.import").exists()


def test_import_is_all_or_nothing(make_student, officer, as_user):
    taken = make_student()
    upload = xlsx(
        [
            HEADER,
            ["12399001", "ok@example.test", "Ok", "", "CSE", 2027, 8, 0, None],
            ["1234", "bad@example.test", "Bad", "", "CSE", 2027, 8, 0, None],
            ["12399002", "x@example.test", "X", "", "MECH", 2027, 8, 0, None],
            ["12399003", taken.user.email, "Dup", "", "CSE", 2027, 11, 0, None],
            ["12399004", "y@example.test", "Y", "", "CSE", 2027, 8, 0, "nobody@example.test"],
        ]
    )
    body = as_user(officer).post("/api/v1/students/import/", {"file": upload}, format="multipart").json()
    assert body["applied"] is False
    assert [e["row"] for e in body["errors"]] == [3, 4, 5, 6]
    assert not StudentProfile.objects.filter(roll_number="12399001").exists()


def test_import_rejects_non_xlsx_and_missing_columns(officer, faculty, as_user):
    fake = SimpleUploadedFile("students.xlsx", b"not a zip", XLSX)
    assert as_user(officer).post("/api/v1/students/import/", {"file": fake}, format="multipart").status_code == 400
    no_col = xlsx([["Email"], ["a@example.test"]])
    response = as_user(officer).post("/api/v1/students/import/", {"file": no_col}, format="multipart")
    assert response.status_code == 400 and "registration_number" in response.json()["detail"]
    assert as_user(faculty).post("/api/v1/students/import/", {"file": no_col}, format="multipart").status_code == 403


# --- faculty mentee data -------------------------------------------------------------------------


def test_faculty_dashboard_has_mentee_summaries(make_student, faculty, taxonomy, give_evidence, as_user):
    s = make_student(name="Mentee")
    give_evidence(s, SourceType.PROJECT, "Repo", [(taxonomy("Django"), Level.INTERMEDIATE)], verified=True)
    give_evidence(s, SourceType.CERTIFICATION, "AWS", [(taxonomy("AWS"), Level.BEGINNER)])
    row = as_user(faculty).get("/api/v1/dashboard/faculty/").json()["students"][0]
    assert row["evidence_total"] == 2 and row["evidence_verified"] == 1
    assert row["cgpa"] == 8.0 and row["registrations"] == 0 and row["plan_total"] == 0


def test_student_drives_visible_to_mentor_only(make_student, make_drive, faculty, make_user, as_user):
    from apps.drives import services as drive_services
    from apps.matching.services import run_drive_matching

    s = make_student()
    drive = make_drive()
    drive_services.register(drive, s)
    run_drive_matching(drive)
    rows = as_user(faculty).get(f"/api/v1/students/{s.pk}/drives/").json()
    assert rows[0]["drive_id"] == drive.pk and rows[0]["is_eligible"] is True and "compatibility" in rows[0]
    other = make_user(email="f2@example.test", roles=[Role.FACULTY])
    assert as_user(other).get(f"/api/v1/students/{s.pk}/drives/").status_code == 404
