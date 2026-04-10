"""
Unit tests for apps.auth_users.otp

Uses Django's cache framework with a LocMemCache backend so these tests
run without Redis and stay fast (@pytest.mark.unit).
"""

import pytest
from apps.auth_users.otp import (
    MAX_OTP_REQUESTS,
    MAX_VERIFY_ATTEMPTS,
    OTPExpired,
    OTPInvalid,
    OTPLockedOut,
    OTPRateLimitExceeded,
    _hash,
    _otp_key,
    generate_otp,
    verify_otp,
)
from django.core.cache import cache

PHONE = "+201012345678"


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear the cache before every test to avoid state leakage."""
    cache.clear()
    yield
    cache.clear()


# ── generate_otp ─────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_generate_otp_returns_six_digit_string():
    otp = generate_otp(PHONE)
    assert len(otp) == 6
    assert otp.isdigit()


@pytest.mark.unit
def test_generate_otp_stores_hash_in_cache():
    otp = generate_otp(PHONE)
    stored = cache.get(_otp_key(PHONE))
    assert stored is not None
    assert stored == _hash(otp)


@pytest.mark.unit
def test_generate_otp_rate_limit_raises_after_max_requests():
    for _ in range(MAX_OTP_REQUESTS):
        generate_otp(PHONE)

    with pytest.raises(OTPRateLimitExceeded):
        generate_otp(PHONE)


@pytest.mark.unit
def test_generate_otp_different_phones_are_independent():
    other_phone = "+201099999999"
    for _ in range(MAX_OTP_REQUESTS):
        generate_otp(PHONE)

    # Other phone should still work
    otp = generate_otp(other_phone)
    assert len(otp) == 6


# ── verify_otp ────────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_verify_otp_success_clears_cache():
    otp = generate_otp(PHONE)
    verify_otp(PHONE, otp)
    assert cache.get(_otp_key(PHONE)) is None


@pytest.mark.unit
def test_verify_otp_invalid_raises_otp_invalid():
    generate_otp(PHONE)
    with pytest.raises(OTPInvalid):
        verify_otp(PHONE, "000000")


@pytest.mark.unit
def test_verify_otp_expired_raises_otp_expired():
    # No OTP generated for this phone
    with pytest.raises(OTPExpired):
        verify_otp(PHONE, "123456")


@pytest.mark.unit
def test_verify_otp_lockout_after_max_failed_attempts():
    generate_otp(PHONE)
    for _ in range(MAX_VERIFY_ATTEMPTS - 1):
        with pytest.raises(OTPInvalid):
            verify_otp(PHONE, "000000")

    # Final attempt triggers lockout
    with pytest.raises(OTPLockedOut):
        verify_otp(PHONE, "000000")


@pytest.mark.unit
def test_verify_otp_locked_out_phone_raises_even_with_correct_otp():
    otp = generate_otp(PHONE)
    # Exhaust attempts
    for _ in range(MAX_VERIFY_ATTEMPTS):
        try:
            verify_otp(PHONE, "000000")
        except (OTPInvalid, OTPLockedOut):
            pass

    # Even the correct OTP is rejected while locked
    with pytest.raises(OTPLockedOut):
        verify_otp(PHONE, otp)


@pytest.mark.unit
def test_verify_otp_cannot_reuse_after_success():
    otp = generate_otp(PHONE)
    verify_otp(PHONE, otp)
    # Second use must fail with OTPExpired (hash purged)
    with pytest.raises(OTPExpired):
        verify_otp(PHONE, otp)


# ── _hash ─────────────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_hash_is_deterministic():
    assert _hash("123456") == _hash("123456")


@pytest.mark.unit
def test_hash_differs_for_different_inputs():
    assert _hash("123456") != _hash("123457")
