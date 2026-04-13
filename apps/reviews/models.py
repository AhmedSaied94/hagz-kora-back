from __future__ import annotations

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.models import TimeStampedModel

RATING_VALIDATORS = [MinValueValidator(1), MaxValueValidator(5)]


class Review(TimeStampedModel):
    booking = models.OneToOneField(
        "bookings.Booking",
        on_delete=models.CASCADE,
        related_name="review",
    )
    player = models.ForeignKey(
        "auth_users.User",
        on_delete=models.CASCADE,
        related_name="reviews",
        limit_choices_to={"role": "player"},
    )
    stadium = models.ForeignKey(
        "stadiums.Stadium",
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    overall_rating = models.IntegerField(validators=RATING_VALIDATORS)
    pitch_quality = models.IntegerField(validators=RATING_VALIDATORS, null=True, blank=True)
    facilities = models.IntegerField(validators=RATING_VALIDATORS, null=True, blank=True)
    value_for_money = models.IntegerField(validators=RATING_VALIDATORS, null=True, blank=True)
    text = models.TextField(max_length=500, blank=True)
    owner_response = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "review"
        verbose_name_plural = "reviews"

    def __str__(self) -> str:
        return (
            f"Review({self.pk}) by {self.player_id} for {self.stadium_id} [{self.overall_rating}★]"
        )
