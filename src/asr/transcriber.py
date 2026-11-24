"""
Speech-to-Text (ASR) Transcriber (Module 2).
Supports Hindi (hi-IN), Marathi (mr-IN), and English (en-IN).
Provides confidence estimation, noise handling, and offline test adapters.
"""
import wave
import speech_recognition as sr
from pathlib import Path
from typing import Dict, Any, Optional


class SpeechTranscriber:
    """
    Multilingual ASR Engine supporting Hindi, Marathi, and English.
    """

    LANGUAGE_MAP = {
        "hi": "hi-IN",
        "mr": "mr-IN",
        "en": "en-IN",
        "hi-IN": "hi-IN",
        "mr-IN": "mr-IN",
        "en-IN": "en-IN"
    }

    def __init__(self, energy_threshold: int = 300, pause_threshold: float = 0.8):
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = energy_threshold
        self.recognizer.pause_threshold = pause_threshold
        self.recognizer.dynamic_energy_threshold = True

        # Offline test dictionary for deterministic mocking during network-isolated tests
        self._mock_audio_transcripts: Dict[str, Dict[str, Any]] = {}

    def register_mock_audio(self, file_path: str, transcript: str, language: str, confidence: float = 0.95):
        """Registers a deterministic mock transcript for a specific audio path (for sandboxed unit tests)."""
        abs_path = str(Path(file_path).resolve())
        self._mock_audio_transcripts[abs_path] = {
            "transcript": transcript,
            "language": language,
            "confidence": confidence
        }

    def transcribe_audio_file(
        self,
        audio_path: str,
        language: str = "hi"
    ) -> Dict[str, Any]:
        """
        Transcribes an input 16 kHz WAV audio file.

        Args:
            audio_path: Path to the 16 kHz WAV audio file.
            language: Expected language hint ('hi', 'mr', 'en').

        Returns:
            Dict containing:
                status: 'success', 'unrecognized', or 'error'
                transcript: text string
                language: language code
                confidence: float between 0.0 and 1.0
                error_message: Optional error details
        """
        path = Path(audio_path).resolve()
        if not path.exists():
            return {
                "status": "error",
                "transcript": "",
                "language": language,
                "confidence": 0.0,
                "error_message": f"Audio file not found: {audio_path}"
            }

        # Check if registered as a deterministic mock for sandboxed testing
        resolved_str = str(path)
        base_name = path.name.replace("norm_", "")
        for mock_path, mock_data in self._mock_audio_transcripts.items():
            if mock_path == resolved_str or Path(mock_path).name == base_name or Path(mock_path).stem in path.stem:
                return {
                    "status": "success",
                    "transcript": mock_data["transcript"],
                    "language": mock_data["language"],
                    "confidence": mock_data["confidence"],
                    "is_mock": True
                }

        lang_code = self.LANGUAGE_MAP.get(language.lower(), "hi-IN")

        try:
            with sr.AudioFile(str(path)) as source:
                # Adjust for ambient noise
                self.recognizer.adjust_for_ambient_noise(source, duration=0.2)
                audio_data = self.recognizer.record(source)

            # Attempt cloud transcription via Google Speech recognition API
            response = self.recognizer.recognize_google(
                audio_data,
                language=lang_code,
                show_all=True
            )

            if not response or not isinstance(response, dict) or "alternative" not in response:
                return {
                    "status": "unrecognized",
                    "transcript": "",
                    "language": language,
                    "confidence": 0.0,
                    "error_message": "Audio was unintelligible or silent."
                }

            best_alt = response["alternative"][0]
            transcript = best_alt.get("transcript", "").strip()
            confidence = float(best_alt.get("confidence", 0.88))

            return {
                "status": "success",
                "transcript": transcript,
                "language": language,
                "confidence": round(confidence, 3),
                "is_mock": False
            }

        except sr.UnknownValueError:
            return {
                "status": "unrecognized",
                "transcript": "",
                "language": language,
                "confidence": 0.0,
                "error_message": "Speech recognizer could not understand audio."
            }
        except sr.RequestError as e:
            return {
                "status": "error",
                "transcript": "",
                "language": language,
                "confidence": 0.0,
                "error_message": f"ASR network request failed: {e}"
            }
        except Exception as e:
            return {
                "status": "error",
                "transcript": "",
                "language": language,
                "confidence": 0.0,
                "error_message": f"Unexpected ASR error: {e}"
            }
