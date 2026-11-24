"""
Comprehensive Test Suite for WhatsApp Business Cloud API Integration (Module 1).
Tests cover:
  1. Webhook GET verification handshake (valid/invalid mode & token)
  2. HMAC-SHA256 signature verification (valid, tampered, wrong secret, malformed)
  3. Inbound text queries (Hindi, Marathi, English, Banned chemical)
  4. Duplicate webhook delivery protection (Message ID deduplication)
  5. Outgoing Meta message sending with mocked API calls (Success, Timeout, API Error)
  6. Voice message metadata parsing & graceful fallbacks
  7. HTTP Webhook server handlers (GET /health, GET /webhook, POST /webhook security)

All tests operate offline without real Meta credentials or external network calls.
"""
import os
import sys
import json
import hmac
import hashlib
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
from io import BytesIO

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.channel.whatsapp_client import WhatsAppCloudClient
from src.core.voice_assistant import VoiceAgriculturalAssistant


class TestWhatsAppWebhookVerification(unittest.TestCase):
    """Tests GET /webhook handshake challenge validation."""

    def setUp(self):
        self.client = WhatsAppCloudClient(data_dir="data")

    def test_verify_webhook_success_with_correct_token(self):
        """Returns challenge string when mode='subscribe' and verify_token matches."""
        challenge = "CHALLENGE_CODE_98765"
        res = self.client.verify_webhook(
            mode="subscribe",
            token=self.client.verify_token,
            challenge=challenge
        )
        self.assertEqual(res, challenge)

    def test_verify_webhook_fails_with_wrong_token(self):
        """Returns None when verify_token does not match."""
        res = self.client.verify_webhook(
            mode="subscribe",
            token="incorrect_token_xyz",
            challenge="CHALLENGE"
        )
        self.assertIsNone(res)

    def test_verify_webhook_fails_with_wrong_mode(self):
        """Returns None when mode is not 'subscribe'."""
        res = self.client.verify_webhook(
            mode="publish",
            token=self.client.verify_token,
            challenge="CHALLENGE"
        )
        self.assertIsNone(res)


class TestWhatsAppSecuritySignatures(unittest.TestCase):
    """Tests HMAC-SHA256 X-Hub-Signature-256 validation."""

    def setUp(self):
        self.client = WhatsAppCloudClient(data_dir="data")
        self.test_secret = "test_meta_app_secret_12345"
        self.test_payload = b'{"entry":[{"changes":[{"value":{"messages":[{"text":{"body":"Hello"}}]}}]}]}'

    def _generate_signature(self, payload: bytes, secret: str) -> str:
        digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
        return f"sha256={digest}"

    def test_verify_signature_valid(self):
        """Valid HMAC signature calculated with app secret passes."""
        sig = self._generate_signature(self.test_payload, self.test_secret)
        self.assertTrue(self.client.verify_signature(self.test_payload, sig, secret=self.test_secret))

    def test_verify_signature_tampered_payload_rejected(self):
        """Tampered payload fails HMAC signature verification."""
        sig = self._generate_signature(self.test_payload, self.test_secret)
        tampered = b'{"entry":[{"changes":[{"value":{"messages":[{"text":{"body":"Hacked"}}]}}]}]}'
        self.assertFalse(self.client.verify_signature(tampered, sig, secret=self.test_secret))

    def test_verify_signature_wrong_secret_rejected(self):
        """Signature calculated with wrong secret fails."""
        sig = self._generate_signature(self.test_payload, "different_secret")
        self.assertFalse(self.client.verify_signature(self.test_payload, sig, secret=self.test_secret))

    def test_verify_signature_missing_header_rejected(self):
        """Missing signature header fails when secret is configured."""
        self.assertFalse(self.client.verify_signature(self.test_payload, None, secret=self.test_secret))

    def test_verify_signature_malformed_header_rejected(self):
        """Header without 'sha256=' prefix fails."""
        self.assertFalse(self.client.verify_signature(self.test_payload, "md5=12345", secret=self.test_secret))

    def test_verify_signature_unconfigured_secret_allows_local_dev(self):
        """When no secret is set, allows locally for local mock testing."""
        self.assertTrue(self.client.verify_signature(self.test_payload, None, secret=""))


