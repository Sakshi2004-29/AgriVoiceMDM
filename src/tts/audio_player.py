"""
Audio Playback Utility (Module 11).
Plays synthesized responses using pygame.mixer.
Safe for headless/automated test environments without hardware speakers.
"""
import os
from pathlib import Path
from typing import Optional


class AudioPlayer:
    """
    Handles local audio playback of synthesized voice notes.
    """

    def __init__(self):
        self._initialized = False

    def _init_mixer(self) -> bool:
        if self._initialized:
            return True
        try:
            import pygame
            # Set dummy audio driver if no sound device in CI / headless environments
            if os.environ.get("SDL_AUDIODRIVER") == "dummy":
                pygame.mixer.init()
            else:
                pygame.mixer.init()
            self._initialized = True
            return True
        except Exception:
            return False

    def play(self, audio_file_path: str, block: bool = False) -> bool:
        """
        Plays an audio file.

        Args:
            audio_file_path: Path to MP3 or WAV audio.
            block: Whether to wait until playback completes.

        Returns:
            bool: True if played successfully, False otherwise.
        """
        path = Path(audio_file_path)
        if not path.exists():
            return False

        if not self._init_mixer():
            return False

        try:
            import pygame
            pygame.mixer.music.load(str(path))
            pygame.mixer.music.play()
            if block:
                while pygame.mixer.music.get_busy():
                    pygame.time.Clock().tick(10)
            return True
        except Exception:
            return False

    def stop(self):
        """Stops active playback."""
        if self._initialized:
            try:
                import pygame
                pygame.mixer.music.stop()
            except Exception:
                pass
