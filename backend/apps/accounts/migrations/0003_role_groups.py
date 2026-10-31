from django.db import migrations

# Kept literal (not imported from apps.accounts.roles) so this migration never changes meaning.
ROLE_GROUPS = ["student", "faculty", "placement_officer", "placement_head", "recruiter", "admin"]


def create_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for name in ROLE_GROUPS:
        Group.objects.get_or_create(name=name)


def remove_groups(apps, schema_editor):
    apps.get_model("auth", "Group").objects.filter(name__in=ROLE_GROUPS).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [migrations.RunPython(create_groups, remove_groups)]
