from datetime import date, timedelta

import pytest

from apps.evidence.models import SourceType
from apps.matching.services import match_student
from apps.planning import services
from apps.planning.models import ItemStatus, LearningResource, PlanStatus, PreparationPlan
from apps.taxonomy.models import Level

pytestmark = pytest.mark.django_db
TODAY = date(2026, 10, 21)


@pytest.fixture
def setup(make_student, make_drive, taxonomy, give_evidence):
    s = make_student()
    give_evidence(s, SourceType.PROJECT, "API", [(taxonomy("Django"), Level.BEGINNER)], verified=True)
    drive = make_drive(
        drive_date=TODAY + timedelta(days=29),
        requirements=[
            (taxonomy("Django"), Level.ADVANCED, 3, True),
            (taxonomy("Docker"), Level.INTERMEDIATE, 2, False),
            (taxonomy("Redis"), Level.BEGINNER, 1, False),
        ],
    )
    match_student(drive, s)
    return s, drive


def test_gap_creation_feeds_plan_in_impact_order(setup):
    s, drive = setup
    plan = services.generate_plan(s, drive, today=TODAY)
    skills_in_order = []
    for item in plan.items.order_by("order"):
        if item.skill.name not in skills_in_order:
            skills_in_order.append(item.skill.name)
    assert skills_in_order == ["Django", "Docker", "Redis"]


def test_checkpoint_dates_fall_before_the_drive(setup):
    s, drive = setup
    plan = services.generate_plan(s, drive, today=TODAY)
    items = list(plan.items.all())
    assert plan.start_date == TODAY and plan.end_date == drive.drive_date - timedelta(days=1)
    assert all(TODAY <= i.start_date <= i.due_date <= plan.end_date for i in items)
    checkpoints = [i for i in items if i.is_checkpoint]
    assert len(checkpoints) == 3
    assert [c.due_date for c in checkpoints] == sorted(c.due_date for c in checkpoints)


def test_plan_compresses_when_time_is_short(setup):
    s, drive = setup
    drive.drive_date = TODAY + timedelta(days=8)
    drive.save()
    plan = services.generate_plan(s, drive, today=TODAY)
    assert max(i.due_date for i in plan.items.all()) <= TODAY + timedelta(days=7)


def test_resources_are_attached(setup, institution, taxonomy):
    s, drive = setup
    LearningResource.objects.create(
        institution=institution,
        skill=taxonomy("Docker"),
        target_level=Level.INTERMEDIATE,
        title="Docker docs: Get started",
        url="https://docs.docker.com/get-started/",
    )
    plan = services.generate_plan(s, drive, today=TODAY)
    assert plan.items.filter(resource_title="Docker docs: Get started").exists()


def test_regenerating_archives_the_previous_plan(setup):
    s, drive = setup
    first = services.generate_plan(s, drive, today=TODAY)
    services.generate_plan(s, drive, today=TODAY)
    first.refresh_from_db()
    assert first.status == PlanStatus.ARCHIVED
    assert PreparationPlan.objects.filter(student=s, status=PlanStatus.ACTIVE).count() == 1


def test_progress_updates_by_owner_only(setup, make_student, as_user):
    s, drive = setup
    plan = services.generate_plan(s, drive, today=TODAY)
    item = plan.items.first()
    other = make_student()
    assert (
        as_user(other.user)
        .patch(f"/api/v1/preparation-plans/items/{item.pk}/", {"status": "done"}, format="json")
        .status_code
        == 404
    )
    response = as_user(s.user).patch(f"/api/v1/preparation-plans/items/{item.pk}/", {"status": "done"}, format="json")
    assert response.status_code == 200
    assert services.progress(plan)["done"] == 1


def test_generate_via_api(setup, as_user):
    s, drive = setup
    response = as_user(s.user).post("/api/v1/preparation-plans/", {"drive_id": drive.pk}, format="json")
    assert response.status_code == 201, response.content
    body = response.json()
    assert body["progress"]["total"] == len(body["items"]) > 0


def test_checkpoint_reminders_sent_once(setup):
    s, drive = setup
    plan = services.generate_plan(s, drive, today=TODAY)
    first_checkpoint = plan.items.filter(is_checkpoint=True).order_by("due_date").first()
    day_before = first_checkpoint.due_date - timedelta(days=1)
    assert services.send_checkpoint_reminders(today=day_before) >= 1
    assert services.send_checkpoint_reminders(today=day_before) == 0
    assert s.user.notifications.filter(kind="checkpoint_due").exists()
    first_checkpoint.refresh_from_db()
    assert first_checkpoint.status == ItemStatus.TODO
