"""Compatibility imports for the relocated speech generation service."""

from backend.app.services.speech.text_to_speech import (
    save_wave_file,
    text_to_speech,
)

__all__ = ["save_wave_file", "text_to_speech"]
