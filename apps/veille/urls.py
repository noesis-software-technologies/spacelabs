from django.urls import path

from . import views

app_name = "veille"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("articles/", views.articles, name="articles"),
    path("articles/<int:pk>/", views.article_detail, name="article_detail"),
]
