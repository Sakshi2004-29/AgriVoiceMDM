"""
WhatsApp Business Cloud API Adapter (Module 1).
Provides secure, credential-gated webhook handling for WhatsApp voice notes and text messages.
Adheres to official Meta WhatsApp Business API specification (Graph API v19.0 / v20.0).

Features:
1. Meta Webhook Verification Handshake (GET /webhook)
2. HMAC-SHA256 Payload Signature Verification (X-Hub-Signature-256)
3. Inbound Payload Parsing (Text & Audio Messages)
4. Duplicate Webhook Delivery Protection (Message ID Tracking)
5. Outgoing Meta Graph API Message Dispatching with Timeouts & Error Handling
6. Voice-Message Ingestion & Fallback Handling
7. Privacy-Conscious Farmer Identification (SHA-256 Hashing)
8. Shared Unified AI Backend Integration (VoiceAgriculturalAssistant)
"""
import os
import json
import hmac
import hashlib
import logging
from typing import Dict, Any, Optional, Set, List
from pathlib import Path
import requests
from dotenv import load_dotenv

from src.channel.privacy_manager import PrivacyManager

load_dotenv()
logger = logging.getLogger(__name__)


class WhatsAppCloudClient:
    """
    Handles WhatsApp Business Cloud API communication.
    Operates in live mode when credentials are provided in .env,
    or diagnostic/offline mode when credentials are missing.
    """

    DEFAULT_API_VERSION = "v19.0"

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "").strip()
        self.access_token = os.getenv("WHATSAPP_ACCESS_TOKEN", "").strip()
        self.verify_token = os.getenv("WHATSAPP_VERIFY_TOKEN", "agri_assistant_verify_token").strip()
        self.app_secret = os.getenv("WHATSAPP_APP_SECRET", "").strip()
        self.api_version = os.getenv("WHATSAPP_API_VERSION", self.DEFAULT_API_VERSION).strip()

        # Check whether credentials are functionally configured
        self.is_configured = bool(
            self.phone_number_id and
            self.access_token and
            self.phone_number_id != "your_whatsapp_phone_number_id_here" and
            self.access_token != "your_whatsapp_access_token_here"
        )

        # Retain backward-compatible attribute
        self.GRAPH_API_VERSION = self.api_version

        # Privacy anonymizer
        self.privacy_manager = PrivacyManager(temp_dir=str(self.data_dir / "cache/temp_audio"))

        # Deduplication tracker for processed message IDs
        self.processed_message_ids: Set[str] = set()
        self._message_id_order: List[str] = []
        self._max_tracked_messages = 5000

    def verify_webhook(self, mode: str, token: str, challenge: str) -> Optional[str]:
        """
        Validates webhook subscription challenge from Meta (GET /webhook).
        Meta sends hub.mode='subscribe' and hub.verify_token.
        Returns the challenge string on success, or None on failure.
        """
        if mode == "subscribe" and token == self.verify_token:
            return challenge
        return None

    def verify_signature(
        self,
        payload_bytes: bytes,
        signature_header: Optional[str],
        secret: Optional[str] = None
    ) -> bool:
        """
        Validates incoming Meta webhook signature using HMAC-SHA256.
        Header format expected from Meta: 'sha256=<hex_digest>'
        If no secret is configured, allows locally with a warning for development.
        """
        app_secret = secret or self.app_secret
        if not app_secret:
            logger.debug("WHATSAPP_APP_SECRET not configured. Allowing in local dev mode.")
            return True

        if not signature_header:
            logger.warning("Missing X-Hub-Signature-256 header while WHATSAPP_APP_SECRET is set.")
            return False

        if not signature_header.startswith("sha256="):
            logger.warning(f"Malformed signature header: {signature_header}")
            return False

        expected_hash = signature_header.split("sha256=", 1)[1].strip()
        calculated_hash = hmac.new(
            app_secret.encode("utf-8"),
            payload_bytes,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(calculated_hash, expected_hash)

    def is_duplicate_message(self, message_id: Optional[str]) -> bool:
        """Checks whether a message_id has already been processed to prevent duplicate processing."""
        if not message_id:
            return False
        return message_id in self.processed_message_ids

    def mark_message_processed(self, message_id: Optional[str]):
        """Records message_id in bounded cache to prevent duplicate processing on Meta retries."""
        if not message_id:
            return
        if message_id not in self.processed_message_ids:
            self.processed_message_ids.add(message_id)
            self._message_id_order.append(message_id)
            if len(self._message_id_order) > self._max_tracked_messages:
                oldest = self._message_id_order.pop(0)
                self.processed_message_ids.discard(oldest)

    def parse_incoming_webhook(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extracts sender phone number, message type, message_id, text, or audio media ID
        from a Meta WhatsApp webhook payload (POST /webhook).
        """
        try:
            entry = payload.get("entry", [])[0]
            change = entry.get("changes", [])[0]
            value = change.get("value", {})
            messages = value.get("messages", [])

            if not messages:
                return None

            msg = messages[0]
            sender_phone = msg.get("from")
            msg_type = msg.get("type")
            msg_id = msg.get("id")

            if msg_type == "text":
                return {
                    "message_id": msg_id,
                    "sender_phone": sender_phone,
                    "type": "text",
                    "content": msg.get("text", {}).get("body", "").strip()
                }
            elif msg_type == "audio":
                audio_obj = msg.get("audio", {})
                return {
                    "message_id": msg_id,
                    "sender_phone": sender_phone,
                    "type": "audio",
                    "media_id": audio_obj.get("id"),
                    "mime_type": audio_obj.get("mime_type", "audio/ogg; codecs=opus")
                }
        except Exception:
            pass

        return None

    def download_media(self, media_id: str, dest_dir: Optional[str] = None) -> Dict[str, Any]:
        """
        Downloads a media file (voice note) from Meta Cloud API using media_id.
        In offline/unconfigured mode, returns structured credential_gated status.
        """
        if not self.is_configured:
            return {
                "status": "credential_gated",
                "message": "WHATSAPP_ACCESS_TOKEN or WHATSAPP_PHONE_NUMBER_ID not configured.",
                "media_id": media_id
            }

        target_dir = Path(dest_dir) if dest_dir else self.data_dir / "cache/temp_audio"
        target_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Step 1: Retrieve Media URL from Meta
            meta_url = f"https://graph.facebook.com/{self.api_version}/{media_id}"
            headers = {"Authorization": f"Bearer {self.access_token}"}
            res = requests.get(meta_url, headers=headers, timeout=10)
            if res.status_code != 200:
                return {"status": "error", "error": f"Failed to get media URL: {res.text}"}

            media_info = res.json()
            download_url = media_info.get("url")
            mime_type = media_info.get("mime_type", "audio/ogg")
            ext = ".ogg" if "ogg" in mime_type else ".wav"
            out_file = target_dir / f"whatsapp_{media_id}{ext}"

            # Step 2: Download the binary file content
            file_res = requests.get(download_url, headers=headers, timeout=15)
            if file_res.status_code != 200:
                return {"status": "error", "error": f"Failed to download media bytes: {file_res.text}"}

            with open(out_file, "wb") as f:
                f.write(file_res.content)

            self.privacy_manager.register_temp_audio(str(out_file))

            return {
                "status": "success",
                "file_path": str(out_file),
                "mime_type": mime_type,
                "media_id": media_id
            }
        except requests.exceptions.Timeout:
            logger.error("Media download timed out.")
            return {"status": "timeout", "error": "Download timed out"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def send_text_message(self, recipient_phone: str, text: str) -> Dict[str, Any]:
        """
        Sends an outbound text response via Meta WhatsApp Business Cloud API.
        Safe offline fallback if unconfigured. Never makes network calls with dummy credentials.
        """
        if not self.is_configured:
            return {
                "status": "credential_gated",
                "message": "WHATSAPP_ACCESS_TOKEN or WHATSAPP_PHONE_NUMBER_ID not configured.",
                "recipient": recipient_phone,
                "text_preview": text[:50]
            }

        url = f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        data = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_phone,
            "type": "text",
            "text": {"body": text}
        }

        try:
            resp = requests.post(url, headers=headers, json=data, timeout=10)
            if resp.status_code in [200, 201]:
                return resp.json()
            else:
                logger.error(f"WhatsApp API error {resp.status_code}: {resp.text}")
                return {
                    "status": "api_error",
                    "http_code": resp.status_code,
                    "error": resp.text
                }
        except requests.exceptions.Timeout:
            logger.error("WhatsApp API request timed out.")
            return {"status": "timeout", "error": "Request to Meta Graph API timed out."}
        except Exception as e:
            logger.error(f"WhatsApp network error: {e}")
            return {"status": "error", "error": str(e)}

    def send_audio_message(self, recipient_phone: str, audio_url: str) -> Dict[str, Any]:
        """
        Sends an outbound audio message link via WhatsApp Cloud API.
        """
        if not self.is_configured:
            return {
                "status": "credential_gated",
                "message": "WHATSAPP_ACCESS_TOKEN or WHATSAPP_PHONE_NUMBER_ID not configured.",
                "recipient": recipient_phone,
                "audio_url": audio_url
            }

        url = f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        data = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_phone,
            "type": "audio",
            "audio": {"link": audio_url}
        }

        try:
            resp = requests.post(url, headers=headers, json=data, timeout=10)
            if resp.status_code in [200, 201]:
                return resp.json()
            else:
                return {
                    "status": "api_error",
                    "http_code": resp.status_code,
                    "error": resp.text
                }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def format_whatsapp_reply(self, assistant_result: Dict[str, Any]) -> str:
        """
        Formats assistant response for WhatsApp readability, adding localized formatting,
        institutional citations, and the Kisan Call Centre toll-free helpline.
        Supports Hindi, Marathi, and English.
        """
        text = assistant_result.get("text_response") or assistant_result.get("spoken_text") or ""
        citations = assistant_result.get("citations", [])
        lang = assistant_result.get("detected_language") or "hi"

        if lang == "mr":
            header = "🌾 *कृषि वाणी (AgriVoice Assistant)*"
            citation_title = "📚 *अधिकृत संदर्भ (Institutional Sources):*"
            helpline = "📞 *किसान हेल्पलाइन:* 1800-180-1551 (टोल-फ्री)"
        elif lang == "en":
            header = "🌾 *AgriVoice Assistant*"
            citation_title = "📚 *Official Sources:*"
            helpline = "📞 *Kisan Call Centre:* 1800-180-1551 (Toll-Free)"
        else:  # Hindi default
            header = "🌾 *कृषि वाणी (AgriVoice Assistant)*"
            citation_title = "📚 *अधिकृत संदर्भ (Institutional Sources):*"
            helpline = "📞 *किसान हेल्पलाइन:* 1800-180-1551 (टोल-फ्री)"

        lines = [
            header,
            "─────────────────────────",
            text,
            ""
        ]

        if citations:
            lines.append(citation_title)
            for c in citations[:3]:
                lines.append(f"• {c}")
            lines.append("")

        lines.append(helpline)
        return "\n".join(lines)

    def process_incoming_message(
        self,
        parsed_message: Dict[str, Any],
        assistant: Any
    ) -> Dict[str, Any]:
        """
        Processes parsed WhatsApp message through the shared VoiceAgriculturalAssistant backend.
        Handles text queries and voice notes.
        Protects against duplicate deliveries.
        """
        sender_phone = parsed_message.get("sender_phone", "")
        msg_type = parsed_message.get("type", "text")
        message_id = parsed_message.get("message_id")

        # 1. Guard against duplicate webhook deliveries from Meta retries
        if message_id and self.is_duplicate_message(message_id):
            logger.info(f"Duplicate WhatsApp delivery ignored for message_id={message_id}")
            return {
                "status": "duplicate_ignored",
                "message_id": message_id,
                "sender_phone": sender_phone,
                "reason": "Message already processed"
            }

        if message_id:
            self.mark_message_processed(message_id)

        # 2. Text message handling
        if msg_type == "text":
            query = parsed_message.get("content", "")
            # Route through the exact same assistant backend as Streamlit
            assistant_result = assistant.process_text_query(
                query=query,
                user_phone_or_id=sender_phone
            )
            reply_text = self.format_whatsapp_reply(assistant_result)
            send_res = self.send_text_message(sender_phone, reply_text)

            return {
                "status": "success",
                "type": "text",
                "sender_phone": sender_phone,
                "user_id_hash": assistant_result.get("user_id_hash"),
                "query": query,
                "detected_language": assistant_result.get("detected_language"),
                "assistant_result": assistant_result,
                "reply_text": reply_text,
                "send_result": send_res
            }

        # 3. Audio / voice note message handling
        elif msg_type == "audio":
            media_id = parsed_message.get("media_id", "")
            dl_res = self.download_media(media_id)

            if dl_res["status"] == "success":
                audio_file = dl_res["file_path"]
                try:
                    # Process through speech pipeline
                    assistant_result = assistant.process_voice_query(
                        audio_path=audio_file,
                        user_phone_or_id=sender_phone
                    )
                    reply_text = self.format_whatsapp_reply(assistant_result)
                    send_res = self.send_text_message(sender_phone, reply_text)

                    return {
                        "status": "success",
                        "type": "audio",
                        "sender_phone": sender_phone,
                        "user_id_hash": assistant_result.get("user_id_hash"),
                        "media_id": media_id,
                        "transcript": assistant_result.get("transcript"),
                        "detected_language": assistant_result.get("detected_language"),
                        "assistant_result": assistant_result,
                        "reply_text": reply_text,
                        "send_result": send_res
                    }
                except Exception as e:
                    logger.error(f"Error processing downloaded voice note: {e}")
                    fallback_msg = (
                        "🌾 *कृषि वाणी (AgriVoice Assistant)*\n\n"
                        "आपला व्हॉइस संदेश प्राप्त झाला आहे, परंतु ऑडिओ डीकोडिंगमध्ये अडचण आली. "
                        "कृपया आपला प्रश्न टेक्स्ट (मजकूर) स्वरूपात पाठवा किंवा किसान कॉल सेंटर 1800-180-1551 (टोल-फ्री) वर संपर्क साधा."
                    )
                    send_res = self.send_text_message(sender_phone, fallback_msg)
                    return {
                        "status": "audio_processing_error",
                        "type": "audio",
                        "sender_phone": sender_phone,
                        "media_id": media_id,
                        "reply_text": fallback_msg,
                        "send_result": send_res,
                        "error": str(e)
                    }
            else:
                # Diagnostic/unconfigured fallback for voice note when credentials are not configured
                fallback_msg = (
                    "🌾 *कृषि वाणी (AgriVoice Assistant)*\n\n"
                    "आपला व्हॉइस संदेश प्राप्त झाला आहे. थेट व्हॉइस प्रक्रिया सुरू करण्यासाठी "
                    "कृपया WhatsApp Business क्रेडेन्शियल जोडा, किंवा आपला प्रश्न टेक्स्ट (मजकूर) संदेशाद्वारे पाठवा.\n\n"
                    "📞 *किसान कॉल सेंटर:* 1800-180-1551 (टोल-फ्री)"
                )
                send_res = self.send_text_message(sender_phone, fallback_msg)
                return {
                    "status": "credential_gated",
                    "type": "audio",
                    "sender_phone": sender_phone,
                    "media_id": media_id,
                    "reply_text": fallback_msg,
                    "send_result": send_res,
                    "download_status": dl_res
                }

        return {"status": "unsupported_type", "type": msg_type}
