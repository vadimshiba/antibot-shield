from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass


@dataclass
class ExpValue:
    value: object
    expires_at: float


class LocalStorage:
    def __init__(self) -> None:
        self._kv: dict[str, ExpValue] = {}
        self._sets: dict[str, ExpValue] = {}
        self._lists: dict[str, ExpValue] = {}
        self._counters: dict[str, ExpValue] = {}

    def _expired(self, exp_value: ExpValue | None) -> bool:
        if not exp_value:
            return True
        return exp_value.expires_at <= time.time()

    def _cleanup(self, store: dict[str, ExpValue], key: str) -> None:
        ev = store.get(key)
        if ev and self._expired(ev):
            store.pop(key, None)

    async def incr(self, key: str, ttl_sec: int) -> int:
        self._cleanup(self._counters, key)
        ev = self._counters.get(key)
        if not ev:
            ev = ExpValue(0, time.time() + ttl_sec)
        ev.value = int(ev.value) + 1
        self._counters[key] = ev
        return int(ev.value)

    async def set(self, key: str, value: str, ttl_sec: int) -> None:
        self._kv[key] = ExpValue(value, time.time() + ttl_sec)

    async def get(self, key: str) -> str | None:
        self._cleanup(self._kv, key)
        ev = self._kv.get(key)
        return str(ev.value) if ev else None

    async def delete(self, key: str) -> None:
        self._kv.pop(key, None)
        self._sets.pop(key, None)
        self._lists.pop(key, None)
        self._counters.pop(key, None)

    async def sadd(self, key: str, value: str, ttl_sec: int) -> int:
        self._cleanup(self._sets, key)
        ev = self._sets.get(key)
        if not ev:
            ev = ExpValue(set(), time.time() + ttl_sec)
        current = ev.value
        if not isinstance(current, set):
            current = set()
        current.add(value)
        ev.value = current
        self._sets[key] = ev
        return len(current)

    async def scard(self, key: str) -> int:
        self._cleanup(self._sets, key)
        ev = self._sets.get(key)
        if not ev or not isinstance(ev.value, set):
            return 0
        return len(ev.value)

    async def lpush_trim(self, key: str, value: str, max_len: int, ttl_sec: int) -> None:
        self._cleanup(self._lists, key)
        ev = self._lists.get(key)
        if not ev:
            ev = ExpValue(deque(), time.time() + ttl_sec)
        current = ev.value
        if not isinstance(current, deque):
            current = deque()
        current.appendleft(value)
        while len(current) > max_len:
            current.pop()
        ev.value = current
        self._lists[key] = ev

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        self._cleanup(self._lists, key)
        ev = self._lists.get(key)
        if not ev or not isinstance(ev.value, deque):
            return []
        data = list(ev.value)
        if end == -1:
            return [str(x) for x in data[start:]]
        return [str(x) for x in data[start : end + 1]]
