from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.evidence import services as evidence_services
from apps.evidence.models import EvidenceItem, VerificationStatus
from apps.taxonomy.selectors import resolve_skill

from . import clients, rating
from .models import CodingProfile, Platform, SyncStatus

MANUAL_REFRESH_INTERVAL = timedelta(minutes=30)
AUTO_REFRESH_INTERVAL = timedelta(hours=24)


class CodingError(ValueError):
    pass


def validate_username(platform, username):
    pattern = clients.GITHUB_USERNAME if platform == Platform.GITHUB else clients.LEETCODE_USERNAME
    if not pattern.match(username):
        raise CodingError(f"That doesn't look like a valid {Platform(platform).label} username.")
    return username


@transaction.atomic
def set_profiles(student, *, github=None, leetcode=None):
    """Create/replace/remove the student's coding handles; changed handles are re-synced.
    Pass "" to remove a platform, None to leave it unchanged."""
    changed = []
    for platform, username in ((Platform.GITHUB, github), (Platform.LEETCODE, leetcode)):
        if username is None:
            continue
        username = username.strip().lstrip("@")
        existing = CodingProfile.objects.filter(student=student, platform=platform).first()
        if not username:
            if existing:
                _retire_evidence(existing)
                existing.delete()
            continue
        validate_username(platform, username)
        if existing and existing.username.lower() == username.lower():
            continue
        if existing:
            _retire_evidence(existing)
            existing.delete()
        profile = CodingProfile.objects.create(
            institution_id=student.institution_id, student=student, platform=platform, username=username
        )
        changed.append(profile)
    for profile in changed:
        schedule_sync(profile)
    return changed


def schedule_sync(profile):
    from .tasks import sync_coding_profile

    transaction.on_commit(lambda: sync_coding_profile.delay(profile.pk))


def request_refresh(student):
    """Manual refresh, rate-limited so GitHub's unauthenticated quota is not exhausted."""
    now = timezone.now()
    queued = []
    for profile in CodingProfile.objects.filter(student=student):
        if profile.last_synced_at and now - profile.last_synced_at < MANUAL_REFRESH_INTERVAL:
            continue
        profile.status = SyncStatus.PENDING
        profile.save(update_fields=["status", "updated_at"])
        schedule_sync(profile)
        queued.append(profile)
    return queued


def sync(profile):
    """Fetch, rate, and record the profile as unverified external evidence."""
    try:
        stats = (
            clients.fetch_github(profile.username)
            if profile.platform == Platform.GITHUB
            else clients.fetch_leetcode(profile.username)
        )
    except clients.ProfileNotFound:
        profile.status, profile.error = SyncStatus.NOT_FOUND, "No public profile with that username."
        profile.score = None
        profile.last_synced_at = timezone.now()
        profile.save()
        _retire_evidence(profile)
        return profile
    except clients.FetchError as exc:
        # Keep the last good stats and score; just record the failure.
        profile.status, profile.error = SyncStatus.ERROR, str(exc)[:300]
        profile.last_synced_at = timezone.now()
        profile.save(update_fields=["status", "error", "last_synced_at", "updated_at"])
        return profile

    score, explanation = (rating.github_rating if profile.platform == Platform.GITHUB else rating.leetcode_rating)(
        stats
    )
    profile.stats, profile.score, profile.explanation = stats, score, explanation
    profile.status, profile.error, profile.last_synced_at = SyncStatus.OK, "", timezone.now()
    profile.save()
    _record_evidence(profile)
    return profile


def _tags(profile):
    student = profile.student
    if profile.platform == Platform.LEETCODE:
        dsa = resolve_skill(student.institution, "Data Structures & Algorithms")
        return [(dsa, rating.leetcode_dsa_level(profile.stats))] if dsa else []
    tags = []
    for language, level in rating.github_language_levels(profile.stats).items():
        skill = resolve_skill(student.institution, language)
        if skill and skill.pk not in {s.pk for s, _ in tags}:
            tags.append((skill, level))
    return tags[:8]


@transaction.atomic
def _record_evidence(profile):
    """One evidence item per profile, updated in place on every sync. It stays self-reported (or
    pending/verified if the student asked their mentor), so evidence rules cap it like any other
    unverified external activity."""
    stats = profile.stats
    title = (
        f"GitHub: {stats.get('original_repos', 0)} original repos, "
        f"{stats.get('recent_push_events', 0)} pushes in 90 days"
        if profile.platform == Platform.GITHUB
        else f"LeetCode: {stats.get('solved_total', 0)} problems solved"
        + (f", contest rating {stats['contest_rating']}" if stats.get("contest_rating") else "")
    )
    data = {"synced": True, "rating": float(profile.score), **{k: v for k, v in stats.items() if k != "top_repos"}}
    item = profile.evidence
    if item is None or not EvidenceItem.objects.filter(pk=item.pk).exists():
        item = evidence_services.submit_evidence(
            student=profile.student,
            source_type=profile.platform,
            title=title,
            source_url=stats.get("profile_url", ""),
            external_reference=profile.username,
            extracted_data=data,
            tags=_tags(profile),
        )
        profile.evidence = item
        profile.save(update_fields=["evidence", "updated_at"])
        return item
    return evidence_services.refresh_synced_evidence(
        item,
        title=title,
        source_url=stats.get("profile_url", item.source_url),
        extracted_data=data,
        tags=_tags(profile),
    )


def _retire_evidence(profile):
    if profile.evidence_id:
        EvidenceItem.objects.filter(pk=profile.evidence_id).exclude(
            verification_status=VerificationStatus.VERIFIED
        ).delete()


def coding_activity(student_ids):
    """{student_id: (score 0-100 or None, [platform rows])}: the mean of synced platform ratings."""
    rows = {}
    for p in CodingProfile.objects.filter(student_id__in=student_ids):
        rows.setdefault(p.student_id, []).append(p)
    result = {}
    for sid, profiles in rows.items():
        scored = [float(p.score) for p in profiles if p.status == SyncStatus.OK and p.score is not None]
        result[sid] = (round(sum(scored) / len(scored), 2) if scored else None, profiles)
    return result


def due_for_refresh(now=None):
    now = now or timezone.now()
    return CodingProfile.objects.filter(last_synced_at__lt=now - AUTO_REFRESH_INTERVAL) | CodingProfile.objects.filter(
        last_synced_at__isnull=True
    )
