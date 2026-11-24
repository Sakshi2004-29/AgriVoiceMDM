"""
WhatsApp Business Cloud API Webhook Server (Module 1).
Exposes the official Meta Webhook endpoints:
  - GET  /webhook : Webhook verification handshake (hub.mode, hub.verify_token, hub.challenge)
  - POST /webhook : Inbound messages handler with HMAC-SHA256 signature verification
  - GET  /health  : Service health check & configuration status

Built using Python standard library http.server for zero-dependency local and production deployment.
"""
import sys
import json
import logging
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Optional

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.channel.whatsapp_client import WhatsAppCloudClient
from src.channel.twilio_client import TwilioWhatsAppClient
from src.core.voice_assistant import VoiceAgriculturalAssistant

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("WhatsAppWebhookServer")

# Shared singletons
_assistant: Optional[VoiceAgriculturalAssistant] = None
_whatsapp_client: Optional[WhatsAppCloudClient] = None
_twilio_client: Optional[TwilioWhatsAppClient] = None


def get_assistant() -> VoiceAgriculturalAssistant:
    global _assistant
    if _assistant is None:
        _assistant = VoiceAgriculturalAssistant(data_dir="data")
    return _assistant


def get_whatsapp_client() -> WhatsAppCloudClient:
    global _whatsapp_client
    if _whatsapp_client is None:
        _whatsapp_client = WhatsAppCloudClient(data_dir="data")
    return _whatsapp_client


def get_twilio_client() -> TwilioWhatsAppClient:
    global _twilio_client
    if _twilio_client is None:
        _twilio_client = TwilioWhatsAppClient(data_dir="data")
    return _twilio_client


