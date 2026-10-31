from drf_spectacular.extensions import OpenApiAuthenticationExtension


class CookieJWTScheme(OpenApiAuthenticationExtension):
    target_class = "apps.accounts.authentication.CookieJWTAuthentication"
    name = "internalCookieAuth"

    def get_security_definition(self, auto_schema):
        return {"type": "apiKey", "in": "cookie", "name": "pa_access"}


class RecruiterCookieJWTScheme(OpenApiAuthenticationExtension):
    target_class = "apps.accounts.authentication.RecruiterCookieJWTAuthentication"
    name = "recruiterCookieAuth"

    def get_security_definition(self, auto_schema):
        return {"type": "apiKey", "in": "cookie", "name": "rc_access"}
