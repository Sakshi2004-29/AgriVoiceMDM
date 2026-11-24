"""
Microphone Audio Recorder (Module 1).
Enables local microphone recording using sounddevice.
Produces standardized 16 kHz 16-bit mono WAV files for the ASR pipeline.
"""
import wave
import numpy as np
from pathlib import Path
from typing import Optional, Dict, Any


class MicrophoneRecorder:
    """
    Records speech directly from a laptop or desktop microphone.
    """

    SAMPLE_RATE = 16000
    CHANNELS = 1

    def __init__(self, default_duration_seconds: int = 5):
        self.default_duration = default_duration_seconds

    @staticmethod
    def is_microphone_available() -> bool:
        """Checks if at least one audio input device is available."""
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            input_devices = [d for d in devices if d.get('max_input_channels', 0) > 0]
            return len(input_devices) > 0
        except Exception:
            return False

    def record_to_file(self, output_path: str, duration_seconds: Optional[int] = None) -> Dict[str, Any]:
        """
        Records audio from the default input device and writes a 16 kHz mono WAV file.

        Args:
            output_path: Target path for the WAV file.
            duration_seconds: Duration of recording in seconds.

        Returns:
            Dict containing audio details.
        """
        duration = duration_seconds or self.default_duration
        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            import sounddevice as sd
        except ImportError:
            raise RuntimeError("sounddevice is not installed. Please install sounddevice.")

        num_samples = int(duration * self.SAMPLE_RATE)
        # Record float32 array
        audio_array = sd.rec(num_samples, samplerate=self.SAMPLE_RATE, channels=self.CHANNELS, dtype='float32')
        sd.wait()  # Block until recording finishes

        # Convert to 16-bit PCM
        pcm_data = (np.clip(audio_array, -1.0, 1.0) * 32767.0).astype(np.int16)

        with wave.open(str(out_path), 'wb') as wf:
            wf.setnchannels(self.CHANNELS)
            wf.setsampwidth(2)
            wf.setframerate(self.SAMPLE_RATE)
            wf.writeframes(pcm_data.tobytes())

        return {
            "status": "success",
            "file_path": str(out_path.resolve()),
            "duration_seconds": duration,
            "sample_rate": self.SAMPLE_RATE,
            "channels": self.CHANNELS
        }
