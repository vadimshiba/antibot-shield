from __future__ import annotations

from antibot_shield.config import ShieldSettings
from antibot_shield.models import CheckResult, RequestContext
from antibot_shield.storage.base import Storage


class MethodGuardCheck:
    name = "method_guard"

    _allowed = {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"}
    _dangerous = {"TRACE", "TRACK", "CONNECT"}

    async def evaluate(self, ctx: RequestContext, storage: Storage, settings: ShieldSettings) -> CheckResult:
        method = ctx.method.upper()

        if method in self._dangerous:
            return CheckResult(score=60, hard_block=True, tags=[f"danger_method:{method}"])

        if method not in self._allowed:
            return CheckResult(score=20, tags=[f"unknown_method:{method}"])

        return CheckResult()
