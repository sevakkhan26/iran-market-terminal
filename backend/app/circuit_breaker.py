"""Per-venue circuit breaker — stops hammering dead / rate-limited exchanges.

States:
  closed   — normal traffic
  open     — skip all requests until cooldown ends
  half-open— allow a probe; success closes, failure re-opens

This keeps one flaky venue from filling the global HTTP pool and starving
healthy exchanges (the main production instability mode).
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Dict

log = logging.getLogger("terminal.circuit")


@dataclass
class _Breaker:
    failures: int = 0
    successes: int = 0
    opened_until: float = 0.0
    half_open: bool = False
    last_error: str = ""


# consecutive failures before opening
FAILURE_THRESHOLD = 5
# how long to stay open (seconds) — longer for known-hostile venues
DEFAULT_COOLDOWN = 45.0
VENUE_COOLDOWN = {
    "Exir": 120.0,
    "Ramzinex": 90.0,
}
# half-open success streak to fully close
SUCCESS_THRESHOLD = 2


class CircuitBreakers:
    def __init__(self) -> None:
        self._b: Dict[str, _Breaker] = {}

    def _get(self, exchange: str) -> _Breaker:
        b = self._b.get(exchange)
        if b is None:
            b = _Breaker()
            self._b[exchange] = b
        return b

    def allow(self, exchange: str) -> bool:
        b = self._get(exchange)
        now = time.time()
        if b.opened_until <= now:
            if b.opened_until > 0 and not b.half_open:
                # transition open → half-open
                b.half_open = True
                b.failures = 0
                log.info("%s circuit half-open — probing", exchange)
            return True
        return False  # still open

    def record_success(self, exchange: str) -> None:
        b = self._get(exchange)
        b.failures = 0
        b.last_error = ""
        if b.half_open:
            b.successes += 1
            if b.successes >= SUCCESS_THRESHOLD:
                b.half_open = False
                b.opened_until = 0.0
                b.successes = 0
                log.info("%s circuit closed — venue recovered", exchange)
        else:
            b.successes = 0
            b.opened_until = 0.0

    def record_failure(self, exchange: str, err: str = "") -> None:
        b = self._get(exchange)
        b.failures += 1
        b.successes = 0
        b.last_error = (err or "")[:160]
        if b.half_open or b.failures >= FAILURE_THRESHOLD:
            cool = VENUE_COOLDOWN.get(exchange, DEFAULT_COOLDOWN)
            b.opened_until = time.time() + cool
            b.half_open = False
            b.failures = 0
            log.warning("%s circuit OPEN for %.0fs (%s)", exchange, cool,
                        b.last_error or "errors")

    def snapshot(self) -> Dict[str, dict]:
        now = time.time()
        out = {}
        for name, b in self._b.items():
            if b.opened_until > now:
                state = "open"
            elif b.half_open:
                state = "half-open"
            else:
                state = "closed"
            out[name] = {
                "state": state,
                "failures": b.failures,
                "open_for_sec": max(0.0, round(b.opened_until - now, 1)),
                "last_error": b.last_error,
            }
        return out


breakers = CircuitBreakers()
