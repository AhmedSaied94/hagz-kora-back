"""Redis-backed slot locking primitives for the booking flow.

The lock guarantees at most one in-flight booking attempt per slot across
all web/worker processes. It is *advisory* — the ultimate source of truth
is the partial UniqueConstraint on Booking(slot, status='confirmed').

Key layout:
    hagz:lock:booking:slot:{slot_id}
Value layout:
    "{user_id}:{uuid4hex}"       ← ownership token, checked at release time
TTL:
    10 seconds (the critical section should complete in well under 1s).
"""

from __future__ import annotations

from contextlib import contextmanager
from uuid import uuid4

import redis
from django.conf import settings

from apps.bookings.exceptions import BookingLockUnavailable, LockAcquisitionFailed

LOCK_KEY_TEMPLATE = "hagz:lock:booking:slot:{slot_id}"
LOCK_TTL_MS = 10_000

# Lua: delete the key only if its value still matches our token.
# Guards against releasing a lock that another worker re-acquired after our TTL.
_RELEASE_LUA = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
else
    return 0
end
"""

_client: redis.Redis | None = None


def _get_client() -> redis.Redis:
    """Return a module-level cached redis-py client (lazy init)."""
    global _client
    if _client is None:
        _client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _client


def _key(slot_id: int) -> str:
    return LOCK_KEY_TEMPLATE.format(slot_id=slot_id)


def acquire_slot_lock(slot_id: int, user_id: int) -> str | None:
    """Attempt to acquire the slot lock.

    Returns the ownership token on success, or None if another caller holds
    the lock. Raises BookingLockUnavailable if Redis is unreachable.
    """
    token = f"{user_id}:{uuid4().hex}"
    try:
        acquired = _get_client().set(_key(slot_id), token, nx=True, px=LOCK_TTL_MS)
    except redis.RedisError as exc:
        raise BookingLockUnavailable("Redis unavailable while acquiring slot lock.") from exc
    return token if acquired else None


def release_slot_lock(slot_id: int, token: str) -> bool:
    """Release the lock iff it is still owned by `token`.

    Returns True on successful release, False if the token no longer matches
    (e.g. TTL expired and another worker now owns the key).
    """
    try:
        result = _get_client().eval(_RELEASE_LUA, 1, _key(slot_id), token)
    except redis.RedisError:
        # Swallow release errors — the lock TTL will free the key on its own.
        return False
    return bool(result)


@contextmanager
def booking_slot_lock(slot_id: int, user_id: int):
    """Context manager acquiring the slot lock for the critical section.

    Raises LockAcquisitionFailed if the lock is held by another caller,
    or BookingLockUnavailable if Redis is down.
    """
    token = acquire_slot_lock(slot_id, user_id)
    if token is None:
        raise LockAcquisitionFailed(f"Slot {slot_id} is currently being booked.")
    try:
        yield token
    finally:
        release_slot_lock(slot_id, token)