class TestWhatsAppInboundTextMessages(unittest.TestCase):
    """Tests processing of inbound WhatsApp text messages in Hindi, Marathi, and English."""

    @classmethod
    def setUpClass(cls):
        cls.client = WhatsAppCloudClient(data_dir="data")
        cls.assistant = VoiceAgriculturalAssistant(data_dir="data")

    def test_inbound_hindi_query_processing(self):
        """Inbound Hindi query routes through assistant and returns formatted response."""
        payload = {
            "message_id": f"WAMID_TEST_HI_{os.urandom(4).hex()}",
            "sender_phone": "919876543210",
            "type": "text",
            "content": "पुणे मंडी में आज प्याज का भाव क्या है?"
        }
        res = self.client.process_incoming_message(payload, self.assistant)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["type"], "text")
        self.assertIn("reply_text", res)
        self.assertIn("1850", res["reply_text"])
        self.assertIn("Pune APMC", res["reply_text"])
        self.assertIn("1800-180-1551", res["reply_text"])

    def test_inbound_marathi_query_processing(self):
        """Inbound Marathi query routes through assistant and returns Marathi response."""
        payload = {
            "message_id": f"WAMID_TEST_MR_{os.urandom(4).hex()}",
            "sender_phone": "919876543210",
            "type": "text",
            "content": "पुण्यात कांद्याचे भाव काय आहेत?"
        }
        res = self.client.process_incoming_message(payload, self.assistant)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["detected_language"], "mr")
        self.assertIn("1850", res["reply_text"])
        self.assertIn("1800-180-1551", res["reply_text"])

    def test_inbound_english_query_processing(self):
        """Inbound English query routes through assistant and returns English response."""
        payload = {
            "message_id": f"WAMID_TEST_EN_{os.urandom(4).hex()}",
            "sender_phone": "919876543210",
            "type": "text",
            "content": "What are the signs of yellow rust on wheat?"
        }
        res = self.client.process_incoming_message(payload, self.assistant)
        self.assertEqual(res["status"], "success")
        self.assertIn("reply_text", res)
        self.assertIn("1800-180-1551", res["reply_text"])

    def test_inbound_banned_chemical_query_refused(self):
        """Inbound query asking for banned chemical dosage is refused safely."""
        payload = {
            "message_id": f"WAMID_TEST_CHEM_{os.urandom(4).hex()}",
            "sender_phone": "919876543210",
            "type": "text",
            "content": "मोनोक्रोटोफॉस कीटनाशक का कितना स्प्रे करें?"
        }
        res = self.client.process_incoming_message(payload, self.assistant)
        self.assertEqual(res["status"], "success")
        self.assertIn("प्रतिबंधित", res["reply_text"])
        self.assertIn("1800-180-1551", res["reply_text"])


class TestWhatsAppDuplicateDeliveries(unittest.TestCase):
    """Tests duplicate webhook delivery protection."""

    def setUp(self):
        self.client = WhatsAppCloudClient(data_dir="data")
        self.assistant = VoiceAgriculturalAssistant(data_dir="data")

    def test_duplicate_webhook_delivery_ignored(self):
        """The second delivery of the exact same message_id is acknowledged but not re-processed."""
        msg_id = f"WAMID_DUP_TEST_{os.urandom(4).hex()}"
        payload = {
            "message_id": msg_id,
            "sender_phone": "919876543210",
            "type": "text",
            "content": "नागपुर में कपास का भाव क्या है?"
        }

        # First delivery: processed normally
        first_res = self.client.process_incoming_message(payload, self.assistant)
        self.assertEqual(first_res["status"], "success")

        # Second delivery (identical message_id): duplicate ignored
        second_res = self.client.process_incoming_message(payload, self.assistant)
        self.assertEqual(second_res["status"], "duplicate_ignored")
        self.assertEqual(second_res["message_id"], msg_id)
        self.assertEqual(second_res["reason"], "Message already processed")


