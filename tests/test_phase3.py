"""
Automated Unit and Integration Test Suite for Phase 3:
Speech-to-Text (ASR), Language Detection, Confidence Gating,
Text-to-Speech (TTS), Privacy Handling, and End-to-End Voice RAG.
Uses Python's standard `unittest` framework.
"""
import unittest
import tempfile
import shutil
from pathlib import Path

from src.asr.audio_preprocessor import AudioPreprocessor
from src.asr.transcriber import SpeechTranscriber
from src.asr.language_detector import LanguageDetector
from src.asr.confidence_gate import ASRConfidenceGate
from src.tts.speech_synthesizer import SpeechSynthesizer
from src.channel.privacy_manager import PrivacyManager
from src.knowledge.models import DocumentMetadata
from src.core.voice_assistant import VoiceAgriculturalAssistant


class TestAudioPreprocessing(unittest.TestCase):
    """Tests audio format conversion, resampling to 16 kHz mono, and VAD silence trimming."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.preprocessor = AudioPreprocessor()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_audio_normalization_and_vad(self):
        raw_wav = Path(self.tmp_dir) / "test_raw.wav"
        norm_wav = Path(self.tmp_dir) / "test_normalized.wav"

        # Generate 1.5s synthetic tone
        self.preprocessor.generate_synthetic_tone_wav(str(raw_wav), duration=1.5, freq=440.0)
        self.assertTrue(raw_wav.exists())

        # Normalize audio to 16 kHz mono
        res = self.preprocessor.normalize_audio(str(raw_wav), str(norm_wav))

        self.assertTrue(norm_wav.exists())
        self.assertEqual(res["target_sample_rate"], 16000)
        self.assertEqual(res["channels"], 1)
        self.assertGreater(res["trimmed_duration_seconds"], 0.0)
        self.assertLessEqual(res["peak_amplitude"], 1.0)


class TestLanguageDetection(unittest.TestCase):
    """Tests Hindi vs. Marathi vs. English detection."""

    def test_marathi_detection(self):
        # Text containing distinctive Marathi markers and characters
        mr_text = "गहू पिकावरील पिवळा तांबेरा रोगाची लक्षणे काय आहेत?"
        lang, conf = LanguageDetector.detect_language(mr_text)
        self.assertEqual(lang, "mr")
        self.assertGreaterEqual(conf, 0.70)

    def test_hindi_detection(self):
        hi_text = "कपास में गुलाबी सुंडी का नियंत्रण कैसे करें?"
        lang, conf = LanguageDetector.detect_language(hi_text)
        self.assertEqual(lang, "hi")
        self.assertGreaterEqual(conf, 0.70)

    def test_english_detection(self):
        en_text = "How many pheromone traps are recommended per hectare for cotton?"
        lang, conf = LanguageDetector.detect_language(en_text)
        self.assertEqual(lang, "en")
        self.assertGreaterEqual(conf, 0.80)


class TestASRConfidenceGate(unittest.TestCase):
    """Tests confidence evaluation and repetition requests."""

    def setUp(self):
        self.gate = ASRConfidenceGate(confidence_threshold=0.50)

    def test_high_confidence_passes(self):
        res = {"status": "success", "confidence": 0.88, "transcript": "कपास"}
        decision = self.gate.evaluate(res, language="hi")
        self.assertTrue(decision["passed"])
        self.assertIsNone(decision["spoken_response"])

    def test_low_confidence_triggers_repeat(self):
        res = {"status": "success", "confidence": 0.32, "transcript": "..."}
        decision_hi = self.gate.evaluate(res, language="hi")
        self.assertFalse(decision_hi["passed"])
        self.assertIn("दोबारा बोलें", decision_hi["spoken_response"])

        decision_mr = self.gate.evaluate(res, language="mr")
        self.assertFalse(decision_mr["passed"])
        self.assertIn("पुन्हा सांगा", decision_mr["spoken_response"])


class TestTextToSpeech(unittest.TestCase):
    """Tests speech synthesis in Hindi and Marathi."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.synthesizer = SpeechSynthesizer(output_dir=self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_hindi_speech_synthesis(self):
        hi_text = "किसान कॉल सेंटर का टोल-फ्री नंबर 1800-180-1551 है।"
        res = self.synthesizer.synthesize(hi_text, language="hi", file_prefix="test_hi")

        self.assertEqual(res["status"], "success")
        self.assertEqual(res["language"], "hi")
        audio_path = Path(res["audio_file"])
        self.assertTrue(audio_path.exists())
        self.assertGreater(res["file_size_bytes"], 0)

    def test_marathi_speech_synthesis(self):
        mr_text = "किसान कॉल सेंटरचा टोल-फ्री क्रमांक 1800-180-1551 आहे."
        res = self.synthesizer.synthesize(mr_text, language="mr", file_prefix="test_mr")

        self.assertEqual(res["status"], "success")
        self.assertEqual(res["language"], "mr")
        audio_path = Path(res["audio_file"])
        self.assertTrue(audio_path.exists())
        self.assertGreater(res["file_size_bytes"], 0)


