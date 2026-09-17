from django.urls import path

from . import views

app_name = "veille"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("articles/", views.articles, name="articles"),
    path("articles/<int:pk>/", views.article_detail, name="article_detail"),
    path("articles/<int:pk>/edit/", views.article_edit, name="article_edit"),
    path("articles/<int:pk>/save/", views.article_save, name="article_save"),
]
