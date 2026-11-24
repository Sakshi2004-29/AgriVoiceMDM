from pathlib import Path
from urllib.parse import urlparse
import requests

def download_twilio_audio(
    media_url,
    account_sid,
    auth_token,
    output_path
):
    """Download an authenticated Twilio voice message."""

    parsed = urlparse(media_url)

    if (
        parsed.scheme != "https"
        or parsed.hostname not in {
            "api.twilio.com",
            "media.twiliocdn.com"
        }
        or parsed.username
        or parsed.password
        or parsed.port
    ):
        raise ValueError("Untrusted Twilio media URL")

    if not account_sid or not auth_token:
        raise ValueError("Twilio credentials are missing")

    output_path = Path(output_path)
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    max_bytes = 10 * 1024 * 1024
    total = 0

    with requests.get(
        media_url,
        auth=(account_sid, auth_token),
        stream=True,
        timeout=(10, 30),
        allow_redirects=False
    ) as response:
        response.raise_for_status()

        if response.is_redirect:
            from urllib.parse import urljoin

            redirect_url = urljoin(
                media_url,
                response.headers.get("Location", "")
            )

            redirect = urlparse(redirect_url)

            if (
                redirect.scheme != "https"
                or redirect.hostname not in {
                    "api.twilio.com",
                    "media.twiliocdn.com",
                    "mms.twiliocdn.com"
                }
                or redirect.username
                or redirect.password
                or redirect.port
            ):
                raise ValueError(f"Untrusted media redirect hostname: {redirect.hostname}")

            with requests.get(
                redirect_url,
                stream=True,
                timeout=(10, 30),
                allow_redirects=False
            ) as redirected_response:
                redirected_response.raise_for_status()

                if redirected_response.is_redirect:
                    raise ValueError("Multiple redirects not allowed")

                with output_path.open("wb") as file:
                    total = 0

                    for chunk in redirected_response.iter_content(
                        chunk_size=65536
                    ):
                        total += len(chunk)

                        if total > max_bytes:
                            raise ValueError(
                                "Voice message exceeds 10 MB"
                            )

                        file.write(chunk)

            return str(output_path)

        with output_path.open("wb") as file:
            for chunk in response.iter_content(
                chunk_size=65536
            ):
                total += len(chunk)

                if total > max_bytes:
                    raise ValueError(
                        "Voice message exceeds 10 MB"
                    )

                file.write(chunk)

    return str(output_path)
