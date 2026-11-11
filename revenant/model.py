"""Scripted model: fixed responses by step index, never random."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


class ScriptExhausted(RuntimeError):
    """Raised when the model is asked for a step past the end of its script."""


class ScriptedModel:
    """Return the scripted response for a step index.

    A resume consumes the model differently from a straight run, so responses
    are looked up by step index rather than drawn from a stream.
    """

    def __init__(self, script: Sequence[Any]) -> None:
        self._script = list(script)

    def __len__(self) -> int:
        return len(self._script)

    def respond(self, step: int) -> Any:
        """Return the response for ``step`` (0-based)."""
        if not 0 <= step < len(self._script):
            raise ScriptExhausted(
                f"step {step} is outside the script of {len(self._script)} responses"
            )
        return self._script[step]
