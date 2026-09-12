from functools import lru_cache

from app.core.config import get_settings
from app.providers.storage.base import ObjectNotFound, ObjectStorageProvider, StorageError
from app.providers.storage.local import LocalStorageProvider


@lru_cache
def get_storage() -> ObjectStorageProvider:
    settings = get_settings()
    if settings.storage_provider == "local":
        return LocalStorageProvider(settings.storage_root_path)
    raise ValueError(f"Unsupported STORAGE_PROVIDER={settings.storage_provider!r} (only 'local' in Phase 1)")


__all__ = ["LocalStorageProvider", "ObjectNotFound", "ObjectStorageProvider", "StorageError", "get_storage"]
