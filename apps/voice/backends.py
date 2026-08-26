"""Reconnaissance vocale serveur — backends pluggables (Sprint 7).

Deux mondes selon COCKPIT_STT_BACKEND :
- "webspeech" : reconnaissance CÔTÉ NAVIGATEUR (Web Speech API, défaut hérité
  du Sprint 6). Aucun transcripteur serveur → get_transcriber() renvoie None.
- "crisperwhisper" : reconnaissance CÔTÉ SERVEUR via faster-whisper + le modèle
  CrisperWhisper (verbatim, fillers). Le navigateur ne fait que capturer
  l'audio et l'envoyer.
- "fake" : transcripteur déterministe (tests / environnements sans les poids du
  modèle). Jamais en production.

Le vrai backend est importé PARESSEUSEMENT : la suite de tests n'a besoin ni de
faster-whisper ni des poids du modèle.
"""
from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path

from django.conf import settings

logger = logging.getLogger("spacelabs.voice")


class TranscriptionError(RuntimeError):
    pass


class BaseTranscriber:
    def transcribe(self, audio: bytes, mime: str = "") -> str:
        raise NotImplementedError


class FakeTranscriber(BaseTranscriber):
    """Renvoie un transcript fixe (paramétrable). Pour tests et sandbox : prouve
    tout le chemin capture→upload→insertion sans les 1,5 Go de poids."""

    def transcribe(self, audio: bytes, mime: str = "") -> str:
        if not audio:
            raise TranscriptionError("audio vide")
        return settings.COCKPIT_STT_FAKE_TRANSCRIPT


class CrisperWhisperBackend(BaseTranscriber):
    """faster-whisper + CrisperWhisper (CTranslate2). Le modèle est chargé à la
    première transcription (pas à la construction) — évite tout téléchargement
    tant qu'on ne transcrit pas réellement."""

    _model = None

    def _load(self):
        if CrisperWhisperBackend._model is not None:
            return CrisperWhisperBackend._model
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:  # pragma: no cover - dépend de l'install prod
            raise TranscriptionError(
                "faster-whisper non installé (pip install faster-whisper)"
            ) from exc
        device = settings.COCKPIT_STT_DEVICE
        compute = settings.COCKPIT_STT_COMPUTE_TYPE
        logger.info("chargement CrisperWhisper %s (device=%s, %s)",
                    settings.COCKPIT_STT_MODEL, device, compute)
        CrisperWhisperBackend._model = WhisperModel(
            settings.COCKPIT_STT_MODEL, device=device, compute_type=compute
        )
        return CrisperWhisperBackend._model

    @staticmethod
    def _to_wav(audio: bytes) -> str:
        """Décode l'audio du navigateur (webm/opus…) en WAV 16 kHz mono via
        ffmpeg — format attendu par le modèle."""
        src = tempfile.NamedTemporaryFile(suffix=".bin", delete=False)
        src.write(audio)
        src.close()
        dst = src.name + ".wav"
        try:
            subprocess.run(
                ["ffmpeg", "-nostdin", "-y", "-i", src.name,
                 "-ar", "16000", "-ac", "1", "-f", "wav", dst],
                capture_output=True, check=True, timeout=60,
            )
        except (subprocess.SubprocessError, OSError) as exc:
            raise TranscriptionError(f"décodage audio échoué : {exc}") from exc
        finally:
            Path(src.name).unlink(missing_ok=True)
        return dst

    def transcribe(self, audio: bytes, mime: str = "") -> str:
        if not audio:
            raise TranscriptionError("audio vide")
        model = self._load()
        wav = self._to_wav(audio)
        try:
            segments, _info = model.transcribe(
                wav, language=settings.COCKPIT_STT_LANGUAGE or None,
                word_timestamps=False,
            )
            return "".join(seg.text for seg in segments).strip()
        finally:
            Path(wav).unlink(missing_ok=True)


_BACKENDS = {
    "fake": FakeTranscriber,
    "crisperwhisper": CrisperWhisperBackend,
}


def get_transcriber() -> BaseTranscriber | None:
    """Instancie le backend serveur, ou None si la reconnaissance est côté
    client (webspeech)."""
    name = settings.COCKPIT_STT_BACKEND
    cls = _BACKENDS.get(name)
    return cls() if cls else None
