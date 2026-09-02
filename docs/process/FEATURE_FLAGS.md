# Feature flags — déployer sans releaser

## Pourquoi un registre

`config/feature_flags.yml` est la **source de vérité** : un flag y est déclaré avant d'être utilisé (Règle 3),
son état y change par PR (paliers), et il en sort quand le code est nettoyé. La CI (`flag-check`) refuse un
flag utilisé dans le code mais absent du registre ; le workflow `flag-hygiene` ouvre une issue quand un flag
dépasse son échéance.

## Nommage

`<slug_de_l_epic>_v<n>` en snake_case : `billing_dashboard_v1`. Le même nom sert partout :
- Python : `is_enabled("billing_dashboard_v1", request.user)`
- environnement : `FLAG_BILLING_DASHBOARD_V1=off`
- template Django : `{% if flags.billing_dashboard_v1 %}` (le tiret est interdit dans un nom de variable
  de template — d'où le snake_case)

## Schéma d'une entrée

```yaml
flags:
  - name: billing_dashboard_v1
    epic: '#42'
    pod: growth
    owner: '@noesis-software-technologies/pod-growth'
    state: 'off'          # off | rollout | on | permanent  (toujours quoté : YAML 1.1 lit off/on comme des booléens)
    percentage: 0         # 0..100, utilisé en état rollout
    allow_users: []       # usernames toujours ON en état rollout (équipe, testeurs, client pilote)
    created: '2026-08-29'
    cleanup_by: '2026-11-27'   # created + FLAG_MAX_AGE_DAYS ; repoussable avec une raison dans la PR
    released_at: '2026-10-02'  # posé par `set --state on` (palier 100) ; retiré par `off` ; déclenche la revue post-launch J+N
    description: ''
```

| État | Comportement | Qui décide |
|---|---|---|
| `off` | fermé pour tous (défaut à la création) | tech lead (gate 1) |
| `rollout` | liste blanche `allow_users` puis `percentage` % des utilisateurs **connectés**, bucket déterministe `sha256(nom:user.pk)` — un utilisateur garde toujours la même réponse | PM (paliers) |
| `on` | ouvert pour tous, y compris anonymes | PM (palier 100) |
| `permanent` | ouvert pour tous et **exclu de l'hygiène** : le verdict est « généraliser », la PR de nettoyage est en cours | PM (clôture) |

## Commandes

```bash
scripts/ci/flags_registry.py add --name billing_dashboard_v1 --epic '#42' --pod growth --owner @org/pod-growth   # fait par 10-new-epic.sh
scripts/ci/flags_registry.py set --name billing_dashboard_v1 --state rollout --percentage 10                        # fait par 35-rollout.sh
scripts/ci/flags_registry.py set --name billing_dashboard_v1 --state rollout --allow-user alice
scripts/ci/flags_registry.py check --code-root .            # ce que fait la CI (--strict : périmé = échec)
scripts/ci/flags_registry.py stale                          # flags en retard de nettoyage
scripts/ci/flags_registry.py review --after 7               # lancements dont la revue post-launch est due (workflow flag-hygiene)
```

## Dans le code Django (`apps/core/flags.py`, drop-in)

```python
# settings.py
TEMPLATES[0]["OPTIONS"]["context_processors"].append("apps.core.flags.feature_flags")
# (pyyaml doit être dans requirements.txt)

# views.py
from apps.core.flags import is_enabled, flag_required

FLAG = "billing_dashboard_v1"

@login_required
@flag_required(FLAG)                      # 404 si fermé : la fonctionnalité « n'existe pas »
def billing_dashboard(request): ...

def sidebar(request):
    show_billing = is_enabled(FLAG, request.user)
```
```django
{% if flags.billing_dashboard_v1 %}<a href="{% url 'billing:dashboard' %}">Facturation</a>{% endif %}
```

Règles d'écriture :
- **un seul point de bascule** par surface (la vue, ou le lien qui y mène) — pas de `if flag` disséminés ;
- une **migration** ne se met pas derrière un flag : elle doit être additive et compatible avec les deux
  chemins (colonne nullable, table nouvelle), le flag ne gouverne que la lecture/écriture ;
- tester les **deux chemins** tant que le flag existe (`monkeypatch.setenv("FLAG_…", "on")`) ;
- un flag inconnu lève `KeyError` en Python (bug de déclaration = échec immédiat) et vaut `False` dans un
  template (le rendu ne casse pas ; la CI le signale).

## Kill switch sans PR

La variable d'environnement gagne sur le registre : `FLAG_BILLING_DASHBOARD_V1=off` dans l'environnement du
service (systemd `Environment=`, `.env`, variables du PaaS) + redémarrage → fermé en quelques secondes.
Ouvrir ensuite la PR de palier `off` pour que le registre reflète la réalité et retirer la variable.

## Nettoyage (clôture de l'épic)

Un flag qui survit à sa release est du code mort et deux chemins à maintenir. Le workflow `flag-hygiene`
ouvre `[flag] Nettoyer <nom>` chaque lundi de retard. La PR de nettoyage : supprimer les conditions, garder
un seul chemin, retirer l'entrée du registre, adapter les tests. `flag-check` vérifie alors que plus rien ne
référence le flag.

## Chemin d'évolution

Quand la liste blanche par username et le pourcentage global ne suffisent plus (ciblage par tenant/plan,
interface d'admin, audit des bascules), **django-waffle** offre `is_enabled(name, user)` avec la même
signature : remplacer le corps de `apps/core/flags.py`, conserver le registre YAML comme source de vérité
déclarative (créer les `Flag` waffle par migration de données depuis le registre).
