"""Timeout, bounded retry and circuit breaking around provider calls.

AI is never a single point of failure: every call is time-boxed, retried at
most `max_attempts - 1` times, and short-circuited while a provider is failing.
Callers receive a structured `AIError` and fall back to the original patient
information.
"""

import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

from app.providers.ai.errors import AICircuitOpen, AIError, AIProviderUnavailable, AITimeout

T = TypeVar("T")

RETRYABLE = (AITimeout, AIProviderUnavailable)


class CircuitBreaker:
    """Opens after `threshold` consecutive failures; half-opens after `reset_seconds`."""

    def __init__(self, threshold: int = 3, reset_seconds: float = 60.0):
        self.threshold = threshold
        self.reset_seconds = reset_seconds
        self._failures = 0
        self._opened_at: float | None = None

    @property
    def is_open(self) -> bool:
        if self._opened_at is None:
            return False
        if time.monotonic() - self._opened_at >= self.reset_seconds:
            # Half-open: let the next call through.
            self._opened_at = None
            self._failures = self.threshold - 1
            return False
        return True

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.threshold:
            self._opened_at = time.monotonic()

    def reset(self) -> None:
        self._failures = 0
        self._opened_at = None


async def call_with_resilience(
    operation: Callable[[], Awaitable[T]],
    *,
    timeout_seconds: float,
    max_attempts: int = 2,
    breaker: CircuitBreaker | None = None,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> T:
    if breaker is not None and breaker.is_open:
        raise AICircuitOpen("AI provider is temporarily unavailable")

    last: AIError | None = None
    for attempt in range(1, max(1, max_attempts) + 1):
        try:
            result = await asyncio.wait_for(operation(), timeout=timeout_seconds)
        except TimeoutError:
            last = AITimeout(f"AI provider did not respond within {timeout_seconds:g}s")
        except AIError as exc:
            last = exc
            if not isinstance(exc, RETRYABLE):
                break  # malformed output or bad credentials will not fix themselves
        else:
            if breaker is not None:
                breaker.record_success()
            return result
        if attempt < max_attempts and isinstance(last, RETRYABLE):
            await sleep(min(0.2 * 2 ** (attempt - 1) + random.uniform(0, 0.1), 2.0))

    if breaker is not None:
        breaker.record_failure()
    raise last or AIProviderUnavailable("AI provider failed")
