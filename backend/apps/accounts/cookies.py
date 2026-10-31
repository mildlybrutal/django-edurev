from django.conf import settings


def _cookie_kwargs(path, max_age):
    return {
        "max_age": int(max_age.total_seconds()),
        "path": path,
        "domain": settings.AUTH_COOKIE_DOMAIN,
        "secure": settings.AUTH_COOKIE_SECURE,
        "httponly": True,
        "samesite": settings.AUTH_COOKIE_SAMESITE,
    }


def set_auth_cookies(response, tokens, portal):
    names = settings.AUTH_COOKIES[portal]
    jwt = settings.SIMPLE_JWT
    response.set_cookie(
        names["access"], tokens.access, **_cookie_kwargs(names["access_path"], jwt["ACCESS_TOKEN_LIFETIME"])
    )
    response.set_cookie(
        names["refresh"], tokens.refresh, **_cookie_kwargs(names["refresh_path"], jwt["REFRESH_TOKEN_LIFETIME"])
    )


def clear_auth_cookies(response, portal):
    names = settings.AUTH_COOKIES[portal]
    for name, path in ((names["access"], names["access_path"]), (names["refresh"], names["refresh_path"])):
        response.delete_cookie(
            name, path=path, domain=settings.AUTH_COOKIE_DOMAIN, samesite=settings.AUTH_COOKIE_SAMESITE
        )
