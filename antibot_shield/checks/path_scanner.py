from __future__ import annotations

from antibot_shield.config import ShieldSettings
from antibot_shield.models import CheckResult, RequestContext
from antibot_shield.storage.base import Storage


class PathScannerCheck:
    name = "path_scanner"

    _exploit_signatures = [
        "/wp-admin",
        "/wp-login",
        "/.env",
        "/phpmyadmin",
        "/cgi-bin",
        "/actuator",
        "/adminer",
    ]

    async def evaluate(self, ctx: RequestContext, storage: Storage, settings: ShieldSettings) -> CheckResult:
        score = 0
        tags: list[str] = []
        hard = False

        path = ctx.path.lower()

        for sig in self._exploit_signatures:
            if sig in path:
                score += 35
                tags.append(f"exploit_probe:{sig}")

        uniq_key = f"abs:uniq:path:{ctx.client_id}:60"
        uniq_size = await storage.sadd(uniq_key, path, ttl_sec=60)

        if uniq_size > settings.max_unique_paths_per_min:
            score += 30
            tags.append("path_scan_pattern")

        if len(tags) >= 2 and any(t.startswith("exploit_probe") for t in tags):
            hard = True

        return CheckResult(score=score, hard_block=hard, tags=tags, meta={"unique_paths": uniq_size})
