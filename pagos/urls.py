from django.urls import path

from .views import oauth_callback, oauth_conectar, oauth_estado, webhook_mp

urlpatterns = [
    path("webhook/", webhook_mp, name="mp-webhook"),
    path("oauth/conectar/", oauth_conectar, name="mp-oauth-conectar"),
    path("oauth/estado/", oauth_estado, name="mp-oauth-estado"),
    path("oauth/callback/", oauth_callback, name="mp-oauth-callback"),
]
