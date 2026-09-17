"""Brouillons de réponse IA pour l'inbox unifié (via le `claude` local, sans clé API).

Génère une réponse prête à valider, dans la langue du message, ton professionnel
et chaleureux, sans placeholder ni info inventée. Rien n'est envoyé : c'est un
brouillon que l'humain valide.
"""
import subprocess

from django.conf import settings

PROMPT = """Tu rédiges une RÉPONSE à un message reçu dans la boîte de communication
d'une petite structure (tu réponds au nom du destinataire, poliment et efficacement).

Consignes :
- Réponds dans la MÊME LANGUE que le message.
- Ton professionnel, chaleureux, direct ; concis (3 à 8 phrases).
- Réponds concrètement au fond ; si une info manque, propose une suite (appel, RDV)
  au lieu d'inventer. N'invente aucun prix, date ou engagement.
- Pas de placeholder type [NOM] : signe neutrement ou pas du tout.
- Rends UNIQUEMENT le texte de la réponse, sans préambule.

=== Canal : {channel} · Expéditeur : {sender} ===
Sujet : {subject}
Message :
{body}
"""


def suggest_reply(msg, timeout: int = 120) -> str | None:
    claude = getattr(settings, "COCKPIT_CLAUDE_BIN", "claude")
    prompt = PROMPT.format(channel=msg.channel, sender=msg.expediteur or "—",
                           subject=msg.sujet or "(sans objet)",
                           body=(msg.corps or "")[:4000] or "(vide)")
    try:
        proc = subprocess.run([claude, "-p", prompt], capture_output=True,
                              text=True, timeout=timeout)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None
