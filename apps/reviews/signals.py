from __future__ import annotations

from django.db import models
from django.db.models import Avg
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.reviews.models import Review


def _update_stadium_rating(stadium) -> None:
    agg = Review.objects.filter(stadium=stadium).aggregate(
        avg=Avg("overall_rating"),
        count=models.Count("id"),
        pitch=Avg("pitch_quality"),
        facilities=Avg("facilities"),
        value=Avg("value_for_money"),
    )
    stadium.avg_rating = agg["avg"] or 0
    stadium.review_count = agg["count"]
    stadium.avg_pitch_quality = agg["pitch"]
    stadium.avg_facilities = agg["facilities"]
    stadium.avg_value_for_money = agg["value"]
    stadium.save(
        update_fields=[
            "avg_rating",
            "review_count",
            "avg_pitch_quality",
            "avg_facilities",
            "avg_value_for_money",
            "updated_at",
        ]
    )


@receiver(post_save, sender=Review)
def update_rating_on_save(sender, instance, **kwargs) -> None:
    _update_stadium_rating(instance.stadium)


@receiver(post_delete, sender=Review)
def update_rating_on_delete(sender, instance, **kwargs) -> None:
    _update_stadium_rating(instance.stadium)
