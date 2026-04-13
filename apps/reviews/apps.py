from django.apps import AppConfig


class ReviewsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.reviews"
    label = "reviews"
    verbose_name = "Reviews"

    def ready(self) -> None:
        import apps.reviews.signals  # noqa: F401
