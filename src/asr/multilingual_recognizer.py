from src.asr.transcriber import SpeechTranscriber
from src.asr.language_detector import LanguageDetector


def recognize_candidates(audio_path):
    transcriber = SpeechTranscriber()
    candidates = []

    for language in ("mr", "hi", "en"):
        result = transcriber.transcribe_audio_file(
            audio_path,
            language=language
        )

        if result.get("status") != "success":
            continue

        transcript = result.get("transcript", "").strip()

        if not transcript:
            continue

        detected, language_confidence = LanguageDetector.detect_language(
            transcript,
            default=language
        )

        candidates.append({
            "recognition_language": language,
            "detected_language": detected,
            "transcript": transcript,
            "asr_confidence": result.get("confidence", 0.0),
            "language_confidence": language_confidence
        })

    return candidates
