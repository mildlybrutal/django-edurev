from .base import *  # noqa: F403
from .base import env

DEBUG = env.bool("DJANGO_DEBUG", default=True)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "backend"])
# Local dev runs over plain http.
AUTH_COOKIE_SECURE = env.bool("AUTH_COOKIE_SECURE", default=False)
# The browser talks to Next (port 3000), which proxies /api to Django, so Django sees a
# cross-host Origin on unsafe requests. Trust the local frontend origin.
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=["http://localhost:3000", "http://127.0.0.1:3000"])
# Demo convenience: MFA is available but not forced locally. Production keeps the base default.
MFA_REQUIRED_ROLES = env.list("MFA_REQUIRED_ROLES", default=[])
# Faster feedback locally; production keeps the 30 s base default.
PROFILE_RECOMPUTE_DEBOUNCE_SECONDS = env.int("PROFILE_RECOMPUTE_DEBOUNCE_SECONDS", default=5)
