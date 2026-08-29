"""Ingère une session OpenClaw (JSONL transcript) dans l'EventLog SpaceLabs.

Usage:
    python manage.py ingest_telegram_session --jsonl <path> --pane <pk> [--clear]
"""
import json
import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.chat.models import EventLog


# Retire l'enveloppe metadata OpenClaw du texte utilisateur
_META_HEADER = re.compile(
    r"Conversation info \(untrusted metadata\):\s*```json\s*\{.*?\}\s*```\s*",
    re.DOTALL,
)


def _strip_meta(text: str) -> str:
    return _META_HEADER.sub("", text).strip()


class Command(BaseCommand):
    help = "Importe les tours d'une session OpenClaw (jsonl) dans l'EventLog d'un pane."

    def add_arguments(self, parser):
        parser.add_argument("--jsonl", required=True, help="Chemin vers le transcript .jsonl")
        parser.add_argument("--pane", type=int, required=True, help="PK du HeadlessPane cible")
        parser.add_argument("--clear", action="store_true", help="Supprimer les events existants avant import")

    def handle(self, *args, **options):
        from apps.workspaces.models import Pane

        jsonl_path = Path(options["jsonl"])
        if not jsonl_path.exists():
            raise CommandError(f"Fichier introuvable : {jsonl_path}")

        try:
            pane = Pane.objects.get(pk=options["pane"])
        except Pane.DoesNotExist:
            raise CommandError(f"Pane pk={options['pane']} introuvable.")

        if options["clear"]:
            deleted, _ = EventLog.objects.filter(pane=pane).delete()
            self.stdout.write(self.style.WARNING(f"  {deleted} events supprimés."))

        # Parse le transcript : on ne garde que les turns user (texte) et
        # assistant (stop_reason=end_turn, bloc text non vide).
        turns = []
        seen_msg_ids = set()

        with jsonl_path.open(encoding="utf-8") as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    obj = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                kind = obj.get("type")

                if kind == "user":
                    msg = obj.get("message", {})
                    content = msg.get("content", "")
                    if isinstance(content, str):
                        text = _strip_meta(content)
                    elif isinstance(content, list):
                        text = _strip_meta(
                            " ".join(
                                b.get("text", "") for b in content if b.get("type") == "text"
                            )
                        )
                    else:
                        continue
                    if text:
                        turns.append(("user", text, obj.get("timestamp", "")))

                elif kind == "assistant":
                    msg = obj.get("message", {})
                    msg_id = msg.get("id", "")
                    if msg_id in seen_msg_ids:
                        continue
                    if msg.get("stop_reason") != "end_turn":
                        continue
                    text_blocks = [
                        b["text"]
                        for b in msg.get("content", [])
                        if b.get("type") == "text" and b.get("text", "").strip()
                    ]
                    if not text_blocks:
                        continue
                    text = "\n\n".join(text_blocks)
                    seen_msg_ids.add(msg_id)
                    turns.append(("assistant", text, obj.get("timestamp", "")))

        if not turns:
            self.stderr.write("Aucun turn extractible du transcript.")
            return

        # Numéro de séquence de départ
        last_seq = EventLog.objects.filter(pane=pane).order_by("-seq").values_list("seq", flat=True).first() or 0

        created = 0
        for i, (role, text, ts) in enumerate(turns):
            seq = last_seq + i + 1
            if role == "user":
                event_type = "user"
                normalized = {"kind": "user", "text": text}
            else:
                event_type = "assistant"
                normalized = {
                    "kind": "assistant",
                    "blocks": [{"type": "text", "text": text}],
                }
            EventLog.objects.get_or_create(
                pane=pane,
                seq=seq,
                defaults={
                    "origin": "telegram",
                    "event_type": event_type,
                    "payload": {"role": role, "text": text[:2000]},
                    "normalized": normalized,
                },
            )
            created += 1

        self.stdout.write(self.style.SUCCESS(
            f"✅ {created} turns importés → pane pk={pane.pk} ({pane.title})"
        ))
