import pytest

from apps.accounts.roles import Role

pytestmark = pytest.mark.django_db
STUDENTS = "/api/v1/students/"


def test_officer_sees_all_faculty_sees_mentees_only(make_student, make_user, officer, faculty, as_user):
    other_fac = make_user(email="f2@example.test", roles=[Role.FACULTY])
    mine = make_student(name="Mine")
    make_student(name="Theirs", mentor=other_fac)
    assert as_user(officer).get(STUDENTS).json()["count"] == 2
    assert [s["id"] for s in as_user(faculty).get(STUDENTS).json()["results"]] == [mine.pk]


def test_student_cannot_list_students(make_student, as_user):
    s = make_student()
    assert as_user(s.user).get(STUDENTS).status_code == 403


def test_student_reads_self_via_me_but_not_others(make_student, as_user):
    a, b = make_student(name="A"), make_student(name="B")
    client = as_user(a.user)
    assert client.get(f"{STUDENTS}me/").json()["id"] == a.pk
    assert client.get(f"{STUDENTS}{b.pk}/").status_code == 404
    assert client.get(f"{STUDENTS}{b.pk}/profile/").status_code == 404
    assert client.get(f"{STUDENTS}{b.pk}/readiness/").status_code == 404


def test_student_edits_own_links_but_not_academic_record(make_student, as_user):
    s = make_student(cgpa="6.00")
    client = as_user(s.user)
    ok = client.patch(f"{STUDENTS}me/", {"headline": "Backend developer", "cgpa": "9.9"}, format="json")
    assert ok.status_code == 200
    s.refresh_from_db()
    assert s.headline == "Backend developer"
    assert str(s.cgpa) == "6.00"  # academic fields ignored for students


def test_officer_creates_student_and_updates_academics(officer, departments, faculty, as_user):
    client = as_user(officer)
    response = client.post(
        STUDENTS,
        {
            "email": "new@example.test",
            "first_name": "New",
            "last_name": "Student",
            "roll_number": "12309000",
            "department_id": departments["IT"].pk,
            "graduation_year": 2027,
            "cgpa": "7.50",
            "mentor_id": faculty.pk,
        },
        format="json",
    )
    assert response.status_code == 201, response.content
    sid = response.json()["id"]
    assert client.patch(f"{STUDENTS}{sid}/", {"active_backlogs": 1}, format="json").json()["active_backlogs"] == 1


def test_faculty_cannot_create_students(faculty, departments, as_user):
    response = as_user(faculty).post(STUDENTS, {"email": "x@example.test"}, format="json")
    assert response.status_code == 403


def test_mentor_must_be_faculty(officer, make_student, as_user):
    s = make_student()
    response = as_user(officer).patch(f"{STUDENTS}{s.pk}/", {"mentor_id": officer.pk}, format="json")
    assert response.status_code == 400


@pytest.mark.parametrize("bad", ["1230222", "123022211", "R0001234", "1230 221", "１２３０２２２１"])
def test_registration_number_must_be_eight_digits(bad, officer, make_student, departments, as_user):
    client = as_user(officer)
    payload = {
        "email": "fmt@example.test",
        "first_name": "Format",
        "last_name": "Check",
        "roll_number": bad,
        "department_id": departments["CSE"].pk,
        "graduation_year": 2027,
        "cgpa": "7.50",
    }
    assert client.post(STUDENTS, payload, format="json").status_code == 400
    s = make_student()
    assert client.patch(f"{STUDENTS}{s.pk}/", {"roll_number": bad}, format="json").status_code == 400


def test_service_layer_rejects_bad_registration_number(departments, institution):
    from decimal import Decimal

    from apps.students.services import StudentError, create_student

    with pytest.raises(StudentError, match="8 digits"):
        create_student(
            institution=institution,
            email="svc@example.test",
            first_name="Svc",
            last_name="Check",
            roll_number="DEMO0001",
            department=departments["CSE"],
            graduation_year=2027,
            cgpa=Decimal("8.00"),
        )
