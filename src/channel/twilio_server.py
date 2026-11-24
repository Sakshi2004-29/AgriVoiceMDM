"""
Dedicated Twilio WhatsApp Sandbox Webhook Server Entry Point.
Allows running:
    python -m src.channel.twilio_server --port 8000
"""
import sys
import argparse
from pathlib import Path

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.channel.whatsapp_server import run_server


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AgriVoice Twilio WhatsApp Sandbox Webhook Server")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host address (default: 0.0.0.0)")
    args = parser.parse_args()
    print("🌾 Starting AgriVoice Twilio WhatsApp Webhook Server...")
    run_server(port=args.port, host=args.host)
