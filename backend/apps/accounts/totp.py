"""RFC 6238 TOTP (HMAC-SHA1, 30 s steps, 6 digits): the scheme authenticator apps implement.
Standard library only; verified against the RFC's published test vectors."""

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote, urlencode

STEP = 30
DIGITS = 6


def new_secret():
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _key(secret_b32):
    padded = secret_b32 + "=" * (-len(secret_b32) % 8)
    return base64.b32decode(padded.upper())


def hotp(key, counter, digits=DIGITS):
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(code % (10**digits)).zfill(digits)


def totp(secret_b32, at=None, digits=DIGITS):
    at = time.time() if at is None else at
    return hotp(_key(secret_b32), int(at // STEP), digits)


def verify(secret_b32, code, *, at=None, window=1, last_counter=None):
    """Return the matching time-step counter, or None. Accepts ±`window` steps for clock drift
    and rejects any counter at or before `last_counter` (no code can be replayed)."""
    code = (code or "").strip().replace(" ", "")
    if not code.isdigit() or len(code) != DIGITS:
        return None
    at = time.time() if at is None else at
    key = _key(secret_b32)
    now = int(at // STEP)
    for counter in range(now - window, now + window + 1):
        if last_counter is not None and counter <= last_counter:
            continue
        if hmac.compare_digest(hotp(key, counter), code):
            return counter
    return None


def provisioning_uri(secret_b32, account, issuer="Placement Readiness"):
    label = quote(f"{issuer}:{account}")
    return f"otpauth://totp/{label}?" + urlencode(
        {"secret": secret_b32, "issuer": issuer, "digits": DIGITS, "period": STEP}
    )
