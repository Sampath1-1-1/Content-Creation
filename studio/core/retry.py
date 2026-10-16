"""Retry with exponential backoff (for rate limits and temporary server errors)."""

from __future__ import annotations

import random
import time
from typing import Callable, TypeVar

T = TypeVar("T")


def backoff_delay(attempt: int, base: float, maximum: float, rng: random.Random) -> float:
    """attempt 1 → ~base, 2 → ~2*base, 3 → ~4*base ... with ±25% jitter, capped."""
    delay = min(maximum, base * (2 ** (attempt - 1)))
    return delay * rng.uniform(0.75, 1.25)


def with_retries(
    fn: Callable[[], T],
    *,
    attempts: int,
    base_delay: float,
    max_delay: float,
    is_retryable: Callable[[BaseException], bool],
    retry_after: Callable[[BaseException], float | None] = lambda e: None,
    on_retry: Callable[[int, float, BaseException], None] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    seed: int = 0,
) -> T:
    rng = random.Random(seed)
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - we re-raise non-retryable
            if attempt >= attempts or not is_retryable(exc):
                raise
            wait = retry_after(exc) or backoff_delay(attempt, base_delay, max_delay, rng)
            wait = min(wait, max_delay)
            if on_retry:
                on_retry(attempt, wait, exc)
            sleep(wait)
    raise RuntimeError("unreachable")  # pragma: no cover
