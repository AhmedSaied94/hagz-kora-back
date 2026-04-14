from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("stadiums", "0004_stadium_avg_rating"),
    ]

    operations = [
        migrations.AddField(
            model_name="stadium",
            name="avg_pitch_quality",
            field=models.DecimalField(
                blank=True, decimal_places=2, default=None, max_digits=3, null=True
            ),
        ),
        migrations.AddField(
            model_name="stadium",
            name="avg_facilities",
            field=models.DecimalField(
                blank=True, decimal_places=2, default=None, max_digits=3, null=True
            ),
        ),
        migrations.AddField(
            model_name="stadium",
            name="avg_value_for_money",
            field=models.DecimalField(
                blank=True, decimal_places=2, default=None, max_digits=3, null=True
            ),
        ),
    ]
