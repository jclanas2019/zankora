"""Retry logic with exponential backoff for transient failures."""
from __future__ import annotations

import asyncio
from typing import Any, Callable, Type, TypeVar

from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from gateway.observability.logging import get_logger

T = TypeVar("T")
log = get_logger("retry")


class RetryableError(Exception):
    """Base exception for errors that should trigger retries."""

    pass


class TransientError(RetryableError):
    """Transient error that may succeed on retry."""

    pass


class RateLimitError(RetryableError):
    """Rate limit exceeded, should retry with backoff."""

    pass


async def retry_async(
    func: Callable[..., T],
    *args: Any,
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 10.0,
    retryable_exceptions: tuple[Type[Exception], ...] = (TransientError, RateLimitError, asyncio.TimeoutError),
    **kwargs: Any,
) -> T:
    """
    Retry an async function with exponential backoff.
    
    Args:
        func: Async function to retry
        *args: Positional arguments for func
        max_attempts: Maximum number of retry attempts
        min_wait: Minimum wait time between retries (seconds)
        max_wait: Maximum wait time between retries (seconds)
        retryable_exceptions: Exceptions that should trigger retry
        **kwargs: Keyword arguments for func
        
    Returns:
        Function result
        
    Raises:
        RetryError: If all retry attempts failed
    """
    retry_config = AsyncRetrying(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(min=min_wait, max=max_wait),
        retry=retry_if_exception_type(retryable_exceptions),
        reraise=True,
    )

    attempt = 0
    async for attempt_state in retry_config:
        with attempt_state:
            attempt += 1
            try:
                log.debug(
                    "retry_attempt",
                    func=func.__name__,
                    attempt=attempt,
                    max_attempts=max_attempts,
                )
                result = await func(*args, **kwargs)
                if attempt > 1:
                    log.info(
                        "retry_succeeded",
                        func=func.__name__,
                        attempts=attempt,
                    )
                return result
            except Exception as e:
                log.warning(
                    "retry_failed_attempt",
                    func=func.__name__,
                    attempt=attempt,
                    max_attempts=max_attempts,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                raise

    # This should never be reached due to reraise=True
    raise RuntimeError("Retry logic failed unexpectedly")


def retry_sync(
    func: Callable[..., T],
    *args: Any,
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 10.0,
    retryable_exceptions: tuple[Type[Exception], ...] = (TransientError, RateLimitError),
    **kwargs: Any,
) -> T:
    """
    Retry a sync function with exponential backoff.
    
    Args:
        func: Function to retry
        *args: Positional arguments for func
        max_attempts: Maximum number of retry attempts
        min_wait: Minimum wait time between retries (seconds)
        max_wait: Maximum wait time between retries (seconds)
        retryable_exceptions: Exceptions that should trigger retry
        **kwargs: Keyword arguments for func
        
    Returns:
        Function result
        
    Raises:
        RetryError: If all retry attempts failed
    """
    from tenacity import Retrying

    retry_config = Retrying(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(min=min_wait, max=max_wait),
        retry=retry_if_exception_type(retryable_exceptions),
        reraise=True,
    )

    attempt = 0
    for attempt_state in retry_config:
        with attempt_state:
            attempt += 1
            try:
                log.debug(
                    "retry_attempt",
                    func=func.__name__,
                    attempt=attempt,
                    max_attempts=max_attempts,
                )
                result = func(*args, **kwargs)
                if attempt > 1:
                    log.info(
                        "retry_succeeded",
                        func=func.__name__,
                        attempts=attempt,
                    )
                return result
            except Exception as e:
                log.warning(
                    "retry_failed_attempt",
                    func=func.__name__,
                    attempt=attempt,
                    max_attempts=max_attempts,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                raise

    # This should never be reached due to reraise=True
    raise RuntimeError("Retry logic failed unexpectedly")
