from pathlib import Path
import subprocess

def convert_to_wav(input_path, output_path):
    """Convert WhatsApp audio to 16 kHz mono WAV using FFmpeg."""
    input_path = Path(input_path)
    output_path = Path(output_path)

    if not input_path.is_file():
        raise FileNotFoundError(input_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    command = [
        "ffmpeg",
        "-nostdin",
        "-hide_banner",
        "-loglevel", "error",
        "-y",
        "-i", str(input_path),
        "-vn",
        "-ac", "1",
        "-ar", "16000",
        "-c:a", "pcm_s16le",
        str(output_path)
    ]

    subprocess.run(command, check=True, timeout=60)

    return str(output_path)
