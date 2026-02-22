from __future__ import annotations

from antibot_shield.config import ShieldSettings
from antibot_shield.models import CheckResult, RequestContext
from antibot_shield.storage.base import Storage


class UserAgentCheck:
    name = "user_agent"

    _bad_fragments = [
        "sqlmap",
        "nmap",
        "nikto",
        "masscan",
        "python-requests",
        "curl/",
        "wget/",
        "bot",
        "spider",
    ]

    async def evaluate(self, ctx: RequestContext, storage: Storage, settings: ShieldSettings) -> CheckResult:
        ua = (ctx.user_agent or "").strip().lower()
        score = 0
        tags: list[str] = []
        hard = False

        if not ua:
            score += 20
            tags.append("ua_missing")

        if len(ua) < 8:
            score += 8
            tags.append("ua_too_short")

        for marker in self._bad_fragments:
            if marker in ua:
                score += 20
                tags.append(f"ua_marker:{marker}")

        if "sqlmap" in ua or "nikto" in ua:
            hard = True

        return CheckResult(score=score, hard_block=hard, tags=tags)
