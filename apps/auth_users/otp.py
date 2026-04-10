"""
OTP service — Redis-backed phone one-time passwords.

Security properties:
- OTPs are stored as SHA-256 hashes; plaintext never persists.
- OTP is invalidated immediately after successful verification.
- 3 failed verify attempts → phone locked for 15 minutes.
- 3 OTP requests per phone per 15 minutes (prevents SMS flooding).
"""

import hashlib
import secrets

from django.core.cache import cache

# ── TTLs (seconds) ────────────────────────────────────────────────────────────
OTP_TTL = 300  # OTP valid for 5 minutes
LOCK_TTL = 900  # Lock lasts 15 minutes after 3 failed attempts
REQUEST_TTL = 900  # Rate-limit window: 15 minutes

# ── Limits ────────────────────────────────────────────────────────────────────
MAX_VERIFY_ATTEMPTS = 3
MAX_OTP_REQUESTS = 3


# ── Redis key helpers ─────────────────────────────────────────────────────────


def _otp_key(phone: str) -> str:
    return f"otp:hash:{phone}"


def _attempts_key(phone: str) -> str:
    return f"otp:attempts:{phone}"


def _requests_key(phone: str) -> str:
    return f"otp:requests:{phone}"


# ── Custom exceptions ─────────────────────────────────────────────────────────


class OTPError(Exception):
    """Base class for OTP errors."""


class OTPRateLimitExceeded(OTPError):
    """Too many OTP requests for this phone within the rate-limit window."""


class OTPLockedOut(OTPError):
    """Too many failed verify attempts — phone is temporarily locked."""


class OTPExpired(OTPError):
    """No active OTP found for this phone (expired or never requested)."""


class OTPInvalid(OTPError):
    """Provided OTP does not match the stored hash."""


# ── Public API ────────────────────────────────────────────────────────────────


def generate_otp(phone: str) -> str:
    """
    Generate a 6-digit OTP for ``phone``, store its hash in Redis, and return
    the plaintext OTP so the caller can send it via SMS.

    Raises:
        OTPRateLimitExceeded: if more than MAX_OTP_REQUESTS have been generated
            for this phone within the REQUEST_TTL window.
    """
    requests_key = _requests_key(phone)
    request_count = cache.get(requests_key, 0)
    if request_count >= MAX_OTP_REQUESTS:
        raise OTPRateLimitExceeded(f"Too many OTP requests for {phone}. Try again in 15 minutes.")

    otp = f"{secrets.randbelow(1_000_000):06d}"
    hashed = _hash(otp)

    cache.set(_otp_key(phone), hashed, OTP_TTL)
    # Increment request counter (preserve existing TTL on first set, then keep the window)
    if request_count == 0:
        cache.set(requests_key, 1, REQUEST_TTL)
    else:
        cache.set(requests_key, request_count + 1, REQUEST_TTL)

    return otp


def verify_otp(phone: str, otp: str) -> None:
    """
    Verify ``otp`` against the stored hash for ``phone``.

    On success: clears the OTP and attempt counter from Redis.
    On failure: increments the attempt counter; locks the phone after MAX_VERIFY_ATTEMPTS.

    Raises:
        OTPLockedOut:  attempt counter already at/above MAX_VERIFY_ATTEMPTS.
        OTPExpired:    no OTP found in Redis (expired or never generated).
        OTPInvalid:    OTP does not match.
    """
    attempts_key = _attempts_key(phone)
    attempts = cache.get(attempts_key, 0)

    if attempts >= MAX_VERIFY_ATTEMPTS:
        raise OTPLockedOut(f"Phone {phone} is locked. Try again in 15 minutes.")

    stored_hash = cache.get(_otp_key(phone))
    if stored_hash is None:
        raise OTPExpired("OTP has expired or was never requested.")

    if _hash(otp) != stored_hash:
        new_attempts = attempts + 1
        cache.set(attempts_key, new_attempts, LOCK_TTL)
        if new_attempts >= MAX_VERIFY_ATTEMPTS:
            raise OTPLockedOut(f"Too many failed attempts. Phone {phone} is locked for 15 minutes.")
        raise OTPInvalid("Invalid OTP.")

    # Success — purge both keys immediately
    cache.delete(_otp_key(phone))
    cache.delete(attempts_key)


# ── Internal helpers ──────────────────────────────────────────────────────────


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()
