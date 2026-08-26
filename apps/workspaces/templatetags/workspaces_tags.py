from django import template

from apps.workspaces.models import Workspace

register = template.Library()


@register.inclusion_tag("workspaces/partials/_sidebar_list.html", takes_context=True)
def workspaces_sidebar(context):
    request = context["request"]
    workspaces = []
    if request.user.is_authenticated:
        workspaces = Workspace.objects.for_owner(request.user).with_counts()
    return {"workspaces": workspaces, "current_slug": context.get("workspace") and context["workspace"].slug}