class WhatsAppWebhookHandler(BaseHTTPRequestHandler):
    """
    HTTP Request Handler conforming to Meta WhatsApp Business API webhook specification.
    Supports HMAC-SHA256 signature verification and duplicate delivery handling.
    """

    def do_GET(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        query = parse_qs(parsed_url.query)

        # 1. Health check endpoint
        if path in ["/", "/health"]:
            meta_client = get_whatsapp_client()
            twilio_client = get_twilio_client()
            health_data = {
                "status": "healthy",
                "service": "AgriVoice WhatsApp Multi-Channel Webhook Server",
                "channels": {
                    "meta_whatsapp_cloud": {
                        "configured": meta_client.is_configured,
                        "phone_number_id": meta_client.phone_number_id[:4] + "***" if meta_client.phone_number_id else "NOT_SET",
                        "verify_token_set": bool(meta_client.verify_token),
                        "app_secret_set": bool(meta_client.app_secret),
                        "graph_api_version": meta_client.api_version,
                        "webhook_path": "/webhook"
                    },
                    "twilio_whatsapp_sandbox": {
                        "configured": twilio_client.is_configured,
                        "account_sid": twilio_client.account_sid[:6] + "***" if twilio_client.account_sid else "NOT_SET",
                        "auth_token_set": bool(twilio_client.auth_token),
                        "from_number": twilio_client.from_number,
                        "webhook_path": "/twilio/webhook"
                    }
                }
            }
            self._send_json_response(200, health_data)
            return

        # 2. Twilio Webhook diagnostic endpoint (GET /twilio/webhook)
        if path in ["/twilio/webhook", "/whatsapp/twilio"]:
            twilio_client = get_twilio_client()
            diag = {
                "status": "active",
                "service": "AgriVoice Twilio WhatsApp Sandbox Endpoint",
                "configured": twilio_client.is_configured,
                "account_sid": twilio_client.account_sid[:6] + "***" if twilio_client.account_sid else "NOT_SET",
                "auth_token_set": bool(twilio_client.auth_token),
                "from_number": twilio_client.from_number,
                "instructions": (
                    "In Twilio Console -> Messaging -> Try it out -> Send a WhatsApp message -> Sandbox settings: "
                    "Set 'WHEN A MESSAGE COMES IN' to this public HTTPS URL with HTTP POST."
                )
            }
            self._send_json_response(200, diag)
            return

        # 3. Meta Webhook Verification endpoint (GET /webhook)
        if path == "/webhook":
            mode = query.get("hub.mode", [""])[0]
            token = query.get("hub.verify_token", [""])[0]
            challenge = query.get("hub.challenge", [""])[0]

            client = get_whatsapp_client()
            verified_challenge = client.verify_webhook(mode, token, challenge)

            if verified_challenge is not None:
                logger.info(f"WhatsApp webhook successfully verified with challenge: {verified_challenge[:10]}...")
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(verified_challenge.encode("utf-8"))
            else:
                logger.warning(f"WhatsApp webhook verification failed for mode={mode}")
                self.send_response(403)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"Forbidden: Verification token mismatch")
            return

        # Serve temporary WhatsApp voice replies
        if path.startswith("/media/"):
            from src.channel.whatsapp_media import get_audio

            filename = path.removeprefix("/media/")

            if not filename.endswith(".mp3"):
                self.send_error(404)
                return

            token = filename[:-4]
            audio_path = get_audio(token)

            if audio_path is None:
                self.send_error(404)
                return

            audio_data = audio_path.read_bytes()

            self.send_response(200)
            self.send_header("Content-Type", "audio/mpeg")
            self.send_header("Content-Length", str(len(audio_data)))
            self.send_header("Cache-Control", "private, max-age=300")
            self.end_headers()
            self.wfile.write(audio_data)
            return

        # Not found
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        # ─── Twilio WhatsApp Sandbox Webhook (POST /twilio/webhook) ───────────
        if path in ["/twilio/webhook", "/whatsapp/twilio"]:
            content_length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(content_length)

            twilio_client = get_twilio_client()

            # Parse application/x-www-form-urlencoded
            decoded_body = raw_body.decode("utf-8", errors="replace")
            parsed_qs = parse_qs(decoded_body, keep_blank_values=True)
            # Flatten single-element lists to plain strings
            form_params = {k: v[0] for k, v in parsed_qs.items()}

            # Reconstruct request URL candidates for signature verification
            host_header = self.headers.get("Host", "localhost")
            proto_header = self.headers.get("X-Forwarded-Proto", "https")
            reconstructed_url = f"{proto_header}://{host_header}{path}"
            http_local_url = f"http://{host_header}{path}"
            candidate_urls = [reconstructed_url, http_local_url]

            # Security: Validate Twilio HMAC-SHA1 signature if auth token is set
            signature_header = self.headers.get("X-Twilio-Signature")
            if twilio_client.auth_token:
                is_valid_sig = twilio_client.verify_signature(
                    url=reconstructed_url,
                    params=form_params,
                    signature_header=signature_header,
                    candidate_urls=candidate_urls
                )
                if not is_valid_sig:
                    logger.warning("Rejected Twilio webhook POST: Invalid X-Twilio-Signature")
                    error_twiml = '<?xml version="1.0" encoding="UTF-8"?>\n<Response><Message>Unauthorized: Invalid Twilio Signature</Message></Response>'
                    self._send_xml_response(401, error_twiml)
                    return

            # Extract message details
            parsed = twilio_client.parse_incoming_webhook(form_params)
            if not parsed or (not parsed.get("content") and not parsed.get("media_url")):
                logger.info("Empty message received from Twilio webhook.")
                empty_twiml = '<?xml version="1.0" encoding="UTF-8"?>\n<Response></Response>'
                self._send_xml_response(200, empty_twiml)
                return

            logger.info(f"Processing Twilio message type={parsed.get('type')} from sender={parsed.get('sender_phone')[:6]}***")
            assistant = get_assistant()
            result = twilio_client.process_incoming_message(parsed, assistant)

            # Return valid TwiML with 200 OK
            self._send_xml_response(200, result["twiml"])
            return

        # ─── Meta WhatsApp Cloud API Webhook (POST /webhook) ──────────────────
        if path == "/webhook":
            content_length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(content_length)

            client = get_whatsapp_client()

            # Security: Validate Meta HMAC-SHA256 signature if App Secret is configured
            signature_header = self.headers.get("X-Hub-Signature-256")
            if client.app_secret:
                is_valid_sig = client.verify_signature(raw_body, signature_header)
                if not is_valid_sig:
                    logger.warning("Rejected webhook POST: Invalid X-Hub-Signature-256")
                    self._send_json_response(401, {
                        "status": "unauthorized",
                        "error": "Invalid webhook signature"
                    })
                    return

            try:
                payload = json.loads(raw_body.decode("utf-8"))
            except Exception as e:
                logger.error(f"Malformed JSON in WhatsApp webhook: {e}")
                self._send_json_response(400, {"status": "error", "message": "Invalid JSON"})
                return

            assistant = get_assistant()
            parsed = client.parse_incoming_webhook(payload)

            if not parsed:
                # Meta sends delivery receipts, read statuses, etc. Must return 200 OK
                self._send_json_response(200, {"status": "event_received_no_message"})
                return

            logger.info(f"Processing incoming WhatsApp {parsed.get('type')} message from {parsed.get('sender_phone')}")

            # Process message through shared backend (with deduplication check)
            result = client.process_incoming_message(parsed, assistant)

            # Meta requires immediate 200 OK acknowledgment
            self._send_json_response(200, result)
            return

        self.send_response(404)
        self.end_headers()

    def _send_xml_response(self, status_code: int, xml_content: str):
        """Sends an XML response with proper Content-Type for TwiML."""
        self.send_response(status_code)
        self.send_header("Content-Type", "application/xml; charset=utf-8")
        self.end_headers()
        self.wfile.write(xml_content.encode("utf-8"))

    def _send_json_response(self, status_code: int, data: dict):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))

    def log_message(self, format, *args):
        # Override to use logger instead of stderr directly
        logger.debug("%s - - [%s] %s" % (self.address_string(), self.log_date_time_string(), format % args))


def run_server(port: int = 8000, host: str = "0.0.0.0"):
    """Starts the Multi-Channel WhatsApp Webhook server."""
    server_address = (host, port)
    httpd = HTTPServer(server_address, WhatsAppWebhookHandler)
    meta_client = get_whatsapp_client()
    twilio_client = get_twilio_client()
    logger.info(f"🌾 AgriVoice WhatsApp Webhook Server listening on {host}:{port}")
    logger.info(f"   ► Twilio WhatsApp Webhook: http://localhost:{port}/twilio/webhook (POST -> TwiML)")
    logger.info(f"   ► Meta WhatsApp Webhook  : http://localhost:{port}/webhook (GET/POST)")
    logger.info(f"   ► Health & Diagnostics   : http://localhost:{port}/health")
    logger.info(f"   Twilio Auth Check        : {'ENFORCED' if twilio_client.auth_token else 'OPTIONAL (TWILIO_AUTH_TOKEN not set)'}")
    logger.info(f"   Meta App Secret Check    : {'ENFORCED' if meta_client.app_secret else 'OPTIONAL (WHATSAPP_APP_SECRET not set)'}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server stopped by user.")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="AgriVoice WhatsApp Business Cloud API Webhook Server")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host address (default: 0.0.0.0)")
    args = parser.parse_args()
    run_server(port=args.port, host=args.host)
