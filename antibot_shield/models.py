from dataclasses import dataclass, field
from typing import Any


@dataclass
class RequestContext:
    client_ip: str
    client_id: str
    method: str
    path: str
    user_agent: str
    headers: dict[str, str]
    is_browser_path: bool


@dataclass
class CheckResult:
    score: int = 0
    hard_block: bool = False
    tags: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)
