"""Base settings shared by every environment.

All configuration comes from environment variables (CES §1.2). See
docs/env.md for the full reference and .env.example for local defaults.
"""

from datetime import timedelta
from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # backend/
REPO_ROOT = BASE_DIR.parent

env = environ.Env()
if (REPO_ROOT / ".env").exists():
    environ.Env.read_env(REPO_ROOT / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "apps.core",
    "apps.accounts",
    "apps.taxonomy",
    "apps.students",
    "apps.notifications",
    "apps.evidence",
    "apps.verification",
    "apps.profiles",
    "apps.assessments",
    "apps.readiness",
    "apps.drives",
    "apps.matching",
    "apps.planning",
    "apps.reporting",
    "apps.recruiter",
    "apps.coding",
    "apps.demo",
]

MIDDLEWARE = [
    "apps.core.middleware.LivenessMiddleware",  # first: platform health checks skip host checks
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DATABASE_CONN_MAX_AGE", default=60)
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("REDIS_URL"),
    }
}

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Uploaded files (resumes, certificates) never live on the app server's disk (CES §1.1). They are
# stored in PostgreSQL by default (ADR 0011), or in S3-compatible object storage with FILE_STORAGE=s3.
FILE_STORAGE = env("FILE_STORAGE", default="database")
if FILE_STORAGE not in ("database", "s3"):
    raise ImproperlyConfigured('FILE_STORAGE must be "database" or "s3".')
RESUME_S3_PUBLIC_URL = env("RESUME_S3_PUBLIC_URL", default="")
RESUME_MAX_BYTES = env.int("RESUME_MAX_BYTES", default=5 * 1024 * 1024)
RESUME_URL_EXPIRY_SECONDS = env.int("RESUME_URL_EXPIRY_SECONDS", default=300)
CERTIFICATE_MAX_BYTES = env.int("CERTIFICATE_MAX_BYTES", default=5 * 1024 * 1024)
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    "resumes": {"BACKEND": "apps.core.file_storage.DatabaseStorage"}
    if FILE_STORAGE == "database"
    else {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": env("RESUME_S3_BUCKET", default="resumes"),
            "endpoint_url": env("RESUME_S3_ENDPOINT_URL", default="http://localhost:8333"),
            "access_key": env("RESUME_S3_ACCESS_KEY", default=""),
            "secret_key": env("RESUME_S3_SECRET_KEY", default=""),
            "region_name": env("RESUME_S3_REGION", default="us-east-1"),
            "default_acl": None,
            "querystring_auth": True,
            "file_overwrite": False,
            "addressing_style": "path",
            "signature_version": "s3v4",
        },
    },
}

GITHUB_TOKEN = env("GITHUB_TOKEN", default="")

REST_FRAMEWORK = {
    # Internal portal by default; the recruiter app overrides this per view (P06 §16).
    "DEFAULT_AUTHENTICATION_CLASSES": ["apps.accounts.authentication.CookieJWTAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": env("THROTTLE_ANON", default="60/min"),
        "user": env("THROTTLE_USER", default="600/min"),
        "login": env("THROTTLE_LOGIN", default="10/min"),
        "signup": env("THROTTLE_SIGNUP", default="5/min"),
        "token_refresh": env("THROTTLE_TOKEN_REFRESH", default="30/min"),
        # Recruiter portal has its own, stricter scopes (P06 §7).
        "recruiter": env("THROTTLE_RECRUITER", default="30/min"),
        "recruiter_login": env("THROTTLE_RECRUITER_LOGIN", default="5/min"),
        # Opening a signed file link (resume or certificate viewer), per IP.
        "file_link": env("THROTTLE_FILE_LINK", default="60/min"),
    },
    "NUM_PROXIES": env.int("NUM_PROXIES", default=0),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env.int("JWT_ACCESS_MINUTES", default=10)),
    "REFRESH_TOKEN_LIFETIME": timedelta(hours=env.int("JWT_REFRESH_HOURS", default=24)),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "SIGNING_KEY": env("JWT_SIGNING_KEY", default=SECRET_KEY),
}

