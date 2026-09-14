from django.urls import path

from . import views

app_name = "vitrine"

urlpatterns = [
    path("", views.vitrine, name="index"),
    path("constellation/", views.vitrine_v2, name="v2"),
    path("savoir-faire/", views.savoir_faire, name="savoir_faire"),
]
