import pytest

from maxinator_bot.app.bot.question_media import google_drive_download_url


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
