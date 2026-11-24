"""
Speech Recognition Confidence Gate (Module 2 & Module 10).
Evaluates ASR confidence scores and triggers clear, localized requests for repetition when audio is unclear.
"""
from typing import Dict, Any


class ASRConfidenceGate:
    """
    Evaluates whether transcription confidence meets the quality threshold.
    """

    DEFAULT_THRESHOLD = 0.50

    REPEAT_MESSAGES = {
        "hi": "आपकी आवाज स्पष्ट सुनाई नहीं दी। कृपया शांत जगह से अपना प्रश्न दोबारा बोलें।",
        "mr": "आपला आवाज स्पष्ट ऐकू आला नाही. कृपया शांत ठिकाणाहून आपला प्रश्न पुन्हा सांगा.",
        "en": "Your voice was not clear. Please repeat your question from a quieter location."
    }

    def __init__(self, confidence_threshold: float = DEFAULT_THRESHOLD):
        self.threshold = confidence_threshold

    def evaluate(self, asr_result: Dict[str, Any], language: str = "hi") -> Dict[str, Any]:
        """
        Evaluates transcription quality.

        Returns:
            Dict containing:
                passed: bool
                reason: str ('CONFIDENCE_OK', 'LOW_CONFIDENCE', 'UNRECOGNIZED_SPEECH')
                spoken_response: Optional spoken message to play back to the farmer
        """
        status = asr_result.get("status", "error")
        confidence = asr_result.get("confidence", 0.0)
        lang = language if language in self.REPEAT_MESSAGES else "hi"

        if status == "unrecognized":
            return {
                "passed": False,
                "reason": "UNRECOGNIZED_SPEECH",
                "spoken_response": self.REPEAT_MESSAGES[lang],
                "confidence": confidence
            }

        if confidence < self.threshold:
            return {
                "passed": False,
                "reason": "LOW_CONFIDENCE",
                "spoken_response": self.REPEAT_MESSAGES[lang],
                "confidence": confidence
            }

        return {
            "passed": True,
            "reason": "CONFIDENCE_OK",
            "spoken_response": None,
            "confidence": confidence
        }
