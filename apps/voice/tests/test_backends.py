"""Backends de transcription : factory + transcripteur factice."""
import pytest

from apps.voice.backends import (
    CrisperWhisperBackend,
    FakeTranscriber,
    TranscriptionError,
    get_transcriber,
)


def test_webspeech_has_no_server_transcriber(settings):
    settings.COCKPIT_STT_BACKEND = "webspeech"
    assert get_transcriber() is None


def test_fake_backend_selected(settings):
    settings.COCKPIT_STT_BACKEND = "fake"
    assert isinstance(get_transcriber(), FakeTranscriber)


def test_crisperwhisper_backend_selected_without_loading_model(settings):
    settings.COCKPIT_STT_BACKEND = "crisperwhisper"
    t = get_transcriber()
    assert isinstance(t, CrisperWhisperBackend)
    # La construction ne charge PAS le modèle (aucun téléchargement).
    assert CrisperWhisperBackend._model is None


def test_fake_transcriber_returns_configured_text(settings):
    settings.COCKPIT_STT_FAKE_TRANSCRIPT = "bonjour ceci est un test"
    assert FakeTranscriber().transcribe(b"audio-bytes") == "bonjour ceci est un test"


def test_fake_transcriber_rejects_empty_audio():
    with pytest.raises(TranscriptionError):
        FakeTranscriber().transcribe(b"")
