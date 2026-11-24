"""
Privacy and Audio Lifecycle Manager (Module 12).
Implements privacy-conscious handling of farmer voice data:
- SHA-256 anonymization of phone numbers and user identifiers
- Tracking and secure cleanup of temporary audio files
- Retention policy enforcement
"""
import hashlib
from pathlib import Path
from typing import Set, List, Optional


class PrivacyManager:
    """
    Protects user privacy and enforces audio retention policies.
    """

    def __init__(self, temp_dir: str = "data/cache/temp_audio"):
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.tracked_files: Set[Path] = set()

    @staticmethod
    def anonymize_user_id(phone_number_or_id: str) -> str:
        """
        Hashes sensitive farmer identifiers using SHA-256.
        Prevents storing plain-text phone numbers in application logs.
        """
        if not phone_number_or_id:
            return "ANONYMOUS_USER"
        return "USER_" + hashlib.sha256(phone_number_or_id.strip().encode("utf-8")).hexdigest()[:16]

    def register_temp_audio(self, file_path: str) -> str:
        """Tracks an audio file for future privacy cleanup."""
        p = Path(file_path).resolve()
        self.tracked_files.add(p)
        return str(p)

    def cleanup_file(self, file_path: str) -> bool:
        """Securely deletes a single temporary audio file."""
        p = Path(file_path).resolve()
        try:
            if p.exists():
                p.unlink()
            self.tracked_files.discard(p)
            return True
        except Exception:
            return False

    def cleanup_all_session_audio(self) -> int:
        """Deletes all tracked temporary audio recordings created during the session."""
        cleaned_count = 0
        for p in list(self.tracked_files):
            try:
                if p.exists():
                    p.unlink()
                cleaned_count += 1
            except Exception:
                pass
        self.tracked_files.clear()
        return cleaned_count
