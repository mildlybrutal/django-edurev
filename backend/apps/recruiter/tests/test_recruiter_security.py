"""Dedicated recruiter-portal authorisation suite (P06 §15, AGENTS.md §17, §30).

Mandatory property: a recruiter can reach registered students of their approved drive and
nothing else, through every endpoint, and every access is logged.
"""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.roles import Role
from apps.accounts.services import issue_tokens
from apps.core.models import Institution
from apps.drives import services as drive_services
from apps.evidence.models import SourceType
from apps.matching.services import run_drive_matching
from apps.recruiter import services
from apps.recruiter.models import AccessAction, AccessLog
from apps.taxonomy.models import Level

pytestmark = pytest.mark.django_db
ALL_FIELDS = [
    "name",
    "email",
    "department",
    "graduation_year",
    "cgpa",
    "compatibility",
    "readiness",
    "skills",
    "evidence",
    "registration_status",
]


@pytest.fixture
def world(make_user, make_student, make_drive, taxonomy, give_evidence, head):
    """Drive A and Drive B with disjoint registrations; recruiter A granted on Drive A only."""
    django = taxonomy("Django")
    drive_a = make_drive(role="Backend Engineer", company="Alpha", requirements=[(django, Level.INTERMEDIATE, 1, True)])
    drive_b = make_drive(
        role="Data Analyst", company="Beta", requirements=[(taxonomy("SQL"), Level.INTERMEDIATE, 1, True)]
    )
    in_a = make_student(name="InA")
    in_b = make_student(name="InB")
    unregistered = make_student(name="Nowhere")
    for s in (in_a, in_b, unregistered):
        give_evidence(s, SourceType.PROJECT, f"{s.name} project", [(django, Level.INTERMEDIATE)], verified=True)
    drive_services.register(drive_a, in_a)
    drive_services.register(drive_b, in_b)
    run_drive_matching(drive_a)
    run_drive_matching(drive_b)
    recruiter_a = make_user(email="rec-a@alpha.example", roles=[Role.RECRUITER])
    recruiter_b = make_user(email="rec-b@beta.example", roles=[Role.RECRUITER])
    grant_a = services.create_grant(
        recruiter=recruiter_a,
        drive=drive_a,
        allowed_fields=["name", "skills"],
        expires_at=timezone.now() + timedelta(days=7),
        granted_by=head,
    )
    return {
        "drive_a": drive_a,
        "drive_b": drive_b,
        "in_a": in_a,
        "in_b": in_b,
        "unregistered": unregistered,
        "recruiter_a": recruiter_a,
        "recruiter_b": recruiter_b,
        "grant_a": grant_a,
    }


def recruiter_client(user):
    client = APIClient()
    client.cookies["rc_access"] = issue_tokens(user, "recruiter").access
    return client


def candidates(drive):
    return f"/api/v1/recruiter/drives/{drive.pk}/candidates/"


# --- Layer 1: scope ------------------------------------------------------------------------------


def test_recruiter_can_access_registered_students_of_approved_drive(world):
    client = recruiter_client(world["recruiter_a"])
    body = client.get(candidates(world["drive_a"])).json()
    assert [c["id"] for c in body["results"]] == [world["in_a"].pk]
    detail = client.get(f"{candidates(world['drive_a'])}{world['in_a'].pk}/")
    assert detail.status_code == 200


def test_recruiter_cannot_access_student_registered_only_for_another_drive(world):
    """THE mandatory negative test: Recruiter A + Drive A cannot reach a Drive B student."""
    client = recruiter_client(world["recruiter_a"])
    # Not via Drive A's detail endpoint …
    assert client.get(f"{candidates(world['drive_a'])}{world['in_b'].pk}/").status_code == 404
    # … not via Drive B's endpoints …
    assert client.get(candidates(world["drive_b"])).status_code == 404
    assert client.get(f"{candidates(world['drive_b'])}{world['in_b'].pk}/").status_code == 404
    # … and not in any list or search result.
    listed = client.get(candidates(world["drive_a"]), {"q": "django"}).json()
    assert world["in_b"].pk not in [c["id"] for c in listed["results"]]


