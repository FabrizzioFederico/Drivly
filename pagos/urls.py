from django.urls import path

from .views import webhook_mp

urlpatterns = [
    path("webhook/", webhook_mp, name="mp-webhook"),
]
