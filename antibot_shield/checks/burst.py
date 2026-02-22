from __future__ import annotations

from antibot_shield.config import ShieldSettings
from antibot_shield.models import CheckResult, RequestContext
from antibot_shield.storage.base import Storage


class BurstCheck:
    name = "burst"

    async def evaluate(self, ctx: RequestContext, storage: Storage, settings: ShieldSettings) -> CheckResult:
        burst_key = f"abs:burst:ip:{ctx.client_id}:{settings.burst_window_sec}"
        count = await storage.incr(burst_key, ttl_sec=settings.burst_window_sec)

        score = 0
        tags: list[str] = []
        hard = False

        if count > settings.burst_requests:
            tags.append("burst_detected")
            score += 35

        if count > settings.burst_requests * 2:
            tags.append("burst_extreme")
            score += 50
            hard = True

        return CheckResult(score=score, hard_block=hard, tags=tags, meta={"burst": count})
