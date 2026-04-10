from django.urls import path

from api.v1.notifications.views import DeviceTokenView

urlpatterns = [
    path("", DeviceTokenView.as_view(), name="device-register"),
    path("<str:token>/", DeviceTokenView.as_view(), name="device-deregister"),
]
