from apps.tournaments.models import Fixture, Tournament, TournamentPlayer, TournamentTeam
from rest_framework import serializers


class PublicTournamentTeamSerializer(serializers.ModelSerializer):
    """Team serializer for unauthenticated public endpoints — omits join_code."""

    captain_name = serializers.CharField(source="captain.full_name", read_only=True)
    player_count = serializers.SerializerMethodField()

    class Meta:
        model = TournamentTeam
        fields = ["id", "name", "captain_name", "player_count", "registered_at"]

    def get_player_count(self, obj: TournamentTeam) -> int:
        return getattr(obj, "players_count", obj.players.count())


class TournamentTeamSerializer(serializers.ModelSerializer):
    captain_name = serializers.CharField(source="captain.full_name", read_only=True)
    player_count = serializers.SerializerMethodField()

    class Meta:
        model = TournamentTeam
        fields = [
            "id",
            "name",
            "captain_name",
            "join_code",
            "registered_at",
            "player_count",
        ]

    def get_player_count(self, obj: TournamentTeam) -> int:
        return getattr(obj, "players_count", obj.players.count())


class TournamentSerializer(serializers.ModelSerializer):
    organizer_name = serializers.CharField(source="organizer.full_name", read_only=True)
    team_count = serializers.SerializerMethodField()

    class Meta:
        model = Tournament
        fields = [
            "id",
            "name",
            "format",
            "status",
            "max_teams",
            "registration_deadline",
            "start_date",
            "prize_info",
            "rules",
            "public_slug",
            "organizer_name",
            "team_count",
            "created_at",
        ]
        read_only_fields = ["status", "public_slug", "organizer_name", "team_count", "created_at"]

    def get_team_count(self, obj: Tournament) -> int:
        return getattr(obj, "teams_count", obj.teams.count())


class TournamentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tournament
        fields = [
            "name",
            "format",
            "max_teams",
            "registration_deadline",
            "start_date",
            "prize_info",
            "rules",
            "stadium",
        ]

    def validate_max_teams(self, value: int) -> int:
        if value < 2:
            raise serializers.ValidationError("max_teams must be at least 2.")
        return value


class FixtureSerializer(serializers.ModelSerializer):
    home_team_name = serializers.CharField(source="home_team.name", read_only=True, allow_null=True)
    away_team_name = serializers.CharField(source="away_team.name", read_only=True, allow_null=True)

    class Meta:
        model = Fixture
        fields = [
            "id",
            "round_number",
            "home_team",
            "home_team_name",
            "away_team",
            "away_team_name",
            "home_score",
            "away_score",
            "status",
            "stage",
            "group_name",
            "scheduled_at",
            "is_bye",
        ]


class ScoreEntrySerializer(serializers.Serializer):
    home_score = serializers.IntegerField(min_value=0)
    away_score = serializers.IntegerField(min_value=0)


class TournamentPlayerSerializer(serializers.ModelSerializer):
    player_name = serializers.CharField(source="player.full_name", read_only=True)
    # player_phone is intentional: teammates need contact details for coordination.
    # This serializer is only returned to authenticated players on the same team (MyTeamView).
    player_phone = serializers.CharField(source="player.phone", read_only=True)

    class Meta:
        model = TournamentPlayer
        fields = ["id", "player", "player_name", "player_phone", "joined_at"]


class TeamRegisterSerializer(serializers.Serializer):
    team_name = serializers.CharField(max_length=100)


class TeamJoinSerializer(serializers.Serializer):
    join_code = serializers.CharField(max_length=10)


class StandingRowSerializer(serializers.Serializer):
    team_id = serializers.IntegerField(source="team.id")
    team_name = serializers.CharField(source="team.name")
    played = serializers.IntegerField()
    won = serializers.IntegerField()
    drawn = serializers.IntegerField()
    lost = serializers.IntegerField()
    goals_for = serializers.IntegerField()
    goals_against = serializers.IntegerField()
    goal_difference = serializers.IntegerField()
    points = serializers.IntegerField()
