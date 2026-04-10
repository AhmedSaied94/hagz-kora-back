from django.urls import path

from api.v1.auth.views import PlayerMeView

urlpatterns = [
    path("me/", PlayerMeView.as_view(), name="player-me"),
]
