from django.urls import path

from api.v1.auth.views import OwnerMeView, OwnerRegisterView

urlpatterns = [
    path("register/", OwnerRegisterView.as_view(), name="owner-register"),
    path("me/", OwnerMeView.as_view(), name="owner-me"),
]
