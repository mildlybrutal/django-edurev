"""File storage in PostgreSQL (ADR 0011). Used when FILE_STORAGE is "database", the default:
hosts such as Render have no object storage, and CES §1.1 forbids keeping uploads on the app
server's disk. Files are small (5 MB caps) and few, so storing their bytes in the database is
acceptable for this scale; set FILE_STORAGE=s3 to use S3-compatible storage instead.

Files are never served by name. `signed_url` returns a link carrying a signed, expiring token,
the same model as an S3 pre-signed URL; `apps.core.views.StoredFileView` serves it."""

import time

from django.conf import settings
from django.core import signing
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible

LINK_SALT = "apps.core.stored-file-link"


@deconstructible
class DatabaseStorage(Storage):
    def _model(self):
        from apps.core.models import StoredFile

        return StoredFile

    def _open(self, name, mode="rb"):
        try:
            row = self._model().objects.only("content").get(name=name)
        except self._model().DoesNotExist as exc:
            raise FileNotFoundError(name) from exc
        f = ContentFile(bytes(row.content))
        f.name = name
        return f

    def _save(self, name, content):
        content.seek(0)
        data = b"".join(content.chunks())
        self._model().objects.create(name=name, content=data, size=len(data))
        return name

    def delete(self, name):
        self._model().objects.filter(name=name).delete()

    def exists(self, name):
        return self._model().objects.filter(name=name).exists()

    def size(self, name):
        row = self._model().objects.filter(name=name).values_list("size", flat=True).first()
        if row is None:
            raise FileNotFoundError(name)
        return row

    def url(self, name):
        return self.signed_url(name)

    def signed_url(self, name, expires=None, content_type="application/octet-stream"):
        """A relative link (the browser reaches Django through the Next.js /api/v1 rewrite) that
        stops working `expires` seconds from now."""
        expires = expires or getattr(settings, "RESUME_URL_EXPIRY_SECONDS", 300)
        payload = {"n": name, "ct": content_type, "x": int(time.time()) + int(expires)}
        return f"/api/v1/files/{signing.dumps(payload, salt=LINK_SALT, compress=True)}/"


class LinkExpired(signing.BadSignature):
    pass


def read_link(token, now=None):
    """(name, content_type) for a valid, unexpired link token. Raises signing.BadSignature for a
    tampered token and LinkExpired (a BadSignature) for an expired one."""
    data = signing.loads(token, salt=LINK_SALT)
    if (now if now is not None else time.time()) > data["x"]:
        raise LinkExpired("Link expired")
    return data["n"], data["ct"]
