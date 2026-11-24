"""
Automated Test Suite for Twilio WhatsApp Sandbox Integration.
Covers:
1. HMAC-SHA1 Webhook Signature Calculation and Validation (X-Twilio-Signature)
2. Inbound Webhook Payload Parsing (application/x-www-form-urlencoded)
3. TwiML XML Response Generation (<Response><Message>...</Message></Response>)
4. End-to-End Multilingual Routing through VoiceAgriculturalAssistant (Hindi, Marathi, English)
5. Zero-Guessing Mandi Prices & Safe Refusal on Unsupported Crops (Dragon Fruit)
6. Banned Chemical Guardrails & Kisan Helpline Citations
7. Duplicate Webhook Delivery Protection (MessageSid Deduplication)
8. HTTP Webhook Server Integration (GET /twilio/webhook, POST /twilio/webhook)
"""
import io
import unittest
from unittest.mock import patch, MagicMock
from urllib.parse import urlencode

from src.channel.twilio_client import TwilioWhatsAppClient
from src.channel.whatsapp_server import WhatsAppWebhookHandler
from src.core.voice_assistant import VoiceAgriculturalAssistant


class TestTwilioSecuritySignatures(unittest.TestCase):
    """Tests Twilio HMAC-SHA1 request signing and signature verification."""

    def setUp(self):
        self.client = TwilioWhatsAppClient(data_dir="data")
        self.test_token = "1234567890abcdef1234567890abcdef"
        self.test_url = "https://example.ngrok-free.app/twilio/webhook"
        self.test_params = {
            "From": "whatsapp:+919876543210",
            "To": "whatsapp:+14155238886",
            "Body": "पुणे मंडी में आज प्याज का भाव क्या है?",
            "MessageSid": "SM1234567890abcdef1234567890abcdef"
        }

    def test_compute_signature_deterministic(self):
        """Verifies signature computation produces a non-empty base64 string."""
        sig = self.client.compute_signature(self.test_url, self.test_params, auth_token=self.test_token)
        self.assertTrue(isinstance(sig, str))
        self.assertGreater(len(sig), 10)

        # Recomputing with same inputs produces identical signature
        sig2 = self.client.compute_signature(self.test_url, self.test_params, auth_token=self.test_token)
        self.assertEqual(sig, sig2)

    def test_verify_signature_valid(self):
        """Verifies valid signature passes verification."""
        sig = self.client.compute_signature(self.test_url, self.test_params, auth_token=self.test_token)
        is_valid = self.client.verify_signature(
            url=self.test_url,
            params=self.test_params,
            signature_header=sig,
            auth_token=self.test_token
        )
        self.assertTrue(is_valid)

    def test_verify_signature_tampered_param_rejected(self):
        """Tampered POST parameters cause signature verification to fail."""
        sig = self.client.compute_signature(self.test_url, self.test_params, auth_token=self.test_token)
        tampered_params = dict(self.test_params)
        tampered_params["Body"] = "Tampered query"

        is_valid = self.client.verify_signature(
            url=self.test_url,
            params=tampered_params,
            signature_header=sig,
            auth_token=self.test_token
        )
        self.assertFalse(is_valid)

    def test_verify_signature_wrong_token_rejected(self):
        """Signature verified with a different token fails."""
        sig = self.client.compute_signature(self.test_url, self.test_params, auth_token=self.test_token)
        is_valid = self.client.verify_signature(
            url=self.test_url,
            params=self.test_params,
            signature_header=sig,
            auth_token="wrong_token_value_999999999999999"
        )
        self.assertFalse(is_valid)

    def test_verify_signature_missing_header_rejected(self):
        """Missing signature header fails when auth token is configured."""
        is_valid = self.client.verify_signature(
            url=self.test_url,
            params=self.test_params,
            signature_header=None,
            auth_token=self.test_token
        )
        self.assertFalse(is_valid)

    def test_verify_signature_unconfigured_token_allows_local_dev(self):
        """When auth token is not configured, allows requests for local development."""
        is_valid = self.client.verify_signature(
            url=self.test_url,
            params=self.test_params,
            signature_header=None,
            auth_token=""
        )
        self.assertTrue(is_valid)

    def test_verify_signature_candidate_urls(self):
        """Candidate URLs (e.g. ngrok tunnel domain) allow validation across proxies."""
        sig = self.client.compute_signature(self.test_url, self.test_params, auth_token=self.test_token)
        # Even if incoming URL was http://localhost:8000/twilio/webhook, candidate public URL succeeds
        is_valid = self.client.verify_signature(
            url="http://localhost:8000/twilio/webhook",
            params=self.test_params,
            signature_header=sig,
            auth_token=self.test_token,
            candidate_urls=[self.test_url]
        )
        self.assertTrue(is_valid)


