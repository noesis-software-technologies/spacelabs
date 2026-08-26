from django.contrib import admin

from .models import Skill


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ("name", "tag", "is_builtin", "owner")
    list_filter = ("tag", "is_builtin")
