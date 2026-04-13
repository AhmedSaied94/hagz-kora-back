from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("stadiums", "0003_add_booking_and_slot_indexes"),
    ]

    operations = [
        migrations.AddField(
            model_name="stadium",
            name="avg_rating",
            field=models.DecimalField(db_index=True, decimal_places=2, default=0, max_digits=3),
        ),
        migrations.AddField(
            model_name="stadium",
            name="review_count",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