def test_unregistered_student_is_unreachable(world):
    client = recruiter_client(world["recruiter_a"])
    assert client.get(f"{candidates(world['drive_a'])}{world['unregistered'].pk}/").status_code == 404


def test_withdrawn_student_disappears(world):
    drive_services.withdraw(world["drive_a"], world["in_a"])
    client = recruiter_client(world["recruiter_a"])
    assert client.get(candidates(world["drive_a"])).json()["count"] == 0
    assert client.get(f"{candidates(world['drive_a'])}{world['in_a'].pk}/").status_code == 404


def test_shortlist_scope_hides_merely_registered_students(world, head):
    services.update_grant(world["grant_a"], actor=head, candidate_scope="shortlisted")
    client = recruiter_client(world["recruiter_a"])
    assert client.get(candidates(world["drive_a"])).json()["count"] == 0


def test_facets_only_count_scoped_candidates(world):
    services.update_grant(
        world["grant_a"],
        actor=world["grant_a"].granted_by,
        allowed_fields=["name", "skills", "department", "compatibility"],
    )
    body = recruiter_client(world["recruiter_a"]).get(candidates(world["drive_a"])).json()
    assert sum(f["count"] for f in body["facets"]["department"]) == 1
    assert body["facets"]["skills"] == [{"value": "Django", "count": 1}]
    assert sum(f["count"] for f in body["facets"]["compatibility"]) == 1


def test_unauthorized_drive_returns_404_and_is_logged(world):
    client = recruiter_client(world["recruiter_b"])  # no grant at all
    assert client.get(candidates(world["drive_a"])).status_code == 404
    log = AccessLog.objects.get(recruiter=world["recruiter_b"])
    assert log.action == AccessAction.DENIED and log.drive_id_requested == world["drive_a"].pk


def test_other_institutions_drive_ids_reveal_nothing(world, head):
    other = Institution.objects.create(name="Elsewhere", code="elsewhere")
    assert world["recruiter_a"].institution_id != other.pk
    client = recruiter_client(world["recruiter_a"])
    assert client.get("/api/v1/recruiter/drives/999999/candidates/").status_code == 404


# --- Grant validity (checked in the permission path on every request) ----------------------------


def test_expired_grant_blocks_access(world):
    grant = world["grant_a"]
    grant.expires_at = timezone.now() - timedelta(seconds=1)
    grant.save()
    client = recruiter_client(world["recruiter_a"])
    assert client.get(candidates(world["drive_a"])).status_code == 404
    assert client.get("/api/v1/recruiter/drives/").json() == []


def test_grant_expiring_mid_session_takes_effect_immediately(world):
    client = recruiter_client(world["recruiter_a"])
    assert client.get(candidates(world["drive_a"])).status_code == 200
    grant = world["grant_a"]
    grant.expires_at = timezone.now() - timedelta(seconds=1)
    grant.save()
    assert client.get(candidates(world["drive_a"])).status_code == 404  # same token, same session


def test_revoked_and_future_grants_block_access(world, head):
    services.revoke_grant(world["grant_a"], actor=head)
    client = recruiter_client(world["recruiter_a"])
    assert client.get(candidates(world["drive_a"])).status_code == 404
    future = services.create_grant(
        recruiter=world["recruiter_a"],
        drive=world["drive_a"],
        allowed_fields=["name"],
        starts_at=timezone.now() + timedelta(days=1),
        expires_at=timezone.now() + timedelta(days=2),
        granted_by=head,
    )
    assert future.pk
    assert client.get(candidates(world["drive_a"])).status_code == 404


# --- Layer 2: field-level release ----------------------------------------------------------------


