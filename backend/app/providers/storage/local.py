import os
import re
from pathlib import Path

from app.providers.storage.base import ObjectNotFound, ObjectStorageProvider, StorageError

_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9/_.-]{0,480}$")


class LocalStorageProvider(ObjectStorageProvider):
    """Stores objects as files under a root directory (development only)."""

    name = "local"

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        if not _KEY_RE.match(key) or ".." in key.split("/"):
            raise StorageError("invalid storage key")
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root):
            raise StorageError("storage key escapes root")
        return path

    def put(self, key: str, data: bytes, content_type: str) -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".part")
        with open(tmp, "xb") as fh:
            fh.write(data)
        os.replace(tmp, path)
        return f"local:{key}"

    def _key(self, reference: str) -> str:
        prefix = "local:"
        if not reference.startswith(prefix):
            raise StorageError("reference not owned by local provider")
        return reference[len(prefix):]

    def get(self, reference: str) -> bytes:
        path = self._path(self._key(reference))
        if not path.is_file():
            raise ObjectNotFound(reference)
        return path.read_bytes()

    def delete(self, reference: str) -> None:
        path = self._path(self._key(reference))
        path.unlink(missing_ok=True)

    def exists(self, reference: str) -> bool:
        return self._path(self._key(reference)).is_file()
