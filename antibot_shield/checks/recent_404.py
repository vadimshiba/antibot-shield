from __future__ import annotations

from antibot_shield.config import ShieldSettings
from antibot_shield.models import CheckResult, RequestContext
from antibot_shield.storage.base import Storage


class Recent404Check:
    name = "recent_404"

    async def evaluate(self, ctx: RequestContext, storage: Storage, settings: ShieldSettings) -> CheckResult:
        key = f"abs:resp404:{ctx.client_id}:300"
        recent = await storage.lrange(key, 0, -1)
        count = sum(1 for x in recent if x == "404")

        score = 0
        tags: list[str] = []

        if count > settings.max_404_per_5min:
            score += 35
            tags.append("too_many_404")

        return CheckResult(score=score, tags=tags, meta={"recent_404": count})
