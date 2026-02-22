from __future__ import annotations

from redis.asyncio import Redis


class RedisStorage:
    def __init__(self, redis_url: str) -> None:
        self.redis = Redis.from_url(redis_url, decode_responses=True)

    async def incr(self, key: str, ttl_sec: int) -> int:
        value = await self.redis.incr(key)
        if value == 1:
            await self.redis.expire(key, ttl_sec)
        return int(value)

    async def set(self, key: str, value: str, ttl_sec: int) -> None:
        await self.redis.set(key, value, ex=ttl_sec)

    async def get(self, key: str) -> str | None:
        return await self.redis.get(key)

    async def delete(self, key: str) -> None:
        await self.redis.delete(key)

    async def sadd(self, key: str, value: str, ttl_sec: int) -> int:
        await self.redis.sadd(key, value)
        await self.redis.expire(key, ttl_sec)
        size = await self.redis.scard(key)
        return int(size)

    async def scard(self, key: str) -> int:
        return int(await self.redis.scard(key))

    async def lpush_trim(self, key: str, value: str, max_len: int, ttl_sec: int) -> None:
        await self.redis.lpush(key, value)
        await self.redis.ltrim(key, 0, max_len - 1)
        await self.redis.expire(key, ttl_sec)

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        return [str(v) for v in await self.redis.lrange(key, start, end)]
