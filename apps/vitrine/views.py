from django.shortcuts import render
from django.views.decorators.cache import cache_page

from .catalogue import PRODUITS


@cache_page(60)
def vitrine(request):
    return render(request, "vitrine/vitrine.html", {"produits": PRODUITS})
