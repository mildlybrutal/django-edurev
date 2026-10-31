from django.apps import AppConfig


class ProfilesConfig(AppConfig):
    name = "apps.profiles"

    def ready(self):
        from . import receivers  # noqa: F401
