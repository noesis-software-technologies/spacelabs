"""Tri automatique des messages entrants : priorité, besoin de réponse, catégorie."""
import re

URGENT = ["urgent", "asap", "au plus vite", "relance", "rappel", "deadline",
          "facture", "paiement", "impayé", "échéance", "aujourd'hui", "avant ce soir",
          "réponse attendue", "merci de revenir", "dernier rappel", "important"]

# expéditeurs automatiques → basse priorité, pas de réponse
AUTO = ["no-reply", "noreply", "ne-pas-repondre", "nepasrepondre", "notification",
        "notifications", "digest", "mailer", "newsletter", "no_reply", "bounce",
        "postmaster", "automated", "do-not-reply"]


def is_auto(sender: str) -> bool:
    s = (sender or "").lower()
    return any(a in s for a in AUTO)


def triage(sender: str, subject: str, body: str):
    text = f"{subject} {body}".lower()
    auto = is_auto(sender)
    # priorité
    if any(k in text for k in URGENT) and not auto:
        priorite = "haute"
    elif auto:
        priorite = "basse"
    else:
        priorite = "normale"
    # besoin de réponse : humain + question / demande directe
    needs_reply = (not auto) and (
        "?" in text
        or any(w in text for w in ["peux-tu", "pouvez-vous", "pourriez", "merci de",
                                   "j'attends", "confirme", "confirmez", "dispo", "rappelle",
                                   "rappelez", "devis", "rendez-vous", "rdv"])
    )
    # catégorie légère
    if auto or "newsletter" in text:
        categorie = "notification"
    elif any(w in text for w in ["facture", "devis", "paiement", "contrat", "comptable"]):
        categorie = "admin/facturation"
    elif any(w in text for w in ["communiqué", "presse", "dossier de presse", "cp |", "drp"]):
        categorie = "rp/presse"
    elif "?" in text:
        categorie = "demande"
    else:
        categorie = "à trier"
    return priorite, needs_reply, categorie