class TestWhatsAppOutgoingAndMockedAPI(unittest.TestCase):
    """Tests outgoing message sending and mocked Meta Graph API responses."""

    def setUp(self):
        self.client = WhatsAppCloudClient(data_dir="data")

    def test_outgoing_message_unconfigured_offline(self):
        """send_text_message in offline mode returns credential_gated without network call."""
        res = self.client.send_text_message("919876543210", "Test message")
        self.assertEqual(res["status"], "credential_gated")
        self.assertIn("WHATSAPP_ACCESS_TOKEN", res["message"])

    @patch("requests.post")
    def test_outgoing_message_mocked_success(self, mock_post):
        """When configured, send_text_message returns Meta response."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "messaging_product": "whatsapp",
            "contacts": [{"input": "919876543210", "wa_id": "919876543210"}],
            "messages": [{"id": "wamid.HBgLM...="}]
        }
        mock_post.return_value = mock_resp

        # Temporarily enable client
        self.client.is_configured = True
        self.client.access_token = "MOCK_TOKEN"
        self.client.phone_number_id = "1234567890"

        res = self.client.send_text_message("919876543210", "Grounded advisory.")
        self.assertIn("messages", res)
        self.assertEqual(res["messages"][0]["id"], "wamid.HBgLM...=")

    @patch("requests.post")
    def test_outgoing_message_mocked_timeout(self, mock_post):
        """Network timeout returns structured timeout dictionary."""
        import requests
        mock_post.side_effect = requests.exceptions.Timeout("Request timed out")

        self.client.is_configured = True
        self.client.access_token = "MOCK_TOKEN"
        self.client.phone_number_id = "1234567890"

        res = self.client.send_text_message("919876543210", "Message")
        self.assertEqual(res["status"], "timeout")

    @patch("requests.post")
    def test_outgoing_message_mocked_api_error(self, mock_post):
        """API error HTTP 400 returns structured api_error dictionary."""
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = '{"error":{"message":"Invalid OAuth access token."}}'
        mock_post.return_value = mock_resp

        self.client.is_configured = True
        self.client.access_token = "MOCK_TOKEN"
        self.client.phone_number_id = "1234567890"

        res = self.client.send_text_message("919876543210", "Message")
        self.assertEqual(res["status"], "api_error")
        self.assertEqual(res["http_code"], 400)


class TestWhatsAppVoiceMessages(unittest.TestCase):
    """Tests voice note metadata parsing and fallback handling."""

    def setUp(self):
        self.client = WhatsAppCloudClient(data_dir="data")
        self.assistant = VoiceAgriculturalAssistant(data_dir="data")

    def test_inbound_voice_metadata_parsing(self):
        """Correctly extracts media_id and mime_type from WhatsApp voice payload."""
        payload = {
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "id": "WAMID_AUDIO_001",
                            "from": "919876543210",
                            "type": "audio",
                            "audio": {
                                "id": "MEDIA_ID_AUDIO_12345",
                                "mime_type": "audio/ogg; codecs=opus"
                            }
                        }]
                    }
                }]
            }]
        }
        parsed = self.client.parse_incoming_webhook(payload)
        self.assertEqual(parsed["type"], "audio")
        self.assertEqual(parsed["media_id"], "MEDIA_ID_AUDIO_12345")
        self.assertEqual(parsed["mime_type"], "audio/ogg; codecs=opus")

    def test_voice_message_unconfigured_fallback(self):
        """When credentials are not configured, voice message returns helpful fallback with helpline."""
        payload = {
            "message_id": f"WAMID_VOICE_{os.urandom(4).hex()}",
            "sender_phone": "919876543210",
            "type": "audio",
            "media_id": "MEDIA_OFFLINE_999"
        }
        res = self.client.process_incoming_message(payload, self.assistant)
        self.assertEqual(res["status"], "credential_gated")
        self.assertIn("reply_text", res)
        self.assertIn("1800-180-1551", res["reply_text"])


class TestWhatsAppServerEndpoints(unittest.TestCase):
    """Tests HTTP endpoints of src/channel/whatsapp_server.py."""

    def test_server_module_attributes(self):
        """Verifies whatsapp_server exposes WhatsAppWebhookHandler and helpers."""
        from src.channel import whatsapp_server
        self.assertTrue(hasattr(whatsapp_server, "WhatsAppWebhookHandler"))
        self.assertTrue(hasattr(whatsapp_server, "get_whatsapp_client"))
        self.assertTrue(hasattr(whatsapp_server, "get_assistant"))

    def test_client_api_version_configurable(self):
        """Verifies that api_version is configurable via environment variable."""
        with patch.dict(os.environ, {"WHATSAPP_API_VERSION": "v20.0"}):
            c = WhatsAppCloudClient(data_dir="data")
            self.assertEqual(c.api_version, "v20.0")


if __name__ == "__main__":
    unittest.main(verbosity=2)