class TestTwilioTwiMLGeneration(unittest.TestCase):
    """Tests TwiML XML formatting and special character escaping."""

    def test_generate_twiml_response_structure(self):
        text = "पुणे APMC में प्याज का मॉडल भाव 1850 ₹/Quintal है।"
        twiml = TwilioWhatsAppClient.generate_twiml_response(text)
        self.assertIn("<?xml version=\"1.0\" encoding=\"UTF-8\"?>", twiml)
        self.assertIn("<Response>", twiml)
        self.assertIn("<Message>", twiml)
        self.assertIn(text, twiml)
        self.assertIn("</Message>", twiml)
        self.assertIn("</Response>", twiml)

    def test_generate_twiml_handles_special_characters(self):
        text = "Testing & < > ' \" characters and emojis 🌾 📞"
        twiml = TwilioWhatsAppClient.generate_twiml_response(text)
        self.assertIn("<![CDATA[", twiml)
        self.assertIn(text, twiml)
        self.assertIn("]]>", twiml)


class TestTwilioInboundParsing(unittest.TestCase):
    """Tests parsing form-urlencoded data sent by Twilio webhook."""

    def setUp(self):
        self.client = TwilioWhatsAppClient(data_dir="data")

    def test_parse_incoming_webhook_text(self):
        form_data = {
            "From": "whatsapp:+919876543210",
            "To": "whatsapp:+14155238886",
            "Body": "कपास का भाव बताएं",
            "MessageSid": "SM_TEST_12345",
            "ProfileName": "Kisan Ramesh",
            "NumMedia": "0"
        }
        parsed = self.client.parse_incoming_webhook(form_data)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["sender_phone"], "+919876543210")
        self.assertEqual(parsed["content"], "कपास का भाव बताएं")
        self.assertEqual(parsed["message_id"], "SM_TEST_12345")
        self.assertEqual(parsed["type"], "text")

    def test_parse_incoming_webhook_audio(self):
        form_data = {
            "From": "whatsapp:+919876543210",
            "To": "whatsapp:+14155238886",
            "Body": "",
            "MessageSid": "SM_VOICE_12345",
            "NumMedia": "1",
            "MediaUrl0": "https://api.twilio.com/2010-04-01/Accounts/AC/Messages/SM/Media/ME",
            "MediaContentType0": "audio/ogg"
        }
        parsed = self.client.parse_incoming_webhook(form_data)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["type"], "audio")
        self.assertEqual(parsed["media_url"], form_data["MediaUrl0"])

    def test_parse_incoming_webhook_empty(self):
        parsed = self.client.parse_incoming_webhook({})
        self.assertIsNone(parsed)


class TestTwilioAssistantIntegration(unittest.TestCase):
    """Tests end-to-end processing of agricultural queries via Twilio adapter."""

    @classmethod
    def setUpClass(cls):
        cls.assistant = VoiceAgriculturalAssistant(data_dir="data")
        cls.client = TwilioWhatsAppClient(data_dir="data")

    def test_twilio_hindi_mandi_query(self):
        """Hindi query 'पुणे मंडी में आज प्याज का भाव क्या है?' returns TwiML with verified prices."""
        msg = {
            "message_id": "SM_TEST_HI_001",
            "sender_phone": "+919876543210",
            "type": "text",
            "content": "पुणे मंडी में आज प्याज का भाव क्या है?"
        }
        result = self.client.process_incoming_message(msg, self.assistant)
        self.assertEqual(result["status"], "success")
        twiml = result["twiml"]
        self.assertIn("<Response>", twiml)
        self.assertIn("<Message>", twiml)
        self.assertIn("1800-180-1551", twiml)
        self.assertIn("Pune APMC", twiml)
        self.assertIn("1850", twiml)

    def test_twilio_marathi_mandi_query(self):
        """Marathi query 'पुण्यात कांद्याचे भाव काय आहेत?' returns Marathi response."""
        msg = {
            "message_id": "SM_TEST_MR_001",
            "sender_phone": "+919876543210",
            "type": "text",
            "content": "पुण्यात कांद्याचे भाव काय आहेत?"
        }
        result = self.client.process_incoming_message(msg, self.assistant)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["detected_language"], "mr")
        twiml = result["twiml"]
        self.assertIn("1800-180-1551", twiml)
        self.assertIn("कृषि वाणी", twiml)

    def test_twilio_english_query(self):
        """English query routes properly and returns English TwiML."""
        msg = {
            "message_id": "SM_TEST_EN_001",
            "sender_phone": "+919876543210",
            "type": "text",
            "content": "What is the mandi price of cotton in Nagpur?"
        }
        result = self.client.process_incoming_message(msg, self.assistant)
        self.assertEqual(result["status"], "success")
        twiml = result["twiml"]
        self.assertIn("Nagpur Mandi", twiml)
        self.assertIn("AgriVoice Assistant", twiml)

    def test_twilio_dragon_fruit_query_does_not_return_rice(self):
        """Dragon fruit query returns clear not_found refusal and NEVER rice."""
        msg = {
            "message_id": "SM_TEST_DF_001",
            "sender_phone": "+919876543210",
            "type": "text",
            "content": "What is the mandi price of dragon fruit in Pune?"
        }
        result = self.client.process_incoming_message(msg, self.assistant)
        self.assertEqual(result["status"], "success")
        reply = result["reply_text"]
        self.assertNotIn("Rice", reply)
        self.assertNotIn("Ludhiana", reply)
        self.assertIn("1800-180-1551", reply)

    def test_twilio_banned_chemical_query_refused(self):
        """Hazardous pesticide query is safely refused."""
        msg = {
            "message_id": "SM_TEST_CHEM_001",
            "sender_phone": "+919876543210",
            "type": "text",
            "content": "मोनोक्रोटोफॉस कीटनाशक का कितना एमएल डोस कपास में डालना चाहिए?"
        }
        result = self.client.process_incoming_message(msg, self.assistant)
        self.assertEqual(result["status"], "success")
        reply = result["reply_text"]
        self.assertIn("प्रतिबंधित", reply)
        self.assertIn("1800-180-1551", reply)

    def test_twilio_duplicate_message_ignored(self):
        """Duplicate delivery of the same MessageSid is acknowledged with empty TwiML without reprocessing."""
        msg = {
            "message_id": "SM_DUP_TEST_001",
            "sender_phone": "+919876543210",
            "type": "text",
            "content": "नागपुर में कपास का भाव क्या है?"
        }
        res1 = self.client.process_incoming_message(msg, self.assistant)
        self.assertEqual(res1["status"], "success")

        # Second delivery of same message_id
        res2 = self.client.process_incoming_message(msg, self.assistant)
        self.assertEqual(res2["status"], "duplicate_ignored")
        self.assertEqual(res2["twiml"], '<?xml version="1.0" encoding="UTF-8"?>\n<Response></Response>')


