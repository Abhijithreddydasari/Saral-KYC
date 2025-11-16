"""Blob storage abstraction."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import BinaryIO

from fastapi import UploadFile

from app.core.config import get_settings

settings = get_settings()


class LocalBlobStorage:
    """Simple file-system backed storage."""

    def __init__(self, base_path: Path | None = None) -> None:
        self.base_path = (base_path or settings.storage_dir)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def save_upload(self, upload: UploadFile, destination: str) -> Path:
        dest_path = self.base_path / destination
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        with dest_path.open("wb") as buffer:
            shutil.copyfileobj(upload.file, buffer)

        return dest_path

    def save_bytes(self, data: bytes, destination: str) -> Path:
        dest_path = self.base_path / destination
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(data)
        return dest_path

    def open(self, destination: str, mode: str = "rb") -> BinaryIO:
        dest_path = self.base_path / destination
        return dest_path.open(mode)

