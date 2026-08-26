"""Endpoint de transcription serveur (Sprint 7).

Le navigateur capture l'audio (MediaRecorder) et le POST ici ; on renvoie le
texte verbatim. Utilisé quand COCKPIT_STT_BACKEND est côté serveur
(crisperwhisper / fake). En mode webspeech, la reconnaissance reste dans le
navigateur et cet endpoint n'est pas sollicité.
"""
import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .backends import TranscriptionError, get_transcriber

logger = logging.getLogger("spacelabs.voice")

MAX_AUDIO_BYTES = 25 * 1024 * 1024  # 25 Mo — largement de quoi dicter une tâche


@login_required
@require_POST
def transcribe(request):
    transcriber = get_transcriber()
    if transcriber is None:
        return JsonResponse(
            {"error": "reconnaissance côté navigateur (webspeech)"}, status=400
        )
    blob = request.FILES.get("audio")
    if blob is None:
        return JsonResponse({"error": "champ 'audio' manquant"}, status=400)
    if blob.size > MAX_AUDIO_BYTES:
        return JsonResponse({"error": "audio trop volumineux"}, status=413)
    try:
        text = transcriber.transcribe(blob.read(), mime=blob.content_type or "")
    except TranscriptionError as exc:
        logger.warning("transcription échouée : %s", exc)
        return JsonResponse({"error": str(exc)}, status=422)
    except Exception:  # noqa: BLE001 — ne pas exposer les détails internes
        logger.exception("erreur de transcription inattendue")
        return JsonResponse({"error": "transcription indisponible"}, status=500)
    return JsonResponse({"text": text})


@login_required
@require_POST
def command(request):
    """Reçoit un transcript, le route, applique, et renvoie ce qui a été fait.

    Le texte peut venir de Web Speech (navigateur) ou du STT serveur : Bridge
    ne fait pas la différence, il ne reçoit que du texte.
    """
    from django.shortcuts import get_object_or_404

    from apps.voice.actions import execute
    from apps.voice.intents import parse
    from apps.workspaces.models import Workspace

    said = (request.POST.get("text") or "").strip()
    slug = request.POST.get("workspace") or ""
    workspace = get_object_or_404(Workspace.objects.for_owner(request.user), slug=slug)
    intent = parse(said)
    reply = execute(intent, workspace)
    logger.info("voice: %r -> %s", said[:60], intent.kind)
    return JsonResponse({"said": said, "intent": intent.kind, "reply": reply,
                         "understood": intent.understood})
