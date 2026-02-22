from __future__ import annotations

from antibot_shield.config import ShieldSettings
from antibot_shield.models import CheckResult, RequestContext
from antibot_shield.storage.base import Storage


class HeaderAnomalyCheck:
    name = "header_anomaly"

    async def evaluate(self, ctx: RequestContext, storage: Storage, settings: ShieldSettings) -> CheckResult:
        score = 0
        tags: list[str] = []

        if ctx.is_browser_path:
            accept = ctx.headers.get("accept", "")
            lang = ctx.headers.get("accept-language", "")
            sec_fetch = ctx.headers.get("sec-fetch-site", "")

            if "text/html" not in accept and "*/*" not in accept:
                score += 10
                tags.append("accept_unusual")

            if not lang:
                score += 8
                tags.append("lang_missing")

            if not sec_fetch and ctx.path.startswith("/"):
                score += 6
                tags.append("sec_fetch_missing")

        return CheckResult(score=score, tags=tags)
