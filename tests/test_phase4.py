"""
Automated Unit and Integration Test Suite for Phase 4:
Live Mandi Market Prices, Live Weather & Agromet Advisory,
Multilingual NLU (Intent & Entity Extraction), and Intelligent Routing.
Uses Python's standard `unittest` framework.
"""
import unittest
import tempfile
import shutil
from pathlib import Path

from src.tools.mandi_price_tool import MandiPriceTool
from src.tools.weather_tool import WeatherTool
from src.nlu.intent_classifier import IntentClassifier
from src.nlu.entity_extractor import EntityExtractor
from src.nlu.query_router import QueryRouter
from src.knowledge.models import DocumentMetadata
from src.core.voice_assistant import VoiceAgriculturalAssistant


class TestMandiPriceTool(unittest.TestCase):
    """Tests authentic mandi market price retrieval, caching, and clarification."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.cache_file = Path(self.tmp_dir) / "mandi_cache.json"
        self.tool = MandiPriceTool(cache_file=str(self.cache_file))

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_get_mandi_price_cotton_nagpur(self):
        res = self.tool.get_mandi_prices(commodity="Cotton", district="Nagpur")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["commodity"], "Cotton")
        self.assertEqual(res["district"], "Nagpur")
        self.assertGreater(res["modal_price"], 0)
        self.assertEqual(res["unit"], "₹/Quintal")
        self.assertIn("Agmarknet", res["source"])
        self.assertIn("Nagpur", res["spoken_text_hi"])
        self.assertIn("₹/Quintal", res["spoken_text_hi"])

    def test_get_mandi_price_onion_nashik(self):
        res = self.tool.get_mandi_prices(commodity="Onion", district="Nashik")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["commodity"], "Onion")
        self.assertGreater(res["modal_price"], 0)

    def test_get_mandi_price_onion_pune(self):
        """Tests that Pune Onion returns authentic Agmarknet reference records."""
        res = self.tool.get_mandi_prices(commodity="Onion", district="Pune")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["commodity"], "Onion")
        self.assertEqual(res["district"], "Pune")
        self.assertEqual(res["modal_price"], 1850)
        self.assertTrue(res["is_historical"])
        self.assertIn("Agmarknet", res["source"])
        self.assertIn("Pune APMC", res["spoken_text_hi"])

    def test_missing_commodity_requests_clarification(self):
        res = self.tool.get_mandi_prices(commodity="")
        self.assertEqual(res["status"], "clarification_required")
        self.assertIn("फसल का नाम बताएं", res["message"])

    def test_unknown_commodity_not_found_has_non_empty_multilingual_messages(self):
        """Tests that unknown commodities never return empty responses and cite helpline."""
        res = self.tool.get_mandi_prices(commodity="ExoticAvocado123", district="Pune")
        self.assertEqual(res["status"], "not_found")
        self.assertEqual(len(res["records"]), 0)
        self.assertTrue(bool(res["spoken_text_hi"]))
        self.assertTrue(bool(res["spoken_text_mr"]))
        self.assertTrue(bool(res["spoken_text_en"]))
        self.assertIn("1800-180-1551", res["spoken_text_hi"])
        self.assertIn("Agmarknet", res["spoken_text_hi"])


class TestWeatherTool(unittest.TestCase):
    """Tests real/cached weather parameter retrieval and agromet advisory rules."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.cache_file = Path(self.tmp_dir) / "weather_cache.json"
        self.tool = WeatherTool(cache_file=str(self.cache_file))

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_get_weather_nagpur(self):
        res = self.tool.get_weather(location_name="Nagpur")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["location"], "Nagpur")
        self.assertIn("temperature", res["weather"])
        self.assertIn("humidity", res["weather"])
        self.assertIn("precipitation_mm", res["weather"])
        self.assertIn("agromet_advisory", res)
        self.assertIn("Open-Meteo", res["source"])
        self.assertIn("Nagpur", res["spoken_text_hi"])

    def test_weather_advisory_spray_warning_on_rain(self):
        advisory = self.tool._generate_agromet_advisory(temp=25.0, rain_mm=5.0, humidity=80.0)
        self.assertIn("छिड़काव और सिंचाई स्थगित", advisory["hi"])
        self.assertIn("फवारणी आणि सिंचन पुढे ढकलावे", advisory["mr"])

    def test_missing_location_requests_clarification(self):
        res = self.tool.get_weather(location_name="")
        self.assertEqual(res["status"], "clarification_required")

    def test_unknown_location_returns_not_found(self):
        res = self.tool.get_weather(location_name="UnknownImaginaryPlaceXYZ")
        self.assertEqual(res["status"], "location_not_found")


