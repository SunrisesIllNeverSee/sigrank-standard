#!/usr/bin/env python3
"""
integrations/python/example.py

Minimal Python implementation of the SigRank Standard v0.1-draft
five-metric portable core. No dependencies.

A conforming implementation MUST produce the same results as the
conformance suite fixtures for the same inputs.
"""

import math
from datetime import datetime, timezone
from typing import Optional


def _round(n: Optional[float], d: int) -> Optional[float]:
    if n is None or not math.isfinite(n):
        return None
    return round(n, d)


def compute_metrics(
    input_tokens: int,
    output_tokens: int,
    cache_write: Optional[int] = None,
    cache_read: Optional[int] = None,
) -> dict:
    """Compute the five portable metrics from four token pillars."""
    warnings = []

    # SNR = output / (input + output)
    snr_denom = input_tokens + output_tokens
    snr = output_tokens / snr_denom if snr_denom > 0 else None
    if snr is None:
        warnings.append("snr_undefined: input+output=0")

    # Velocity = output / input
    velocity = output_tokens / input_tokens if input_tokens > 0 else None
    if velocity is None:
        warnings.append("velocity_undefined: input=0")

    # Leverage = cache_read / input
    leverage = None
    if cache_read is None:
        pass  # unavailable → null
    elif input_tokens > 0:
        leverage = cache_read / input_tokens
    else:
        warnings.append("leverage_undefined: input=0")

    # Yield = leverage × velocity
    y = None
    if cache_read is None:
        pass  # unavailable → null
    elif leverage is not None and velocity is not None:
        y = leverage * velocity
    else:
        warnings.append("yield_undefined: requires input>0")

    # Standard-level warnings for unavailable cache (emitted before dev10x
    # warning so the "why" precedes the "what" in the warning list)
    if cache_write is None:
        warnings.append("cache_write is unavailable; 10xDEV is undefined.")
    if cache_read is None:
        warnings.append("cache_read is unavailable; Yield, Leverage, and 10xDEV are undefined.")

    # 10xDEV = log10(R / I) = log10(Leverage) — requires all four pillars > 0
    dev10x = None
    if cache_write is None or cache_read is None:
        pass  # unavailable → null
        warnings.append("dev10x_undefined: requires all four pillars > 0")
    elif input_tokens > 0 and output_tokens > 0 and cache_write > 0 and cache_read > 0:
        dev10x = math.log10(cache_read / input_tokens)
    else:
        warnings.append("dev10x_undefined: requires all four pillars > 0")

    return {
        "metrics": {
            "yield": _round(y, 2),
            "leverage": _round(leverage, 1),
            "velocity": _round(velocity, 3),
            "snr": _round(snr, 4),
            "dev10x": _round(dev10x, 2),
        },
        "warnings": warnings,
    }


def build_record(
    input_tokens: int,
    output_tokens: int,
    cache_write: Optional[int] = None,
    cache_read: Optional[int] = None,
    provider: str = "unknown",
    model: str = "unknown",
    tool: str = "unknown",
) -> dict:
    """Build a complete SigRank Standard v0.1-draft record."""
    result = compute_metrics(input_tokens, output_tokens, cache_write, cache_read)
    return {
        "spec": "sigrank/0.1-draft",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": {"provider": provider, "model": model, "tool": tool},
        "telemetry": {
            "input": input_tokens,
            "output": output_tokens,
            "cache_write": cache_write,
            "cache_read": cache_read,
        },
        "metrics": result["metrics"],
        "warnings": result["warnings"],
    }


if __name__ == "__main__":
    # Canonical reference: MO§ES seed values
    record = build_record(
        input_tokens=1251211,
        output_tokens=11296121,
        cache_write=128196310,
        cache_read=2555179769,
        provider="anthropic",
        model="claude-sonnet-4",
        tool="claude-code",
    )
    import json
    print(json.dumps(record, indent=2))
