from __future__ import annotations

from antibot_shield.checks.automation import AutomationCheck
from antibot_shield.checks.burst import BurstCheck
from antibot_shield.checks.header_anomaly import HeaderAnomalyCheck
from antibot_shield.checks.method_guard import MethodGuardCheck
from antibot_shield.checks.path_scanner import PathScannerCheck
from antibot_shield.checks.rate_limit import RateLimitCheck
from antibot_shield.checks.recent_404 import Recent404Check
from antibot_shield.checks.strict_path import StrictPathCheck
from antibot_shield.checks.user_agent import UserAgentCheck
from antibot_shield.config import ShieldSettings
from antibot_shield.models import CheckResult, RequestContext
from antibot_shield.storage.base import Storage


class ShieldEngine:
    def __init__(self) -> None:
        self.checks = [
            MethodGuardCheck(),
            AutomationCheck(),
            UserAgentCheck(),
            HeaderAnomalyCheck(),
            RateLimitCheck(),
            BurstCheck(),
            PathScannerCheck(),
            StrictPathCheck(),
            Recent404Check(),
        ]

    async def evaluate(self, ctx: RequestContext, storage: Storage, settings: ShieldSettings) -> tuple[int, bool, list[str], dict[str, int]]:
        total = 0
        hard = False
        tags: list[str] = []
        meta: dict[str, int] = {}

        for check in self.checks:
            result: CheckResult = await check.evaluate(ctx, storage, settings)
            total += result.score
            hard = hard or result.hard_block
            tags.extend(result.tags)
            for k, v in result.meta.items():
                if isinstance(v, int):
                    meta[k] = v

        return total, hard, tags, meta
