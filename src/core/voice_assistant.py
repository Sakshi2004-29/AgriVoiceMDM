"""
Unified Voice-First Multilingual Agricultural Assistant (Phase 4 Orchestrator).
Integrates:
1. Audio format normalization (16 kHz mono WAV) & silence trimming (VAD)
2. Speech-to-Text (ASR) in Hindi, Marathi, and English with confidence estimation
3. Language detection & dialect distinction
4. ASR Confidence Gate & low-confidence repetition prompt
5. Multilingual NLU & Query Router:
   - Live Mandi Market Prices (Agmarknet)
   - Live Weather & Agromet Advisories (Open-Meteo & IMD)
   - Phase 2 Grounded Agricultural RAG (ICAR/KVK verified hybrid search)
   - Out-of-Scope Zero-Guessing Safe Refusal (Kisan Call Centre 1800-180-1551)
6. Natural Text-to-Speech (TTS) voice generation in Hindi & Marathi
7. Privacy-conscious audio management
"""
from pathlib import Path
from typing import Dict, Any, Optional

from src.asr.audio_preprocessor import AudioPreprocessor
from src.asr.transcriber import SpeechTranscriber
from src.asr.language_detector import LanguageDetector
from src.asr.confidence_gate import ASRConfidenceGate
from src.knowledge.rag_service import AgriculturalRAGService
from src.tools.mandi_price_tool import MandiPriceTool
from src.tools.weather_tool import WeatherTool
from src.nlu.query_router import QueryRouter
from src.tts.speech_synthesizer import SpeechSynthesizer
from src.channel.privacy_manager import PrivacyManager


class VoiceAgriculturalAssistant:
    """
    End-to-end voice and text assistant coordinator.
    Processes user queries across Voice Notes, Mandi Prices, Weather, and ICAR/KVK RAG.
    """

    def __init__(self, data_dir: str = "data", asr_confidence_threshold: float = 0.50):
        self.data_dir = Path(data_dir)
        self.preprocessor = AudioPreprocessor()
        self.transcriber = SpeechTranscriber()
        self.language_detector = LanguageDetector()
        self.confidence_gate = ASRConfidenceGate(confidence_threshold=asr_confidence_threshold)

        # Knowledge & Tools
        self.rag_service = AgriculturalRAGService(data_dir=str(self.data_dir))
        self.mandi_tool = MandiPriceTool()
        self.weather_tool = WeatherTool()
        self.query_router = QueryRouter(
            rag_service=self.rag_service,
            mandi_tool=self.mandi_tool,
            weather_tool=self.weather_tool
        )

        # Output & Privacy
        self.synthesizer = SpeechSynthesizer(output_dir=str(self.data_dir / "cache/audio_output"))
        self.privacy_manager = PrivacyManager(temp_dir=str(self.data_dir / "cache/temp_audio"))

    def process_text_query(
        self,
        query: str,
        user_phone_or_id: Optional[str] = None,
        language_hint: Optional[str] = None,
        default_district: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes text query routing through the NLU pipeline.
        """
        user_hash = self.privacy_manager.anonymize_user_id(user_phone_or_id or "")
        detected_lang, lang_conf = self.language_detector.detect_language(
            query,
            default=language_hint or "hi"
        )

        route_result = self.query_router.route_query(
            query=query,
            language=detected_lang,
            default_district=default_district,
            asr_confidence=1.0
        )
        route_result["user_id_hash"] = user_hash
        route_result["detected_language"] = detected_lang
        return route_result

    def process_voice_query(
        self,
        audio_path: str,
        user_phone_or_id: Optional[str] = None,
        language_hint: Optional[str] = None,
        crop_hint: Optional[str] = None,
        region_hint: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes the complete Voice-First pipeline:
        Audio In -> Standardize -> ASR -> Language ID -> Confidence Gate -> NLU Router -> TTS -> Audio Out
        """
        # 1. Privacy anonymization
        user_hash = self.privacy_manager.anonymize_user_id(user_phone_or_id or "")

        # 2. Audio preprocessing & standardization to 16 kHz mono WAV
        norm_output = self.data_dir / f"cache/temp_audio/norm_{Path(audio_path).name}.wav"
        norm_result = self.preprocessor.normalize_audio(audio_path, str(norm_output))
        self.privacy_manager.register_temp_audio(str(norm_output))

        # 3. Speech-to-Text (ASR)
        expected_lang = language_hint or "hi"
        asr_result = self.transcriber.transcribe_audio_file(norm_result["output_path"], language=expected_lang)

        # 4. Language Identification
        detected_lang, lang_conf = self.language_detector.detect_language(
            asr_result.get("transcript", ""),
            default=expected_lang
        )

        # 5. ASR Confidence Gate
        gate_decision = self.confidence_gate.evaluate(asr_result, language=detected_lang)
        if not gate_decision["passed"]:
            repeat_audio = self.synthesizer.synthesize(
                text=gate_decision["spoken_response"],
                language=detected_lang,
                file_prefix="repeat_prompt"
            )
            return {
                "user_id_hash": user_hash,
                "status": "repeat_required",
                "reason": gate_decision["reason"],
                "detected_language": detected_lang,
                "transcript": asr_result.get("transcript", ""),
                "asr_confidence": gate_decision["confidence"],
                "text_response": gate_decision["spoken_response"],
                "audio_response_path": repeat_audio["audio_file"],
                "citations": []
            }

        transcript = asr_result["transcript"]

        # 6. Multilingual NLU Routing (Mandi vs Weather vs RAG vs Refusal)
        route_result = self.query_router.route_query(
            query=transcript,
            language=detected_lang,
            default_district=region_hint,
            asr_confidence=asr_result.get("confidence", 1.0)
        )

        spoken_text = route_result.get("spoken_text") or route_result.get("text_response") or ""

        # 7. Synthesize Spoken Audio Output (TTS)
        tts_result = self.synthesizer.synthesize(
            text=spoken_text,
            language=detected_lang,
            file_prefix=f"voice_reply_{route_result.get('intent', 'general')}_{route_result['status']}"
        )

        return {
            "user_id_hash": user_hash,
            "status": route_result["status"],
            "intent": route_result.get("intent", "general"),
            "entities": route_result.get("entities", {}),
            "detected_language": detected_lang,
            "transcript": transcript,
            "asr_confidence": asr_result.get("confidence", 1.0),
            "text_response": spoken_text,
            "audio_response_path": tts_result["audio_file"],
            "audio_format": tts_result["format"],
            "citations": route_result.get("citations", []),
            "evidence_passages": route_result.get("evidence_passages", []),
            "referrals": route_result.get("referrals", {}),
            "tool_data": route_result.get("tool_data")
        }
