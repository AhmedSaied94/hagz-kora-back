from __future__ import annotations

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("bookings", "0002_add_booking_and_slot_indexes"),
        ("stadiums", "0001_initial"),
        ("auth_users", "0002_phase1_user_profiles"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Review",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "overall_rating",
                    models.IntegerField(
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(5),
                        ]
                    ),
                ),
                (
                    "pitch_quality",
                    models.IntegerField(
                        blank=True,
                        null=True,
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(5),
                        ],
                    ),
                ),
                (
                    "facilities",
                    models.IntegerField(
                        blank=True,
                        null=True,
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(5),
                        ],
                    ),
                ),
                (
                    "value_for_money",
                    models.IntegerField(
                        blank=True,
                        null=True,
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(5),
                        ],
                    ),
                ),
                ("text", models.TextField(blank=True, max_length=500)),
                ("owner_response", models.TextField(blank=True)),
                (
                    "booking",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="review",
                        to="bookings.booking",
                    ),
                ),
                (
                    "player",
                    models.ForeignKey(
                        limit_choices_to={"role": "player"},
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reviews",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "stadium",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reviews",
                        to="stadiums.stadium",
                    ),
                ),
            ],
            options={
                "verbose_name": "review",
                "verbose_name_plural": "reviews",
                "ordering": ["-created_at"],
            },
        ),
    ]
