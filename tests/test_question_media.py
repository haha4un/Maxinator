from uuid import uuid4

import pytest
from maxapi.enums.upload_type import UploadType

from maxinator_bot.app.bot.question_media import (
    _image_extension,
    build_question_attachments,
    google_drive_download_url,
)
from maxinator_bot.app.domain.models import QuestionProgress


@pytest.mark.parametrize(
    ("source", "file_id"),
    [
        ("https://drive.google.com/file/d/abc_123/view?usp=sharing", "abc_123"),
        ("https://drive.google.com/open?id=xyz-789", "xyz-789"),
    ],
)
def test_google_drive_download_url(source: str, file_id: str) -> None:
    assert google_drive_download_url(source) == (
        f"https://drive.usercontent.google.com/download?id={file_id}&export=download"
    )


def test_non_drive_image_url_is_rejected() -> None:
    with pytest.raises(ValueError, match="Google Drive"):
        google_drive_download_url("https://example.com/question.png")


@pytest.mark.parametrize(
    ("data", "extension"),
    [
        (b"\xff\xd8\xffrest", "jpg"),
        (b"\x89PNG\r\n\x1a\nrest", "png"),
        (b"GIF89arest", "gif"),
        (b"RIFF\x00\x00\x00\x00WEBPrest", "webp"),
        (b"<html>Google Drive access denied</html>", None),
    ],
)
def test_image_extension_uses_file_contents(data: bytes, extension: str | None) -> None:
    assert _image_extension(data) == extension


async def test_build_question_attachments_downloads_octet_stream(monkeypatch) -> None:
    image = b"\x89PNG\r\n\x1a\nrest"

    class Response:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        def raise_for_status(self) -> None:
            return None

        async def read(self) -> bytes:
            return image

    class Session:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        def get(self, _url: str) -> Response:
            return Response()

    monkeypatch.setattr("maxinator_bot.app.bot.question_media.ClientSession", Session)
    progress = QuestionProgress(
        attempt_id=uuid4(),
        attempt_question_id=uuid4(),
        question_text="Question",
        image_url="https://drive.google.com/file/d/abc/view",
        current_number=1,
        total=1,
    )

    attachments = await build_question_attachments(progress)

    assert len(attachments) == 2
    assert attachments[0].buffer == image
    assert attachments[0].filename == "question-image.png"
    assert attachments[0].type is UploadType.IMAGE
