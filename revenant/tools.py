"""Side-effecting tools and the ledgered invocation path.

A tool performs its effect by writing to the :class:`~revenant.sink.EffectSink`.
``invoke`` wraps it in the ledger protocol: record intent, perform, commit.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from revenant.ledger import Decision, Ledger
from revenant.sink import EffectSink


class ToolError(ValueError):
    """Raised when a tool is called with arguments it must refuse."""


class Tool(ABC):
    """A named operation with an external effect."""

    name: str

    @abstractmethod
    def idempotency_key(self, args: dict[str, Any]) -> str:
        """Return the key that identifies this logical effect across attempts."""

    @abstractmethod
    def perform(self, args: dict[str, Any], sink: EffectSink) -> Any:
        """Carry out the effect, recording it in ``sink``."""


@dataclass(frozen=True)
class Invocation:
    """Outcome of one ledgered call."""

    key: str
    executed: bool
    result: Any = None


def invoke(tool: Tool, args: dict[str, Any], sink: EffectSink, ledger: Ledger) -> Invocation:
    """Run ``tool`` through the ledger: ``begin`` -> ``perform`` -> ``commit``.

    A suppressed attempt (the key is already committed) performs nothing.
    """
    key = tool.idempotency_key(args)
    if ledger.begin(key, {"tool": tool.name, "args": args}) is Decision.SUPPRESS:
        return Invocation(key, executed=False)
    result = tool.perform(args, sink)
    ledger.commit(key)
    return Invocation(key, executed=True, result=result)