def test_only_approved_fields_are_released(world):
    client = recruiter_client(world["recruiter_a"])
    row = client.get(candidates(world["drive_a"])).json()["results"][0]
    assert set(row) == {"id", "name", "skills"}
    detail = client.get(f"{candidates(world['drive_a'])}{world['in_a'].pk}/").json()
    assert set(detail) == {"id", "name", "skills"}
    for unapproved in ("email", "cgpa", "department", "evidence", "readiness", "compatibility"):
        assert unapproved not in detail


def test_all_releasable_fields_when_granted(world, head):
    services.update_grant(world["grant_a"], actor=head, allowed_fields=ALL_FIELDS)
    detail = recruiter_client(world["recruiter_a"]).get(f"{candidates(world['drive_a'])}{world['in_a'].pk}/").json()
    assert set(detail) == {"id", *ALL_FIELDS}
    # Even with evidence released, only titles/types/status go out: no descriptions, files or URLs.
    assert set(detail["evidence"][0]) == {"title", "type", "verification"}


def test_unknown_fields_cannot_be_granted(world, head):
    with pytest.raises(services.GrantError):
        services.update_grant(world["grant_a"], actor=head, allowed_fields=["name", "password"])
    with pytest.raises(services.GrantError):
        services.update_grant(world["grant_a"], actor=head, allowed_fields=["phone", "address"])


def test_filters_on_unreleased_fields_are_ignored(world):
    """Filtering by an unreleased field must not become a side channel (e.g. probing departments)."""
    client = recruiter_client(world["recruiter_a"])
    assert client.get(candidates(world["drive_a"]), {"department": "ECE"}).json()["count"] == 1
    assert client.get(candidates(world["drive_a"]), {"min_compatibility": 101}).json()["count"] == 1


# --- Direct API access, portal separation, export, throttling, logging ---------------------------


def test_internal_portal_token_cannot_call_recruiter_api(world, as_user):
    client = as_user(world["recruiter_a"])  # internal cookie name, internal claim
    assert client.get(candidates(world["drive_a"])).status_code == 401


def test_recruiter_token_cannot_call_internal_api(world):
    client = APIClient()
    client.cookies["pa_access"] = issue_tokens(world["recruiter_a"], "recruiter").access
    assert client.get("/api/v1/students/").status_code == 401
    assert client.get(f"/api/v1/students/{world['in_a'].pk}/").status_code == 401
    assert client.get("/api/v1/evidence/").status_code == 401


def test_staff_cannot_use_the_recruiter_portal(world, officer):
    client = APIClient()
    client.cookies["rc_access"] = issue_tokens(officer, "recruiter").access
    assert client.get(candidates(world["drive_a"])).status_code == 403


def test_anonymous_requests_rejected(world):
    assert APIClient().get(candidates(world["drive_a"])).status_code == 401


def test_recruiter_login_uses_its_own_portal(world, csrf_client, make_user):
    world["recruiter_a"].set_password("Rec-Pass-12345")
    world["recruiter_a"].save()
    ok = csrf_client.post(
        "/api/v1/recruiter/auth/login/", {"email": "rec-a@alpha.example", "password": "Rec-Pass-12345"}, format="json"
    )
    assert ok.status_code == 200
    assert ok.cookies["rc_access"]["path"] == "/api/v1/recruiter/"
    assert "pa_access" not in ok.cookies
    staff = make_user(email="staff@example.test", roles=[Role.PLACEMENT_OFFICER])
    denied = csrf_client.post(
        "/api/v1/recruiter/auth/login/", {"email": staff.email, "password": "Correct-Horse-9"}, format="json"
    )
    assert denied.status_code == 401


