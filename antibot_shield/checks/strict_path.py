from __future__ import annotations

from antibot_shield.config import ShieldSettings
from antibot_shield.models import CheckResult, RequestContext
from antibot_shield.storage.base import Storage


class StrictPathCheck:
    name = "strict_path"

    async def evaluate(self, ctx: RequestContext, storage: Storage, settings: ShieldSettings) -> CheckResult:
        path = ctx.path.lower()
        if not any(s in path for s in settings.strict_paths):
            return CheckResult()

        score = 0
        tags: list[str] = []

        if not ctx.user_agent:
            score += 10
            tags.append("strict_ua_missing")

        if not ctx.headers.get("content-type") and ctx.method in {"POST", "PUT", "PATCH"}:
            score += 18
            tags.append("strict_content_type_missing")

        if ctx.headers.get("x-forwarded-for", "").count(",") > 5:
            score += 14
            tags.append("strict_xff_chain_long")

        return CheckResult(score=score, tags=tags)
