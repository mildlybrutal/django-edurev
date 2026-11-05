import os

# Tests never need a real secret; set a placeholder before base reads the env.
os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-not-a-secret")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from .base import *  # noqa: E402, F403

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CSRF_TRUSTED_ORIGINS = ["http://localhost:3000"]
# Individual tests opt in to MFA enforcement with override_settings.
MFA_REQUIRED_ROLES = []
