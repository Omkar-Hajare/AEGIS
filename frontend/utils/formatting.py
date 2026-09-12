"""Standardized formatting rules for AEGIS.

Strictly enforces human-readable formatting across hit rates, latency, sizes,
durations, and timestamps while avoiding fake precision or NaN/None errors.
"""

from datetime import datetime
from typing import Any


def format_percentage(val: float | None, precision: int = 1) -> str:
    """Format hit/miss ratio into human-readable percentage (e.g. 0.50 -> '50.0%')."""
    if val is None:
        return "Not available"
    try:
        f_val = float(val)
        # If value is between 0.0 and 1.0, scale to 0-100%
        if 0.0 <= f_val <= 1.0:
            f_val = f_val * 100.0
        return f"{f_val:.{precision}f}%"
    except (ValueError, TypeError):
        return "Not available"


def format_latency(ms: float | None, precision: int = 1) -> str:
    """Format latency in milliseconds (e.g. 30.188 -> '30.2 ms')."""
    if ms is None or ms < 0:
        return "0.0 ms"
    try:
        return f"{float(ms):.{precision}f} ms"
    except (ValueError, TypeError):
        return "Not available"


def format_request_rate(rps: float | None, precision: int = 3) -> str:
    """Format request rate in req/s (e.g. 0.052 -> '0.052 req/s')."""
    if rps is None:
        return "0.000 req/s"
    try:
        f_rps = float(rps)
        if f_rps >= 10.0:
            return f"{f_rps:.1f} req/s"
        return f"{f_rps:.{precision}f} req/s"
    except (ValueError, TypeError):
        return "0.000 req/s"


def format_bytes(num_bytes: int | float | None) -> str:
    """Format byte size into human-readable B / KB / MB / GB.
    
    If None, returns 'Unconstrained / not configured' adhering to backend contract.
    """
    if num_bytes is None:
        return "Unconstrained / not configured"
    try:
        b = float(num_bytes)
        if b < 0:
            return "0 B"
        if b < 1024:
            return f"{int(b)} B"
        elif b < 1024 * 1024:
            return f"{b / 1024:.1f} KB"
        elif b < 1024 * 1024 * 1024:
            return f"{b / (1024 * 1024):.1f} MB"
        else:
            return f"{b / (1024 * 1024 * 1024):.2f} GB"
    except (ValueError, TypeError):
        return "Not available"


def format_duration(seconds: float | None) -> str:
    """Format window duration into human-readable format (e.g. 278s -> '4m 38s')."""
    if seconds is None or seconds <= 0:
        return "0s"
    try:
        total_sec = int(round(float(seconds)))
        if total_sec < 60:
            return f"{total_sec}s"
        mins = total_sec // 60
        rem_sec = total_sec % 60
        if mins < 60:
            return f"{mins}m {rem_sec:02d}s" if rem_sec > 0 else f"{mins}m"
        hours = mins // 60
        rem_mins = mins % 60
        return f"{hours}h {rem_mins}m"
    except (ValueError, TypeError):
        return "0s"


def format_int(count: int | float | None) -> str:
    """Format integer count with thousands separators (e.g. 1240 -> '1,240')."""
    if count is None:
        return "0"
    try:
        return f"{int(count):,}"
    except (ValueError, TypeError):
        return "0"


def format_timestamp(ts: Any) -> str:
    """Format ISO timestamp or datetime object into human-readable local format."""
    if not ts:
        return "Just now"
    try:
        if isinstance(ts, str):
            # Parse ISO format (handling optional Z or +00:00)
            cleaned = ts.replace("Z", "+00:00")
            dt = datetime.fromisoformat(cleaned)
        elif isinstance(ts, datetime):
            dt = ts
        else:
            return str(ts)
        return dt.strftime("%H:%M:%S UTC")
    except Exception:
        return str(ts)[:19]
