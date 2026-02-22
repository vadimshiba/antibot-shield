from __future__ import annotations

from antibot_shield.config import ShieldSettings
from antibot_shield.models import CheckResult, RequestContext
from antibot_shield.storage.base import Storage


class AutomationCheck:
    name = "automation"

    async def evaluate(self, ctx: RequestContext, storage: Storage, settings: ShieldSettings) -> CheckResult:
        score = 0
        tags: list[str] = []
        hard = False

        h = ctx.headers
        ua = (ctx.user_agent or "").lower()
        sec_ch_ua = h.get("sec-ch-ua", "").lower()

        # Common headless fingerprints
        if "headlesschrome" in ua or "headless" in sec_ch_ua:
            score += 35
            tags.append("headless_fingerprint")

        # Selenium / webdriver hints
        if h.get("x-webdriver") == "1" or h.get("x-automation") == "1":
            score += 45
            tags.append("webdriver_header")

        # Browser path with missing modern browser hints may indicate scripted client
        if ctx.is_browser_path:
            if not h.get("sec-ch-ua-platform") and not h.get("sec-ch-ua-mobile"):
                score += 6
                tags.append("missing_client_hints")

        if "selenium" in ua or "playwright" in ua:
            score += 40
            tags.append("automation_ua")
            hard = True

        return CheckResult(score=score, hard_block=hard, tags=tags)
