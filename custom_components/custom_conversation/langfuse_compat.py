"""Lazy-loading compatibility layer for langfuse.

Langfuse uses Pydantic v1 internally, which is incompatible with Python 3.14+
(PEP 649 deferred annotations). This module defers all langfuse imports to
runtime so that module-level imports don't crash during HA startup.
"""

from __future__ import annotations

import functools
import inspect
from typing import Any


class _LazyLangfuseContext:
    """Proxy that lazily imports langfuse_context on first attribute access."""

    _real: Any = None

    def _load(self) -> Any:
        if self._real is None:
            from langfuse.decorators import langfuse_context
            self._real = langfuse_context
        return self._real

    def __getattr__(self, name: str) -> Any:
        return getattr(self._load(), name)


langfuse_context = _LazyLangfuseContext()


def observe(
    name: str | None = None, *, capture_input: bool = True, **extra_kwargs: Any
) -> Any:
    """Lazy wrapper for langfuse @observe decorator.

    Returns a decorator that defers the langfuse import to the first call.
    Accepts all kwargs that the real langfuse @observe accepts.
    """
    def decorator(func: Any) -> Any:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                from langfuse.decorators import observe as _observe
                kw: dict[str, Any] = {"capture_input": capture_input, **extra_kwargs}
                if name is not None:
                    kw["name"] = name
                decorated = _observe(**kw)(func)
                return await decorated(*args, **kwargs)
            except Exception:
                return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                from langfuse.decorators import observe as _observe
                kw: dict[str, Any] = {"capture_input": capture_input, **extra_kwargs}
                if name is not None:
                    kw["name"] = name
                decorated = _observe(**kw)(func)
                return decorated(*args, **kwargs)
            except Exception:
                return func(*args, **kwargs)

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator
