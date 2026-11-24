import tempfile
from pathlib import Path

from src.channel.twilio_audio import download_twilio_audio
from src.asr.whatsapp_audio import convert_to_wav


def process_whatsapp_voice(
    media_url,
    sender_phone,
    assistant,
    twilio_client,
    language_hint=None
):
    """Process a Twilio WhatsApp voice note."""

    with tempfile.TemporaryDirectory(
        prefix="agrivoice_"
    ) as temp_dir:

        temp_dir = Path(temp_dir)

        original_audio = temp_dir / "incoming_audio"
        wav_audio = temp_dir / "incoming_audio.wav"

        # Step 1: Download voice note
        download_twilio_audio(
            media_url=media_url,
            account_sid=twilio_client.account_sid,
            auth_token=twilio_client.auth_token,
            output_path=original_audio
        )

        # Step 2: Convert to WAV
        convert_to_wav(
            original_audio,
            wav_audio
        )

        # Step 3: Speech recognition and answer
        result = assistant.process_voice_query(
            audio_path=str(wav_audio),
            user_phone_or_id=sender_phone,
            language_hint=language_hint
        )

        return result