def test_no_write_or_export_endpoints(world):
    from apps.recruiter.api import urls as recruiter_urls

    client = recruiter_client(world["recruiter_a"])
    url = candidates(world["drive_a"])
    for method in ("post", "put", "patch", "delete"):
        assert getattr(client, method)(url, {}, format="json").status_code == 405
    routes = [str(p.pattern) for p in recruiter_urls.urlpatterns]
    assert not [r for r in routes if any(word in r for word in ("export", "csv", "download", "bulk"))]
    # Recruiter routes are auth plus read-only candidate browsing; nothing else exists.
    assert sorted(routes) == sorted(
        [
            "auth/login/",
            "auth/mfa/verify/",
            "auth/refresh/",
            "auth/logout/",
            "me/",
            "drives/",
            "drives/<int:drive_id>/candidates/",
            "drives/<int:drive_id>/candidates/<int:student_id>/",
            "drives/<int:drive_id>/candidates/<int:student_id>/resume/",  # one signed link per logged request
        ]
    )


def test_page_size_cannot_be_raised(world, make_student, head):
    for _ in range(12):
        s = make_student()
        drive_services.register(world["drive_a"], s)
    client = recruiter_client(world["recruiter_a"])
    body = client.get(candidates(world["drive_a"]), {"page_size": 1000}).json()
    assert body["count"] == 13 and len(body["results"]) == 10


def test_responses_are_not_cacheable(world):
    response = recruiter_client(world["recruiter_a"]).get(candidates(world["drive_a"]))
    assert response["Cache-Control"] == "no-store"


def test_recruiter_requests_are_throttled(world, settings):
    from rest_framework.throttling import ScopedRateThrottle

    original = ScopedRateThrottle.THROTTLE_RATES
    ScopedRateThrottle.THROTTLE_RATES = {**original, "recruiter": "3/min"}
    try:
        client = recruiter_client(world["recruiter_a"])
        codes = [client.get(candidates(world["drive_a"])).status_code for _ in range(4)]
    finally:
        ScopedRateThrottle.THROTTLE_RATES = original
    assert codes == [200, 200, 200, 429]


def test_every_access_is_logged_with_students_and_fields(world):
    client = recruiter_client(world["recruiter_a"])
    client.get(candidates(world["drive_a"]))
    client.get(candidates(world["drive_a"]), {"q": "django"})
    client.get(f"{candidates(world['drive_a'])}{world['in_a'].pk}/")
    client.get(f"{candidates(world['drive_a'])}{world['in_b'].pk}/")
    logs = list(AccessLog.objects.filter(recruiter=world["recruiter_a"]).order_by("id"))
    assert [log.action for log in logs] == ["list", "search", "detail", "denied"]
    assert logs[0].student_ids == [world["in_a"].pk]
    assert logs[0].fields_released == ["name", "skills"]
    assert logs[1].query == {"q": "django"}
    assert logs[3].student_ids == [world["in_b"].pk]


def test_access_log_is_reviewable_by_head_only(world, head, officer, as_user):
    recruiter_client(world["recruiter_a"]).get(candidates(world["drive_a"]))
    assert as_user(head).get("/api/v1/recruiter-admin/access-logs/").json()["count"] == 1
    assert as_user(officer).get("/api/v1/recruiter-admin/access-logs/").status_code == 403


def test_only_head_manages_grants(world, officer, head, as_user):
    payload = {
        "recruiter_id": world["recruiter_b"].pk,
        "drive_id": world["drive_b"].pk,
        "allowed_fields": ["name"],
        "expires_at": (timezone.now() + timedelta(days=3)).isoformat(),
    }
    assert as_user(officer).post("/api/v1/recruiter-admin/grants/", payload, format="json").status_code == 403
    response = as_user(head).post("/api/v1/recruiter-admin/grants/", payload, format="json")
    assert response.status_code == 201, response.content
    assert recruiter_client(world["recruiter_b"]).get(candidates(world["drive_b"])).json()["count"] == 1


def test_grants_cannot_target_non_recruiters(world, head, officer):
    with pytest.raises(services.GrantError):
        services.create_grant(
            recruiter=officer,
            drive=world["drive_a"],
            allowed_fields=["name"],
            expires_at=timezone.now() + timedelta(days=1),
            granted_by=head,
        )
