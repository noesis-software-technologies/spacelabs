"""Helper canonique « une URL, deux représentations » (Blueprint §6.2).

Le partial EST la source unique ; la page complète n'est qu'une enveloppe
qui l'inclut. `django-htmx` pose déjà `Vary: HX-Request`.
"""
from django.shortcuts import render
from django.utils.cache import patch_vary_headers


def render_htmx(request, page_template, partial_template, context=None):
    template = partial_template if getattr(request, "htmx", False) else page_template
    response = render(request, template, context or {})
    # django-htmx parse la requête mais ne pose PAS Vary sur la réponse :
    # on le fait ici, au seul endroit où la double représentation existe,
    # pour que les caches ne servent jamais un fragment à la place d'une page.
    patch_vary_headers(response, ["HX-Request"])
    return response
