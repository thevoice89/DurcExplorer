"""Policy di retry con backoff esponenziale + jitter (wrapper su tenacity)."""
import logging
from collections.abc import Callable
from typing import Any

import requests
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    wait_random,
)

from durc_batch.core.exceptions import RateLimitExceeded
from durc_batch.core.logging_conf import get_logger

# Errori considerati transitori → si ritenta.
_TRANSIENT = (
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
    RateLimitExceeded,
)


def with_backoff(max_retries: int) -> Callable[..., Any]:
    """Decoratore: ritenta su errori transitori (timeout/5xx/429) con
    exponential backoff e jitter, fino a `max_retries`. NON ritenta sui 4xx
    definitivi (es. 400/401/403)."""
    logger = get_logger(__name__)
    _exp = wait_exponential(multiplier=1, max=60)
    _jitter = wait_random(0, 1)

    def _wait(retry_state) -> float:
        """Onora Retry-After dei 429, altrimenti backoff esponenziale + jitter."""
        exc = retry_state.outcome.exception() if retry_state.outcome else None
        if isinstance(exc, RateLimitExceeded) and exc.retry_after is not None:
            return float(exc.retry_after)
        return _exp(retry_state) + _jitter(retry_state)

    return retry(
        retry=retry_if_exception_type(_TRANSIENT),
        stop=stop_after_attempt(max_retries + 1),
        wait=_wait,
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
