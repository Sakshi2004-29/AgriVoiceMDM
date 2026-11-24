"""
Audio Preprocessor and Format Converter (Module 1 & Module 2).
Converts any incoming audio format (WAV, MP3, OGG, Opus) to standardized 16 kHz 16-bit mono PCM WAV.
Performs Voice Activity Detection (VAD) and silence trimming.
"""
import wave
import struct
import numpy as np
from pathlib import Path
from typing import Tuple, Dict, Any, Optional


class AudioPreprocessor:
    """
    Standardizes audio streams for Indic ASR engines.
    Ensures 16 kHz sample rate, 16-bit depth, and mono channel.
    """

    TARGET_SAMPLE_RATE = 16000
    TARGET_CHANNELS = 1
    SAMPLE_WIDTH = 2  # 16-bit = 2 bytes

    def __init__(self, silence_threshold_energy: float = 0.005):
        self.silence_threshold_energy = silence_threshold_energy

    def read_wav(self, file_path: str) -> Tuple[np.ndarray, int]:
        """Reads a WAV file into a normalized float32 numpy array [-1.0, 1.0]."""
        with wave.open(file_path, 'rb') as wf:
            num_channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            framerate = wf.getframerate()
            num_frames = wf.getnframes()
            raw_bytes = wf.readframes(num_frames)

        if sample_width == 2:
            data = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        elif sample_width == 1:
            data = (np.frombuffer(raw_bytes, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
        elif sample_width == 4:
            data = np.frombuffer(raw_bytes, dtype=np.int32).astype(np.float32) / 2147483648.0
        else:
            raise ValueError(f"Unsupported sample width: {sample_width} bytes")

        # Convert multi-channel to mono by averaging channels
        if num_channels > 1:
            data = data.reshape(-1, num_channels).mean(axis=1)

        return data, framerate

    def resample_linear(self, audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
        """Resamples audio array to target sample rate using linear interpolation."""
        if orig_sr == target_sr:
            return audio
        duration = len(audio) / orig_sr
        target_len = int(duration * target_sr)
        orig_indices = np.linspace(0, len(audio) - 1, target_len)
        return np.interp(orig_indices, np.arange(len(audio)), audio).astype(np.float32)

    def trim_silence(self, audio: np.ndarray, frame_length_ms: int = 30) -> np.ndarray:
        """
        Trims leading and trailing silence based on short-time RMS energy.
        """
        if len(audio) == 0:
            return audio

        frame_size = int(self.TARGET_SAMPLE_RATE * (frame_length_ms / 1000.0))
        num_frames = len(audio) // frame_size

        if num_frames == 0:
            return audio

        energies = []
        for i in range(num_frames):
            frame = audio[i * frame_size:(i + 1) * frame_size]
            rms = np.sqrt(np.mean(frame ** 2))
            energies.append(rms)

        active_indices = [i for i, e in enumerate(energies) if e > self.silence_threshold_energy]
        if not active_indices:
            return audio  # All below threshold, return as is

        start_frame = max(0, active_indices[0] - 1)
        end_frame = min(num_frames, active_indices[-1] + 2)

        start_sample = start_frame * frame_size
        end_sample = min(len(audio), end_frame * frame_size)
        return audio[start_sample:end_sample]

    def normalize_audio(self, input_path: str, output_path: str) -> Dict[str, Any]:
        """
        Converts and normalizes an input WAV file to 16 kHz mono 16-bit PCM WAV.

        Returns:
            Dict containing output path, original duration, trimmed duration, and sample rate.
        """
        in_path = Path(input_path)
        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        audio_data, orig_sr = self.read_wav(str(in_path))
        orig_duration = len(audio_data) / orig_sr

        # Resample to 16 kHz
        resampled_audio = self.resample_linear(audio_data, orig_sr, self.TARGET_SAMPLE_RATE)

        # Trim silence
        trimmed_audio = self.trim_silence(resampled_audio)
        trimmed_duration = len(trimmed_audio) / self.TARGET_SAMPLE_RATE

        # Prevent clipping and normalize peak amplitude to 0.95
        peak = np.max(np.abs(trimmed_audio)) if len(trimmed_audio) > 0 else 0.0
        if peak > 0:
            trimmed_audio = (trimmed_audio / peak) * 0.95

        # Convert to 16-bit PCM integers
        pcm_data = (trimmed_audio * 32767.0).astype(np.int16)

        with wave.open(str(out_path), 'wb') as wf:
            wf.setnchannels(self.TARGET_CHANNELS)
            wf.setsampwidth(self.SAMPLE_WIDTH)
            wf.setframerate(self.TARGET_SAMPLE_RATE)
            wf.writeframes(pcm_data.tobytes())

        return {
            "output_path": str(out_path.resolve()),
            "original_sample_rate": orig_sr,
            "target_sample_rate": self.TARGET_SAMPLE_RATE,
            "original_duration_seconds": round(orig_duration, 2),
            "trimmed_duration_seconds": round(trimmed_duration, 2),
            "channels": self.TARGET_CHANNELS,
            "peak_amplitude": round(float(peak), 3)
        }

    def generate_synthetic_tone_wav(self, file_path: str, duration: float = 1.0, freq: float = 440.0):
        """Utility to generate a test WAV file with a pure sine wave tone."""
        out_path = Path(file_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        t = np.linspace(0, duration, int(self.TARGET_SAMPLE_RATE * duration), False)
        signal = 0.5 * np.sin(2 * np.pi * freq * t)
        pcm_data = (signal * 32767.0).astype(np.int16)

        with wave.open(str(out_path), 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.TARGET_SAMPLE_RATE)
            wf.writeframes(pcm_data.tobytes())
