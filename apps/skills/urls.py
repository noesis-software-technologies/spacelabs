from django.urls import path

from . import views

app_name = "skills"

urlpatterns = [
    path("w/<slug:slug>/", views.panel, name="panel"),
    path("<int:pk>/appliquer/", views.apply, name="apply"),
]
