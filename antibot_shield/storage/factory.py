from __future__ import annotations

from antibot_shield.config import ShieldSettings
from antibot_shield.storage.local import LocalStorage
from antibot_shield.storage.redis_store import RedisStorage


def build_storage(settings: ShieldSettings):
    if settings.redis_url:
        return RedisStorage(settings.redis_url)
    return LocalStorage()
