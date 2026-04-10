from rest_framework.routers import DefaultRouter

from .views import PitchViewSet

router = DefaultRouter()
router.register(r"pitches", PitchViewSet, basename="pitch")

urlpatterns = router.urls
