"""
Unit tests for Stadium model business logic.
"""

import pytest

from apps.stadiums.models import StadiumStatus
from tests.factories import StadiumFactory


@pytest.mark.unit
class TestStadiumStatusTransitions:
    def test_submit_for_review_from_draft(self):
        stadium = StadiumFactory.build(status=StadiumStatus.DRAFT)
        # Don't hit DB — just test the state machine logic
        # Monkey-patch save so we can run unit-style
        calls = []
        stadium.save = lambda update_fields=None: calls.append(update_fields)
        stadium.submit_for_review()
        assert stadium.status == StadiumStatus.PENDING_REVIEW
        assert stadium.rejection_note == ""
        assert calls  # save was called

    def test_submit_raises_if_not_draft(self):
        stadium = StadiumFactory.build(status=StadiumStatus.ACTIVE)
        with pytest.raises(ValueError, match="Cannot submit"):
            stadium.submit_for_review()

    def test_approve_from_pending_review(self):
        stadium = StadiumFactory.build(status=StadiumStatus.PENDING_REVIEW)
        stadium.save = lambda update_fields=None: None
        stadium.approve()
        assert stadium.status == StadiumStatus.ACTIVE

    def test_approve_raises_if_not_pending(self):
        stadium = StadiumFactory.build(status=StadiumStatus.DRAFT)
        with pytest.raises(ValueError, match="Cannot approve"):
            stadium.approve()

    def test_reject_sets_draft_and_note(self):
        stadium = StadiumFactory.build(status=StadiumStatus.PENDING_REVIEW)
        stadium.save = lambda update_fields=None: None
        stadium.reject(note="Missing photos.")
        assert stadium.status == StadiumStatus.DRAFT
        assert stadium.rejection_note == "Missing photos."

    def test_reject_raises_if_not_pending(self):
        stadium = StadiumFactory.build(status=StadiumStatus.ACTIVE)
        with pytest.raises(ValueError, match="Cannot reject"):
            stadium.reject(note="nope")

    def test_str_returns_name_ar(self):
        stadium = StadiumFactory.build(name_ar="ملعب النور", pk=1)
        assert "ملعب النور" in str(stadium)