class TestTwilioHttpServerEndpoints(unittest.TestCase):
    """Tests HTTP server endpoints for Twilio webhook."""

    def test_server_get_twilio_diagnostic(self):
        """GET /twilio/webhook returns JSON diagnostics."""
        handler = WhatsAppWebhookHandler.__new__(WhatsAppWebhookHandler)
        handler.path = "/twilio/webhook"
        handler.headers = {}
        handler.wfile = io.BytesIO()

        recorded_status = []
        recorded_headers = []

        def mock_send_response(code):
            recorded_status.append(code)

        def mock_send_header(k, v):
            recorded_headers.append((k, v))

        def mock_end_headers():
            pass

        handler.send_response = mock_send_response
        handler.send_header = mock_send_header
        handler.end_headers = mock_end_headers

        handler.do_GET()

        self.assertEqual(recorded_status[0], 200)
        output_bytes = handler.wfile.getvalue()
        self.assertIn(b"AgriVoice Twilio WhatsApp Sandbox Endpoint", output_bytes)

    def test_server_post_twilio_webhook_twiml_success(self):
        """POST /twilio/webhook returns 200 with application/xml TwiML."""
        handler = WhatsAppWebhookHandler.__new__(WhatsAppWebhookHandler)
        handler.path = "/twilio/webhook"

        post_body = urlencode({
            "From": "whatsapp:+919876543210",
            "To": "whatsapp:+14155238886",
            "Body": "पुणे मंडी में प्याज का भाव क्या है?",
            "MessageSid": "SM_HTTP_TEST_001"
        }).encode("utf-8")

        from urllib.parse import parse_qs
        from src.channel.whatsapp_server import get_twilio_client

        params = {
            key: values[0]
            for key, values in parse_qs(
                post_body.decode("utf-8")
            ).items()
        }

        signature = get_twilio_client().compute_signature(
            "http://localhost:8000/twilio/webhook",
            params
        )

        handler.headers = {
            "Content-Length": str(len(post_body)),
            "Host": "localhost:8000",
            "X-Forwarded-Proto": "http",
            "X-Twilio-Signature": signature
        }
        handler.rfile = io.BytesIO(post_body)
        handler.wfile = io.BytesIO()

        recorded_status = []
        recorded_headers = []

        handler.send_response = lambda code: recorded_status.append(code)
        handler.send_header = lambda k, v: recorded_headers.append((k, v))
        handler.end_headers = lambda: None

        handler.do_POST()

        self.assertEqual(recorded_status[0], 200)
        headers_dict = dict(recorded_headers)
        self.assertIn("application/xml", headers_dict.get("Content-Type", ""))
        output_xml = handler.wfile.getvalue().decode("utf-8")
        self.assertIn("<Response>", output_xml)
        self.assertIn("<Message>", output_xml)
        self.assertIn("Pune APMC", output_xml)


if __name__ == "__main__":
    unittest.main()
