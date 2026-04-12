"""Domain exceptions for the bookings app.

These are raised from the service layer. The API view layer is responsible
for mapping each exception to an HTTP status + error code.
"""

from __future__ import annotations


class BookingError(Exception):
    """Base class for all booking domain errors."""


class SlotNotAvailable(BookingError):
    """The slot exists but is not in the 'available' state (booked/blocked)."""


class LockAcquisitionFailed(BookingError):
    """Another worker currently holds the slot lock — treat as SLOT_TAKEN."""


class StadiumInactive(BookingError):
    """The stadium is not in the 'active' state and cannot accept bookings."""


class BookingLockUnavailable(BookingError):
    """Redis is unreachable — the booking subsystem is temporarily degraded."""


class BookingNotCancellable(BookingError):
    """The booking is not in a state that allows player cancellation."""
