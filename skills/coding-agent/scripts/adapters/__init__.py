from __future__ import annotations

from .base import BaseAdapter, InputError
from .codex import CodexAdapter
from .agy import AgyAdapter

_ADAPTERS: dict[str, BaseAdapter] = {
    "codex": CodexAdapter("codex"),
    "tcodex": CodexAdapter("tcodex"),
    "agy": AgyAdapter(),
}

SUPPORTED_AGENTS = tuple(_ADAPTERS.keys())


def get_adapter(name: str) -> BaseAdapter:
    """Retrieve an adapter by agent name."""
    if name not in _ADAPTERS:
        raise InputError(f"unsupported agent: {name!r}; choose from {list(SUPPORTED_AGENTS)}")
    return _ADAPTERS[name]


def is_supported_agent(name: str) -> bool:
    """Check if an agent name is supported."""
    return name in _ADAPTERS
