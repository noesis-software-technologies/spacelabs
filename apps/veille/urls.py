from django.urls import path

from . import views

app_name = "veille"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("articles/", views.articles, name="articles"),
    path("articles/<int:pk>/", views.article_detail, name="article_detail"),
    path("articles/<int:pk>/edit/", views.article_edit, name="article_edit"),
    path("articles/<int:pk>/save/", views.article_save, name="article_save"),
    path("articles/<int:pk>/quick/", views.article_quick, name="article_quick"),
    path("articles/<int:pk>/publish/", views.article_publish, name="article_publish"),
    path("articles/<int:pk>/publish-related/", views.article_publish_related, name="article_publish_related"),
    path("mcp/status-refresh/", views.mcp_status_refresh, name="mcp_status_refresh"),
]
