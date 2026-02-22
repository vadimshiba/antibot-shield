from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ShieldSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ABS_", extra="ignore")

    enabled: bool = True
    redis_url: str = ""
    runtime_env: str = "dev"

    # Hard limits
    requests_per_minute: int = 120
    burst_requests: int = 25
    burst_window_sec: int = 5

    # Risk thresholds
    slow_threshold: int = 30
    challenge_threshold: int = 55
    block_threshold: int = 80

    # Automatic mitigation
    slow_delay_ms: int = 250
    challenge_retry_after_sec: int = 20
    ban_seconds: int = 600
    strike_limit: int = 5
    strike_window_sec: int = 900

    # Scanner detection
    max_unique_paths_per_min: int = 35
    max_404_per_5min: int = 40

    # Trust signals
    trusted_proxies: list[str] = Field(default_factory=list)
    trusted_ips: list[str] = Field(default_factory=list)

    # Header checks for browser paths
    browser_path_prefixes: list[str] = Field(default_factory=lambda: ["/", "/app", "/web", "/ui"])

    # Endpoint tuning
    strict_paths: list[str] = Field(default_factory=lambda: ["/login", "/auth", "/signup", "/register", "/api/auth"])

    # JS challenge
    challenge_secret: str = "change-me-abs-secret"
    js_cookie_name: str = "abs_js_ok"
    js_cookie_ttl_sec: int = 3600
    js_cookie_secure: bool = False
    js_obfuscate_assets_in_prod: bool = True
    js_always_challenge_browser_paths: bool = False
    js_challenge_difficulty: int = 4
    js_pow_rounds: int = 4
    js_score_discount: int = 35
    js_challenge_paths: list[str] = Field(default_factory=lambda: ["/", "/app", "/web", "/ui"])
    js_nonce_max_verify_attempts: int = 4
    js_nonce_verify_window_sec: int = 60
    js_verify_min_pow_elapsed_ms: int = 180
    js_verify_max_pow_elapsed_ms: int = 180000
    js_fp_hash_requests_per_min: int = 40
    js_request_id_requests_per_min: int = 80
    verify_fail_delay_start: int = 2
    verify_fail_short_ban_threshold: int = 6
    verify_fail_long_ban_threshold: int = 12
    verify_fail_short_ban_sec: int = 120
    verify_fail_long_ban_sec: int = 900
    subnet_ban_enabled: bool = True
    subnet_ban_trigger: int = 3
    subnet_ban_window_sec: int = 3600
    subnet_ban_seconds: int = 900
