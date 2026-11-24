"""
Twilio WhatsApp Sandbox Adapter (Module 1 Extension).
Handles:
1. Twilio Webhook Payload Parsing (application/x-www-form-urlencoded)
2. HMAC-SHA1 Webhook Signature Verification (X-Twilio-Signature)
3. Formatting Assistant Responses into standard Twilio TwiML (<Response><Message>...</Message></Response>)
4. Multilingual Agricultural Query Processing via VoiceAgriculturalAssistant backend
5. Privacy Management with SHA-256 Phone Number Anonymization
6. Optional Outbound REST API dispatch via Twilio Messages API
7. Two-Way Voice: Download Twilio voice notes, transcribe, synthesize reply, serve via /media endpoint
"""
import os
import re
import hmac
import base64
import hashlib
import logging
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, List
import requests
from dotenv import load_dotenv

from src.channel.privacy_manager import PrivacyManager

load_dotenv()
logger = logging.getLogger("TwilioWhatsAppClient")


class TwilioWhatsAppClient:
    """
    Twilio WhatsApp Sandbox Adapter for AgriVoice Assistant.
    Provides TwiML response generation and Twilio webhook signature verification.
    """

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.privacy_manager = PrivacyManager(temp_dir=str(self.data_dir / "cache/temp_audio"))

        # Twilio Credentials from environment
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
        self.from_number = os.getenv("TWILIO_PHONE_NUMBER", "whatsapp:+14155238886").strip()
        self.configured_webhook_url = os.getenv("TWILIO_WEBHOOK_URL", "").strip()

        # Public base URL for media files (ngrok HTTPS URL) used in voice replies
        # e.g. https://xxxx.ngrok-free.app  (no trailing slash, no /twilio/webhook suffix)
        raw_public_url = os.getenv("TWILIO_PUBLIC_BASE_URL", "").strip()
        if not raw_public_url and self.configured_webhook_url:
            # Derive from webhook URL by stripping the path component
            from urllib.parse import urlparse as _urlparse
            _p = _urlparse(self.configured_webhook_url)
            raw_public_url = f"{_p.scheme}://{_p.netloc}"
        self.public_base_url = raw_public_url.rstrip("/")

        # Audio output directory (same dir used by SpeechSynthesizer)
        self._audio_output_dir = self.data_dir / "cache/audio_output"
        self._audio_output_dir.mkdir(parents=True, exist_ok=True)

        # Deduplication cache for MessageSid (bounded FIFO, max 5000 entries)
        self._processed_message_ids: List[str] = []
        self._max_cache_size = 5000

        # Remember language preferences during this server session.
        # Key: anonymized sender ID; value: mr, hi, or en.
        self._language_preferences = {}

    @property
    def is_configured(self) -> bool:
        """Returns True if minimum Twilio credentials are configured."""
        return bool(
            self.account_sid
            and self.auth_token
            and self.account_sid != "your_twilio_account_sid_here"
            and self.auth_token != "your_twilio_auth_token_here"
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Deduplication Guard
    # ──────────────────────────────────────────────────────────────────────────

    def is_duplicate_message(self, message_id: str) -> bool:
        """Checks if MessageSid has already been processed."""
        if not message_id:
            return False
        return message_id in self._processed_message_ids

    def mark_message_processed(self, message_id: str):
        """Records MessageSid in bounded cache to prevent duplicate processing."""
        if not message_id or message_id in self._processed_message_ids:
            return
        if len(self._processed_message_ids) >= self._max_cache_size:
            self._processed_message_ids.pop(0)
        self._processed_message_ids.append(message_id)

    # ──────────────────────────────────────────────────────────────────────────
    # Webhook Signature Verification (HMAC-SHA1)
    # ──────────────────────────────────────────────────────────────────────────

    def compute_signature(self, url: str, params: Dict[str, str], auth_token: Optional[str] = None) -> str:
        """
        Computes the expected Twilio X-Twilio-Signature for a given URL and POST parameters.
        Official Twilio Algorithm:
        1. Take the full URL (e.g. https://xxx.ngrok-free.app/twilio/webhook).
        2. Sort POST parameters alphabetically by key.
        3. Append each key and its value to the URL string (url + key1 + val1 + key2 + val2...).
        4. Compute HMAC-SHA1 using Twilio Auth Token.
        5. Base64 encode the digest.
        """
        token = auth_token or self.auth_token
        if not token:
            return ""

        # Build data string: URL + sorted key-value pairs
        s = url
        for key in sorted(params.keys()):
            s += key + str(params[key])

        computed_hmac = hmac.new(
            token.encode("utf-8"),
            s.encode("utf-8"),
            hashlib.sha1
        ).digest()

        return base64.b64encode(computed_hmac).decode("utf-8")

    def verify_signature(
        self,
        url: str,
        params: Dict[str, str],
        signature_header: Optional[str],
        auth_token: Optional[str] = None,
        candidate_urls: Optional[List[str]] = None
    ) -> bool:
        """
        Validates Twilio webhook signature from the X-Twilio-Signature header.
        - If auth_token is unconfigured: allows locally for development/offline testing.
        - If signature header is missing when token is configured: rejects.
        - Supports candidate URLs (e.g., behind ngrok or reverse proxies).
        """
        token = self.auth_token if auth_token is None else auth_token

        # Dev-friendly fallback: allow if auth token is not set
        if not token or token == "your_twilio_auth_token_here":
            logger.info("TWILIO_AUTH_TOKEN not configured; bypassing Twilio signature verification for local testing.")
            return True

        if not signature_header:
            logger.warning("Missing X-Twilio-Signature header while TWILIO_AUTH_TOKEN is configured.")
            return False

        # Build list of URLs to try (configured URL, incoming URL, candidate URLs)
        urls_to_try = [url]
        if self.configured_webhook_url and self.configured_webhook_url not in urls_to_try:
            urls_to_try.append(self.configured_webhook_url)
        if candidate_urls:
            for cu in candidate_urls:
                if cu and cu not in urls_to_try:
                    urls_to_try.append(cu)

        sig_clean = signature_header.strip()
        for test_url in urls_to_try:
            expected_sig = self.compute_signature(test_url, params, auth_token=token)
            if hmac.compare_digest(expected_sig, sig_clean):
                return True

        logger.warning("Twilio signature verification failed. Header did not match computed signature.")
        return False

    # ──────────────────────────────────────────────────────────────────────────
    # Inbound Webhook Payload Parsing
    # ──────────────────────────────────────────────────────────────────────────

    def parse_incoming_webhook(self, form_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parses Twilio WhatsApp incoming webhook form data (application/x-www-form-urlencoded).
        Returns a normalized dictionary.
        """
        if not form_data:
            return None

        # Helper to extract scalar values if form_data contains lists
        def get_val(key: str, default: str = "") -> str:
            v = form_data.get(key, default)
            if isinstance(v, list):
                return v[0] if v else default
            return str(v) if v is not None else default

        from_raw = get_val("From", "")
        # Twilio sends phone as "whatsapp:+91XXXXXXXXXX"
        sender_phone = from_raw.replace("whatsapp:", "").strip()
        body = get_val("Body", "").strip()
        message_sid = get_val("MessageSid", "")
        profile_name = get_val("ProfileName", "")
        num_media = int(get_val("NumMedia", "0") or "0")

        # Media parsing (e.g. voice notes or images)
        media_url = get_val("MediaUrl0", "") if num_media > 0 else None
        media_content_type = get_val("MediaContentType0", "") if num_media > 0 else None

        msg_type = "audio" if (media_content_type and "audio" in media_content_type) else ("text" if body else "other")

        return {
            "message_id": message_sid,
            "sender_phone": sender_phone,
            "sender_raw": from_raw,
            "profile_name": profile_name,
            "type": msg_type,
            "content": body,
            "num_media": num_media,
            "media_url": media_url,
            "media_content_type": media_content_type
        }

    # ──────────────────────────────────────────────────────────────────────────
    # TwiML Response Generation
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def generate_twiml_response(reply_text: str) -> str:
        """
        Wraps response text into valid Twilio TwiML XML:
        <?xml version="1.0" encoding="UTF-8"?>
        <Response>
            <Message><![CDATA[...]]></Message>
        </Response>
        """
        # Escape any CDATA closing delimiter inside the text
        safe_text = (reply_text or "").replace("]]>", "]]]]><![CDATA[>")
        twiml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<Response>\n'
            f'    <Message><![CDATA[{safe_text}]]></Message>\n'
            '</Response>'
        )
        return twiml

    # ──────────────────────────────────────────────────────────────────────────
    # Reply Formatting (Multilingual AgriVoice Standard)
    # ──────────────────────────────────────────────────────────────────────────

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

    # ──────────────────────────────────────────────────────────────────────────
    # Inbound Message Processing Pipeline
    # ──────────────────────────────────────────────────────────────────────────

    def process_incoming_message(
        self,
        parsed_message: Dict[str, Any],
        assistant: Any
    ) -> Dict[str, Any]:
        """
        Processes parsed Twilio message through the shared VoiceAgriculturalAssistant backend.
        Returns a dictionary containing:
          - reply_text: raw text response
          - twiml: valid TwiML XML string
          - status: status code
        """
        sender_phone = parsed_message.get("sender_phone", "")
        msg_type = parsed_message.get("type", "text")
        message_id = parsed_message.get("message_id")

        # Anonymize sender phone number for logging and telemetry
        phone_hash = self.privacy_manager.anonymize_user_id(sender_phone)

        # 1. Deduplication check
        if message_id and self.is_duplicate_message(message_id):
            logger.info(f"Duplicate Twilio delivery ignored for message_id={message_id}")
            empty_twiml = '<?xml version="1.0" encoding="UTF-8"?>\n<Response></Response>'
            return {
                "status": "duplicate_ignored",
                "message_id": message_id,
                "phone_hash": phone_hash,
                "twiml": empty_twiml,
                "reply_text": ""
            }

        if message_id:
            self.mark_message_processed(message_id)

        # 2. Text message handling
        if msg_type == "text":
            query = parsed_message.get("content", "")

            # WhatsApp language selection commands
            language_commands = {
                "1": ("mr", "Marathi"),
                "2": ("hi", "Hindi"),
                "3": ("en", "English"),
                "marathi": ("mr", "Marathi"),
                "hindi": ("hi", "Hindi"),
                "english": ("en", "English"),
            }

            command = query.strip().lower()

            # Show welcome menu when language is not selected,
            # or when the farmer requests to change language.
            if command in (
                "hi",
                "hello",
                "hey",
                "start",
                "language",
                "menu",
                "change language",
            ):
                reply_text = (
                    "Welcome to AgriVoice!\n\n"
                    "Please select your preferred language:\n\n"
                    "1. Marathi\n"
                    "2. Hindi\n"
                    "3. English\n\n"
                    "Reply with 1, 2, or 3."
                )

                return {
                    "status": "success",
                    "type": "text",
                    "message_id": message_id,
                    "phone_hash": phone_hash,
                    "reply_text": reply_text,
                    "twiml": self.generate_twiml_response(reply_text),
                }

            if command in language_commands:
                language_code, language_name = language_commands[command]
                self._language_preferences[phone_hash] = language_code

                reply_text = (
                    f"Language set to {language_name}. "
                    "You can now send your voice question."
                )

                return {
                    "status": "success",
                    "type": "text",
                    "message_id": message_id,
                    "phone_hash": phone_hash,
                    "detected_language": language_code,
                    "reply_text": reply_text,
                    "twiml": self.generate_twiml_response(reply_text),
                }

            logger.info(f"Processing Twilio text query from user [{phone_hash[:8]}...]")

            # Process through unified AgriVoice backend (same as Streamlit and Meta WhatsApp)
            assistant_result = assistant.process_text_query(
                query=query,
                user_phone_or_id=sender_phone
            )

            reply_text = self.format_whatsapp_reply(assistant_result)
            twiml = self.generate_twiml_response(reply_text)

            return {
                "status": "success",
                "type": "text",
                "message_id": message_id,
                "phone_hash": phone_hash,
                "detected_language": assistant_result.get("detected_language", "hi"),
                "reply_text": reply_text,
                "twiml": twiml,
                "assistant_result": assistant_result
            }

        # 3. Audio / Voice Note handling
        elif msg_type == "audio":
            from src.channel.whatsapp_voice_pipeline import process_whatsapp_voice

            media_url = parsed_message.get("media_url")

            try:
                result = process_whatsapp_voice(
                    media_url=media_url,
                    sender_phone=sender_phone,
                    assistant=assistant,
                    twilio_client=self,
                    language_hint=self._language_preferences.get(phone_hash)
                )

                reply_text = result.get(
                    "text_response",
                    "Please repeat your question."
                )

                # Send text and generated MP3 together
                from xml.etree.ElementTree import Element, SubElement, tostring
                from urllib.parse import urlparse
                from src.channel.whatsapp_media import register_audio

                twiml = self.generate_twiml_response(reply_text)
                audio_path = result.get("audio_response_path")
                public_url = self.public_base_url

                if audio_path and public_url:
                    parsed_url = urlparse(public_url)

                    if (
                        parsed_url.scheme == "https"
                        and parsed_url.hostname
                        and not parsed_url.username
                        and not parsed_url.password
                        and not parsed_url.query
                        and not parsed_url.fragment
                        and parsed_url.path in ("", "/")
                    ):
                        try:
                            token = register_audio(audio_path)
                            media_url = (
                                public_url.rstrip("/")
                                + "/media/" + token + ".mp3"
                            )

                            response = Element("Response")
                            message = SubElement(response, "Message")
                            SubElement(message, "Body").text = reply_text
                            SubElement(message, "Media").text = media_url

                            twiml = tostring(
                                response,
                                encoding="unicode"
                            )
                            logger.info(
                                "WhatsApp text and audio reply prepared"
                            )
                        except (OSError, ValueError):
                            logger.exception(
                                "Audio attachment failed; sending text only"
                            )
                    else:
                        logger.warning(
                            "Invalid public HTTPS base URL; sending text only"
                        )
                else:
                    logger.warning(
                        "Audio path or public URL missing; sending text only"
                    )

                return {
                    "status": "success",
                    "type": "audio",
                    "message_id": message_id,
                    "phone_hash": phone_hash,
                    "detected_language": result.get(
                        "detected_language", "hi"
                    ),
                    "transcript": result.get("transcript", ""),
                    "reply_text": reply_text,
                    "audio_response_path": result.get(
                        "audio_response_path"
                    ),
                    "twiml": twiml
                }

            except Exception:
                logger.exception("WhatsApp voice processing failed")

                reply_text = (
                    "Sorry, I could not process your voice message. "
                    "Please try again or send your question as text."
                )

                return {
                    "status": "audio_error",
                    "type": "audio",
                    "message_id": message_id,
                    "phone_hash": phone_hash,
                    "reply_text": reply_text,
                    "twiml": self.generate_twiml_response(reply_text)
                }

        # 4. Unknown or other message types
        else:
            default_msg = (
                "🌾 *कृषि वाणी (AgriVoice Assistant)*\n"
                "─────────────────────────\n"
                "कृपया आपला कृषी प्रश्न मजकूर (text) स्वरूपात पाठवा (उदा. 'पुणे मंडी में प्याज का भाव क्या है?').\n\n"
                "📞 *किसान हेल्पलाइन:* 1800-180-1551 (टोल-फ्री)"
            )
            twiml = self.generate_twiml_response(default_msg)
            return {
                "status": "unsupported_media",
                "message_id": message_id,
                "phone_hash": phone_hash,
                "reply_text": default_msg,
                "twiml": twiml
            }

    # ──────────────────────────────────────────────────────────────────────────
    # Optional Proactive Outbound REST Dispatch
    # ──────────────────────────────────────────────────────────────────────────

    def send_message(self, to_phone: str, body: str) -> Dict[str, Any]:
        """
        Dispatches an outbound WhatsApp message via Twilio REST API.
        Used for proactive alerts or secondary dispatch outside webhook responses.
        In unconfigured/offline mode, returns structured credential_gated status without network call.
        """
        if not self.is_configured:
            return {
                "status": "credential_gated",
                "message": "TWILIO_ACCOUNT_SID or TWILIO_AUTH_TOKEN not configured.",
                "to": to_phone
            }

        # Ensure whatsapp: prefix
        recipient = to_phone if to_phone.startswith("whatsapp:") else f"whatsapp:{to_phone}"
        sender = self.from_number if self.from_number.startswith("whatsapp:") else f"whatsapp:{self.from_number}"

        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"
        data = {
            "From": sender,
            "To": recipient,
            "Body": body
        }

        try:
            resp = requests.post(
                url,
                data=data,
                auth=(self.account_sid, self.auth_token),
                timeout=10
            )
            if resp.status_code in [200, 201]:
                return {"status": "sent", "response": resp.json()}
            else:
                logger.error(f"Twilio API error {resp.status_code}: {resp.text}")
                return {"status": "api_error", "code": resp.status_code, "error": resp.text}
        except requests.exceptions.Timeout:
            logger.error("Twilio API request timed out.")
            return {"status": "timeout", "error": "Request timed out"}
        except Exception as e:
            logger.error(f"Twilio network error: {e}")
            return {"status": "network_error", "error": str(e)}