class TestPrivacyManager(unittest.TestCase):
    """Tests SHA-256 anonymization and temporary audio cleanup."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.privacy = PrivacyManager(temp_dir=self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_user_id_anonymization(self):
        phone = "+919876543210"
        hashed = self.privacy.anonymize_user_id(phone)
        self.assertTrue(hashed.startswith("USER_"))
        self.assertNotIn("9876543210", hashed)
        # Deterministic
        self.assertEqual(hashed, self.privacy.anonymize_user_id(phone))

    def test_audio_lifecycle_cleanup(self):
        dummy_file = Path(self.tmp_dir) / "farmer_audio_sample.wav"
        dummy_file.write_text("dummy audio data")
        self.privacy.register_temp_audio(str(dummy_file))

        self.assertTrue(dummy_file.exists())
        cleaned = self.privacy.cleanup_all_session_audio()
        self.assertEqual(cleaned, 1)
        self.assertFalse(dummy_file.exists())


class TestEndToEndVoiceRAG(unittest.TestCase):
    """Integration test: Audio In -> ASR -> RAG -> TTS -> Audio Out."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.assistant = VoiceAgriculturalAssistant(data_dir=self.tmp_dir)

        # Ingest and approve official ICAR Cotton advisory
        meta_cotton = DocumentMetadata(
            doc_id="DOC_COTTON_OFFICIAL",
            title="ICAR-CICR Cotton Advisory: Pink Bollworm Management",
            source="ICAR-CICR Advisory Bulletin 2026",
            publisher="Indian Council of Agricultural Research",
            crop="Cotton",
            region="Maharashtra",
            season="Kharif",
            language="en",
            publication_date="2026-05-15"
        )
        self.assistant.rag_service.ingest_pdf(
            "data/raw_documents/cotton_pink_bollworm_icar_advisory.pdf",
            meta_cotton,
            auto_approve=True
        )

        # Ingest and approve official KVK Wheat advisory
        meta_wheat = DocumentMetadata(
            doc_id="DOC_WHEAT_OFFICIAL",
            title="KVK Wheat Advisory: Yellow Rust Surveillance",
            source="KVK Agricultural Extension Bulletin 2026",
            publisher="Krishi Vigyan Kendra (KVK)",
            crop="Wheat",
            region="Punjab",
            season="Rabi",
            language="en",
            publication_date="2026-01-20"
        )
        self.assistant.rag_service.ingest_pdf(
            "data/raw_documents/wheat_yellow_rust_kvk_bulletin.pdf",
            meta_wheat,
            auto_approve=True
        )

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_voice_query_answered_with_audio_response(self):
        # 1. Create a synthetic test WAV representing a voice note
        test_audio_path = Path(self.tmp_dir) / "hi_voice_question.wav"
        self.assistant.preprocessor.generate_synthetic_tone_wav(str(test_audio_path), duration=2.0)

        # 2. Register mock transcription for the test audio to verify pipeline deterministically
        hi_transcript = "कपास में गुलाबी सुंडी की रोकथाम के लिए फेरोमोन ट्रैप"
        self.assistant.transcriber.register_mock_audio(
            file_path=str(test_audio_path),
            transcript=hi_transcript,
            language="hi",
            confidence=0.92
        )

        # 3. Process complete voice query
        result = self.assistant.process_voice_query(
            audio_path=str(test_audio_path),
            user_phone_or_id="9876543210",
            language_hint="hi"
        )

        # 4. Verify outcomes
        self.assertEqual(result["status"], "answered")
        self.assertEqual(result["detected_language"], "hi")
        self.assertEqual(result["transcript"], hi_transcript)
        self.assertGreater(len(result["citations"]), 0)
        self.assertIn("Indian Council of Agricultural Research", result["citations"][0])

        # Verify spoken audio response was generated
        audio_out = Path(result["audio_response_path"])
        self.assertTrue(audio_out.exists(), "Audio output response must exist")
        self.assertGreater(audio_out.stat().st_size, 0)

    def test_voice_query_out_of_scope_safely_refused_with_spoken_referral(self):
        # 1. Create a synthetic test WAV
        test_audio_path = Path(self.tmp_dir) / "crypto_voice_question.wav"
        self.assistant.preprocessor.generate_synthetic_tone_wav(str(test_audio_path), duration=2.0)

        # 2. Register out-of-scope query
        unsupported_transcript = "What are the latest cryptocurrency prices in Bengaluru?"
        self.assistant.transcriber.register_mock_audio(
            file_path=str(test_audio_path),
            transcript=unsupported_transcript,
            language="en",
            confidence=0.95
        )

        # 3. Process voice query
        result = self.assistant.process_voice_query(
            audio_path=str(test_audio_path),
            user_phone_or_id="9876543210",
            language_hint="en"
        )

        # 4. Verify zero-guessing safe refusal with spoken referral
        self.assertEqual(result["status"], "refused")
        self.assertIn("1800-180-1551", result["text_response"])
        self.assertIn("Kisan Call Centre", result["text_response"])

        # Spoken audio file must exist and contain the refusal message
        audio_out = Path(result["audio_response_path"])
        self.assertTrue(audio_out.exists())


if __name__ == "__main__":
    unittest.main()
