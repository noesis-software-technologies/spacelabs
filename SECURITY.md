# Sécurité

SpaceLabs est **local-first** : le serveur tourne sur ta machine et pilote
ton `claude` local. Il n'est pas conçu pour être exposé nu sur Internet.

## Modèle de confidentialité

- **Privé par défaut** : un pane n'est jamais visible dans la vue observateur
  tant que tu ne le rends pas explicitement public *et* que le direct est actif.
- **Redaction côté serveur** : des règles (`RedactionRule`) masquent le contenu
  sensible dans le flux public, appliquées de façon identique aux terminaux et
  aux chats. Les buffers publics sont purgés dès que le direct est coupé ou le
  pane repassé en privé — passer public ne révèle jamais le passé.
- **Bouton panique** : coupe le direct et repasse tous les panes en privé
  instantanément.

> La redaction s'applique par événement/chunk : un secret réparti sur deux
> événements pourrait échapper au filet. Règle d'or : **si c'est confidentiel,
> garde le pane privé.**

## Mode headless autonome

Le chat headless lance `claude -p`. Pour que l'agent exécute des outils sans
invite interactive, Claude Code requiert `--dangerously-skip-permissions`. Il
n'est **pas** activé par défaut : l'ajouter à `COCKPIT_CLAUDE_HEADLESS_ARGS` est
un choix explicite, à réserver aux répertoires que tu maîtrises.

## Commande vocale

Deux moteurs (`COCKPIT_STT_BACKEND`) : la **Web Speech API** (défaut) fait
transcrire l'audio par le navigateur — sous Chrome, l'audio part chez Google.
Pour du contenu sensible, préfère le backend **CrisperWhisper** (serveur) :
l'audio est transcrit **localement**, rien ne sort de ta machine.

## Exposition LAN

Pour la vue « télé » ou un accès depuis un autre appareil du réseau, définis
`COCKPIT_LAN_TOKEN`. Tout le serveur exige alors ce secret partagé (fourni une
fois via `?token=…`, puis en cookie). Ajoute aussi ton IP LAN à `ALLOWED_HOSTS`.
Le cockpit garde par ailleurs son authentification par utilisateur.

## Signaler une faille

Ouvre une issue « security » ou contacte les mainteneurs en privé. Merci de ne
pas divulguer publiquement avant correction.
