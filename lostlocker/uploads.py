"""Photo uploads: validate, re-encode as JPEG, store under a random name."""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from PIL import Image, ImageOps

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_DIMENSION = 1600
_STORED_NAME = re.compile(r"^[0-9a-f]{32}\.jpg$")


class UploadError(ValueError):
    """The uploaded file can't be used. The message is safe to show to the user."""


def is_stored_name(name: str) -> bool:
    return bool(_STORED_NAME.match(name))


def save_image(file_storage, folder: str) -> str | None:
    """Validate and store an uploaded photo. Returns the stored filename, or None if no file."""
    if file_storage is None or not file_storage.filename:
        return None
    stream = file_storage.stream
    try:
        stream.seek(0)
        with Image.open(stream) as probe:
            image_format = probe.format
            probe.verify()  # catches truncated/corrupt files
        if image_format not in ALLOWED_FORMATS:
            raise UploadError("Please upload a JPG, PNG or WebP photo.")
        stream.seek(0)
        with Image.open(stream) as img:
            img = ImageOps.exif_transpose(img)  # honour phone rotation, then drop EXIF
            img = img.convert("RGB")
            img.thumbnail((MAX_DIMENSION, MAX_DIMENSION))
            Path(folder).mkdir(parents=True, exist_ok=True)
            name = f"{uuid.uuid4().hex}.jpg"
            img.save(Path(folder) / name, format="JPEG", quality=85)
    except UploadError:
        raise
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError) as exc:
        raise UploadError("That file doesn't look like a valid photo.") from exc
    return name


def delete_image(folder: str, name: str | None) -> None:
    if name and is_stored_name(name):
        (Path(folder) / name).unlink(missing_ok=True)