# Separate cookie names and paths per portal so recruiter and internal sessions never mix.
AUTH_COOKIES = {
    "internal": {
        "access": "pa_access",
        "access_path": "/",
        "refresh": "pa_refresh",
        "refresh_path": "/api/v1/auth/",
        "mfa": "pa_mfa",
    },
    "recruiter": {
        "access": "rc_access",
        "access_path": "/api/v1/recruiter/",
        "refresh": "rc_refresh",
        "refresh_path": "/api/v1/recruiter/auth/",
        "mfa": "rc_mfa",
    },
}
AUTH_COOKIE_SECURE = env.bool("AUTH_COOKIE_SECURE", default=not DEBUG)
AUTH_COOKIE_SAMESITE = "Lax"
AUTH_COOKIE_DOMAIN = env("AUTH_COOKIE_DOMAIN", default=None)
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# CES §1.1: TOTP MFA for admin roles. Users in these roles get a restricted session until enrolled.
MFA_REQUIRED_ROLES = env.list("MFA_REQUIRED_ROLES", default=["admin", "placement_head", "placement_officer"])

LOGIN_LOCKOUT_THRESHOLD = env.int("LOGIN_LOCKOUT_THRESHOLD", default=5)
LOGIN_LOCKOUT_SECONDS = env.int("LOGIN_LOCKOUT_SECONDS", default=15 * 60)

SPECTACULAR_SETTINGS = {
    "TITLE": "Placement Skill Matcher & Readiness Analyser API",
    "VERSION": "1.0.0",
    "SCHEMA_PATH_PREFIX": "/api/v1",
    "SERVE_INCLUDE_SCHEMA": False,
    "ENUM_NAME_OVERRIDES": {
        "LevelEnum": "apps.taxonomy.models.Level",
        "PositiveLevelEnum": "apps.taxonomy.models.POSITIVE_LEVEL_CHOICES",
        "AssessmentKindEnum": "apps.assessments.models.AssessmentKind",
        "ResourceKindEnum": "apps.planning.models.ResourceKind",
        "GapKindEnum": "apps.matching.models.GapKind",
        "DriveStatusEnum": "apps.drives.models.DriveStatus",
        "RegistrationStatusEnum": "apps.drives.models.RegistrationStatus",
        "VerificationStatusEnum": "apps.evidence.models.VerificationStatus",
        "GrantStatusEnum": "apps.recruiter.models.GrantStatus",
        "PlanStatusEnum": "apps.planning.models.PlanStatus",
        "ItemStatusEnum": "apps.planning.models.ItemStatus",
        "JobStatusEnum": "apps.core.models.JobStatus",
        "JDStatusEnum": "apps.drives.models.JDStatus",
    },
}

CELERY_BROKER_URL = env("CELERY_BROKER_URL", default=env("REDIS_URL"))
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default=env("REDIS_URL"))
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_TIME_LIMIT = 30 * 60
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULE = {
    "checkpoint-reminders": {
        "task": "apps.planning.tasks.checkpoint_reminders",
        "schedule": 60 * 60 * 24,
    },
    "coding-profiles-refresh": {
        "task": "apps.coding.tasks.refresh_stale_profiles",
        "schedule": 60 * 60 * 6,
    },
}

PROFILE_RECOMPUTE_DEBOUNCE_SECONDS = env.int("PROFILE_RECOMPUTE_DEBOUNCE_SECONDS", default=30)
RECRUITER_BROADCASTS_PER_DAY = env.int("RECRUITER_BROADCASTS_PER_DAY", default=5)
NOTIFICATION_EMAIL_KINDS = env.list(
    "NOTIFICATION_EMAIL_KINDS", default=["verification_completed", "shortlist_result", "checkpoint_due"]
)
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="placement@localhost")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"json": {"()": "apps.core.logging.JsonFormatter"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "json"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", default="INFO")},
}
