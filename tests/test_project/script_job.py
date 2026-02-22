from __future__ import annotations

import hashlib
import time


def run_heavy_job(input_text: str) -> dict[str, object]:
    """Example script logic you can replace with your real task."""
    start = time.perf_counter()
    digest = hashlib.sha256(input_text.encode("utf-8")).hexdigest()
    time.sleep(0.25)
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    return {
        "ok": True,
        "input": input_text,
        "sha256": digest,
        "elapsed_ms": elapsed_ms,
    }
