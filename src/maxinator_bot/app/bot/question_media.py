from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

from aiohttp import ClientSession, ClientTimeout
from maxapi.enums.upload_type import UploadType
from maxapi.types.input_media import InputMediaBuffer

from maxinator_bot.app.bot.keyboards import build_answer_keyboard
from maxinator_bot.app.domain.models import QuestionProgress


_DRIVE_FILE_RE = re.compile(r"/file/d/([a-zA-Z0-9_-]+)")
_MAX_IMAGE_BYTES = 15 * 1024 * 1024


def google_drive_download_url(url: str) -> str:
    """Convert a public Google Drive sharing URL to a download URL."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Image URL must use HTTP or HTTPS")
    if parsed.hostname not in {"drive.google.com", "docs.google.com"}:
        raise ValueError("Image URL must point to Google Drive")
    match = _DRIVE_FILE_RE.search(parsed.path)
    file_id = match.group(1) if match else parse_qs(parsed.query).get("id", [None])[0]
    if not file_id:
        raise ValueError("Google Drive file ID was not found")
    return f"https://drive.usercontent.google.com/download?id={file_id}&export=download"


async def build_question_attachments(progress: QuestionProgress) -> list[object]:
    attachments: list[object] = []
    if progress.image_url:
        try:
            image_url = google_drive_download_url(progress.image_url)
            timeout = ClientTimeout(total=20)
            async with ClientSession(timeout=timeout) as session:
                async with session.get(image_url) as response:
                    response.raise_for_status()
                    content_type = response.headers.get("Content-Type", "")
                    data = await response.read()
            if not content_type.startswith("image/") or len(data) > _MAX_IMAGE_BYTES:
                raise ValueError("URL did not return a supported image")
            attachments.append(
                InputMediaBuffer(data, filename="question-image", type=UploadType.IMAGE),
            )
        except Exception:
            # A broken external image must not prevent the test from continuing.
            pass
    attachments.append(build_answer_keyboard(progress.attempt_question_id))
    return attachments
