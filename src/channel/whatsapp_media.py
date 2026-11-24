import secrets
import shutil
import tempfile
import time
from pathlib import Path
from threading import Lock

MEDIA_DIR = Path(tempfile.gettempdir()) / "agrivoice_whatsapp_media"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

EXPIRY_SECONDS = 3600
_lock = Lock()
_expiries = {}


def register_audio(audio_path):
    """Create a temporary, unpredictable URL token for an MP3 reply."""
    source = Path(audio_path)

    if not source.is_file() or source.stat().st_size == 0:
        raise ValueError("Generated audio file is missing or empty")

    if source.suffix.lower() != ".mp3":
        raise ValueError("Only MP3 audio replies are supported")

    with _lock:
        now = time.time()

        for token, expiry in list(_expiries.items()):
            if expiry <= now:
                (MEDIA_DIR / (token + ".mp3")).unlink(missing_ok=True)
                del _expiries[token]

        token = secrets.token_urlsafe(24)
        destination = MEDIA_DIR / (token + ".mp3")
        shutil.copyfile(source, destination)
        _expiries[token] = now + EXPIRY_SECONDS

    return token


def get_audio(token):
    """Return the temporary MP3 path only for valid, unexpired tokens."""
    if not token or not all(c.isalnum() or c in "-_" for c in token):
        return None

    with _lock:
        expiry = _expiries.get(token)

        if expiry is None:
            return None

        if expiry <= time.time():
            (MEDIA_DIR / (token + ".mp3")).unlink(missing_ok=True)
            del _expiries[token]
            return None

        path = MEDIA_DIR / (token + ".mp3")
        return path if path.is_file() and path.stat().st_size > 0 else None
