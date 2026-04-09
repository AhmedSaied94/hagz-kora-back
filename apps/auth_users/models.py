from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """
    Custom user model — extended in Phase 1.

    Placeholder so Django's AUTH_USER_MODEL = "auth_users.User" resolves
    before full profile fields are added in Phase 1 (auth & profiles).
    """

    class Meta:
        verbose_name = "user"
        verbose_name_plural = "users"