class TestMultilingualNLU(unittest.TestCase):
    """Tests Intent Classification and Entity Extraction across Hindi, Marathi, and English."""

    def test_intent_classification(self):
        # Mandi intent
        q_mandi_hi = "नागपुर मंडी में कपास का भाव क्या है?"
        intent, conf = IntentClassifier.classify_intent(q_mandi_hi)
        self.assertEqual(intent, "mandi_price")

        # Weather intent
        q_weather_mr = "पुणे येथील आजचे हवामान कसे आहे?"
        intent, conf = IntentClassifier.classify_intent(q_weather_mr)
        self.assertEqual(intent, "weather")

        # Pest/Disease intent
        q_pest_hi = "कपास में गुलाबी सुंडी कीट का नियंत्रण कैसे करें?"
        intent, conf = IntentClassifier.classify_intent(q_pest_hi)
        self.assertEqual(intent, "pest_disease")

        # Out of scope intent
        q_crypto = "What is the bitcoin cryptocurrency rate today?"
        intent, conf = IntentClassifier.classify_intent(q_crypto)
        self.assertEqual(intent, "out_of_scope")

    def test_entity_extraction(self):
        extractor = EntityExtractor()

        # Hindi query with crop and district
        q1 = "नागपुर में कपास का क्या रेट है?"
        e1 = extractor.extract_entities(q1)
        self.assertEqual(e1["crop"], "Cotton")
        self.assertEqual(e1["district"], "Nagpur")

        # Marathi query with crop and district
        q2 = "नाशिक बाजारपेठेत कांद्याचा भाव काय आहे?"
        e2 = extractor.extract_entities(q2)
        self.assertEqual(e2["crop"], "Onion")
        self.assertEqual(e2["district"], "Nashik")

        # Query with pest and crop
        q3 = "कपाशीवरील गुलाबी बोंडअळी नियंत्रणासाठी उपाय सांगा"
        e3 = extractor.extract_entities(q3)
        self.assertEqual(e3["crop"], "Cotton")
        self.assertEqual(e3["disease_or_pest"], "Pink Bollworm")


class TestQueryRouterAndPipelineIntegration(unittest.TestCase):
    """Integration test: Routing queries to Mandi Tool, Weather Tool, RAG Engine, or Safe Refusal."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.assistant = VoiceAgriculturalAssistant(data_dir=self.tmp_dir)

        # Ingest approved ICAR Cotton advisory
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

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_text_route_mandi_price(self):
        q = "नागपुर मंडी में कपास का भाव क्या है?"
        res = self.assistant.process_text_query(q, language_hint="hi")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["intent"], "mandi_price")
        self.assertIn("7450", res["text_response"])
        self.assertIn("Agmarknet", res["citations"][0])

    def test_text_route_mandi_price_pune_onion(self):
        """Verifies exact user question 'पुणे मंडी में आज प्याज का भाव क्या है?'."""
        q = "पुणे मंडी में आज प्याज का भाव क्या है?"
        res = self.assistant.process_text_query(q, language_hint="hi")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["intent"], "mandi_price")
        self.assertEqual(res["decision"], "ANSWER")
        self.assertTrue(bool(res["text_response"]))
        self.assertIn("1850", res["text_response"])
        self.assertIn("Pune APMC", res["text_response"])
        self.assertIn("Agmarknet", res["citations"][0])

    def test_entity_extraction_pune_marathi_inflections(self):
        """Verifies Marathi inflections for Pune and Onion."""
        extractor = EntityExtractor()
        entities = extractor.extract_entities("पुण्यात कांद्याचे भाव काय आहेत?")
        self.assertEqual(entities["district"], "Pune")
        self.assertEqual(entities["crop"], "Onion")

    def test_text_route_weather_advisory(self):
        q = "पुणे येथील आजचे हवामान कसे आहे?"
        res = self.assistant.process_text_query(q, language_hint="mr")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["intent"], "weather")
        self.assertIn("Open-Meteo", res["citations"][0])
        self.assertIn("Pune", res["text_response"])

    def test_text_route_rag_knowledge(self):
        q = "कपास में गुलाबी सुंडी नियंत्रण के लिए फेरोमोन ट्रैप"
        res = self.assistant.process_text_query(q, language_hint="hi")
        self.assertEqual(res["status"], "answered")
        self.assertIn("Indian Council of Agricultural Research", res["citations"][0])

    def test_text_route_out_of_scope_refusal(self):
        q = "What is the cryptocurrency price of ethereum?"
        res = self.assistant.process_text_query(q, language_hint="en")
        self.assertEqual(res["status"], "refused")
        self.assertEqual(res["intent"], "out_of_scope")
        self.assertIn("1800-180-1551", res["text_response"])

    def test_voice_route_mandi_price_with_audio_playback(self):
        # 1. Create a synthetic test WAV representing a voice note
        test_audio_path = Path(self.tmp_dir) / "hi_mandi_voice.wav"
        self.assistant.preprocessor.generate_synthetic_tone_wav(str(test_audio_path), duration=2.0)

        # 2. Register mock transcription for the test audio
        mandi_transcript = "नागपुर में कपास का मंडी भाव क्या है?"
        self.assistant.transcriber.register_mock_audio(
            file_path=str(test_audio_path),
            transcript=mandi_transcript,
            language="hi",
            confidence=0.93
        )

        # 3. Process voice query
        res = self.assistant.process_voice_query(str(test_audio_path), language_hint="hi")

        # 4. Verify outcomes
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["intent"], "mandi_price")
        self.assertEqual(res["detected_language"], "hi")
        self.assertIn("Agmarknet", res["citations"][0])

        # Verify generated voice output file
        audio_out = Path(res["audio_response_path"])
        self.assertTrue(audio_out.exists())
        self.assertGreater(audio_out.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
