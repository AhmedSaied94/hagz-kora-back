from __future__ import annotations

import secrets

from django.conf import settings
from django.db import models
from django.utils.text import slugify

from apps.core.models import TimeStampedModel


class TournamentFormat(models.TextChoices):
    ROUND_ROBIN = "round_robin", "Round Robin"
    KNOCKOUT = "knockout", "Knockout"
    GROUP_KNOCKOUT = "group_knockout", "Group then Knockout"


class TournamentStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    REGISTRATION_OPEN = "registration_open", "Registration Open"
    REGISTRATION_CLOSED = "registration_closed", "Registration Closed"
    IN_PROGRESS = "in_progress", "In Progress"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


class FixtureStatus(models.TextChoices):
    SCHEDULED = "scheduled", "Scheduled"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


class FixtureStage(models.TextChoices):
    GROUP = "group", "Group"
    KNOCKOUT = "knockout", "Knockout"


class Tournament(TimeStampedModel):
    stadium = models.ForeignKey(
        "stadiums.Stadium",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tournaments",
    )
    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organized_tournaments",
        limit_choices_to={"role": "owner"},
    )
    name = models.CharField(max_length=200)
    format = models.CharField(max_length=20, choices=TournamentFormat.choices)
    max_teams = models.PositiveIntegerField()
    registration_deadline = models.DateTimeField()
    start_date = models.DateField()
    status = models.CharField(
        max_length=25,
        choices=TournamentStatus.choices,
        default=TournamentStatus.DRAFT,
        db_index=True,
    )
    prize_info = models.TextField(blank=True)
    rules = models.TextField(blank=True)
    public_slug = models.SlugField(max_length=100, unique=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.public_slug:
            base = slugify(self.name) or "tournament"
            slug = base
            n = 1
            while Tournament.objects.filter(public_slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{n}"
                n += 1
            self.public_slug = slug
        super().save(*args, **kwargs)


class TournamentTeam(TimeStampedModel):
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name="teams")
    name = models.CharField(max_length=100)
    captain = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="captained_teams",
        limit_choices_to={"role": "player"},
    )
    join_code = models.CharField(max_length=10, unique=True, db_index=True)
    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["registered_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.tournament})"

    def save(self, *args, **kwargs):
        if not self.join_code:
            while True:
                code = secrets.token_urlsafe(6)[:8].upper()
                if not TournamentTeam.objects.filter(join_code=code).exists():
                    self.join_code = code
                    break
        super().save(*args, **kwargs)


class TournamentPlayer(TimeStampedModel):
    team = models.ForeignKey(TournamentTeam, on_delete=models.CASCADE, related_name="players")
    player = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tournament_memberships",
        limit_choices_to={"role": "player"},
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("team", "player")
        ordering = ["joined_at"]

    def __str__(self) -> str:
        return f"{self.player} in {self.team}"


class Fixture(TimeStampedModel):
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name="fixtures")
    home_team = models.ForeignKey(
        TournamentTeam,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="home_fixtures",
    )
    away_team = models.ForeignKey(
        TournamentTeam,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="away_fixtures",
    )
    round_number = models.PositiveIntegerField()
    scheduled_at = models.DateTimeField(null=True, blank=True)
    home_score = models.PositiveIntegerField(null=True, blank=True)
    away_score = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=FixtureStatus.choices,
        default=FixtureStatus.SCHEDULED,
        db_index=True,
    )
    stage = models.CharField(
        max_length=10,
        choices=FixtureStage.choices,
        default=FixtureStage.KNOCKOUT,
    )
    group_name = models.CharField(max_length=5, blank=True)
    is_bye = models.BooleanField(default=False)

    class Meta:
        ordering = ["round_number", "scheduled_at"]

    def __str__(self) -> str:
        return f"Round {self.round_number}: {self.home_team} vs {self.away_team}"
