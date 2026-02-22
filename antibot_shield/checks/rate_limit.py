from __future__ import annotations

from antibot_shield.config import ShieldSettings
from antibot_shield.models import CheckResult, RequestContext
from antibot_shield.storage.base import Storage


class RateLimitCheck:
    name = "rate_limit"

    async def evaluate(self, ctx: RequestContext, storage: Storage, settings: ShieldSettings) -> CheckResult:
        minute_key = f"abs:rl:ip:{ctx.client_id}:60"
        count = await storage.incr(minute_key, ttl_sec=60)

        score = 0
        tags: list[str] = []
        hard = False

        if count > settings.requests_per_minute:
            tags.append("rpm_exceeded")
            score += 45

        if count > settings.requests_per_minute * 2:
            tags.append("rpm_massive")
            hard = True
            score += 40

        return CheckResult(score=score, hard_block=hard, tags=tags, meta={"rpm": count})
