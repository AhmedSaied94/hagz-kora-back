"""
Phase 1 migration — Auth & User Profiles.

Changes vs 0001 (Phase 0 AbstractUser stub):
  - Remove username, first_name, last_name (replaced by full_name + phone)
  - Add phone (unique, nullable — allows email-only dev accounts)
  - Make email unique
  - Add full_name, role, kyc_status
  - Switch manager to apps.auth_users.models.UserManager
  - Add PlayerProfile and OwnerProfile tables
"""

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

import apps.auth_users.models


class Migration(migrations.Migration):
    dependencies = [
        ("auth_users", "0001_initial"),
    ]

    operations = [
        # ── Remove legacy AbstractUser fields no longer needed ────────────────
        migrations.RemoveField(model_name="user", name="username"),
        migrations.RemoveField(model_name="user", name="first_name"),
        migrations.RemoveField(model_name="user", name="last_name"),
        # ── Add new Phase 1 fields ────────────────────────────────────────────
        migrations.AddField(
            model_name="user",
            name="phone",
            field=models.CharField(blank=True, max_length=20, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="user",
            name="full_name",
            field=models.CharField(default="", max_length=200),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("player", "Player"),
                    ("owner", "Owner"),
                    ("admin", "Admin"),
                ],
                default="player",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="kyc_status",
            field=models.CharField(
                choices=[
                    ("pending_kyc", "Pending KYC"),
                    ("under_review", "Under Review"),
                    ("kyc_approved", "KYC Approved"),
                    ("kyc_rejected", "KYC Rejected"),
                ],
                default="pending_kyc",
                max_length=20,
            ),
        ),
        # ── Make email unique ─────────────────────────────────────────────────
        migrations.AlterField(
            model_name="user",
            name="email",
            field=models.EmailField(max_length=254, unique=True),
        ),
        # ── Swap manager ──────────────────────────────────────────────────────
        migrations.AlterModelManagers(
            name="user",
            managers=[
                ("objects", apps.auth_users.models.UserManager()),
            ],
        ),
        # ── PlayerProfile ─────────────────────────────────────────────────────
        migrations.CreateModel(
            name="PlayerProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("city", models.CharField(blank=True, max_length=100)),
                ("date_of_birth", models.DateField(blank=True, null=True)),
                ("preferred_position", models.CharField(blank=True, max_length=50)),
                ("avatar", models.ImageField(blank=True, null=True, upload_to="avatars/")),
                ("bio", models.TextField(blank=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="player_profile",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "player profile",
                "verbose_name_plural": "player profiles",
            },
        ),
        # ── OwnerProfile ──────────────────────────────────────────────────────
        migrations.CreateModel(
            name="OwnerProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("business_name_ar", models.CharField(max_length=200)),
                ("business_name_en", models.CharField(blank=True, max_length=200)),
                ("national_id_number", models.CharField(max_length=50)),
                ("city", models.CharField(blank=True, max_length=100)),
                ("national_id_front", models.ImageField(blank=True, null=True, upload_to="kyc/")),
                ("national_id_back", models.ImageField(blank=True, null=True, upload_to="kyc/")),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="owner_profile",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "owner profile",
                "verbose_name_plural": "owner profiles",
            },
        ),
    ]
