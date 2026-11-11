"""Scripted model: fixed responses by step index, never random."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from revenant.canon import state_hash


class ScriptExhausted(RuntimeError):
    """Raised when the model is asked for a step past the end of its script."""


class PromptDivergence(RuntimeError):
    """Raised when the prompt at a step differs from the one the script expects."""


class ScriptedModel:
    """Return the scripted response for a step index.

    A resume consumes the model differently from a straight run, so responses
    are looked up by step index rather than drawn from a stream.

    ``prompt_hashes`` optionally pins the expected prompt per step (a
    ``state_hash`` of the prompt, or ``None`` to leave a step unchecked), so
    input drift is caught where it starts instead of surfacing later as a
    mysterious state divergence.
    """

    def __init__(
        self,
        script: Sequence[Any],
        prompt_hashes: Sequence[str | None] | None = None,
    ) -> None:
        self._script = list(script)
        if prompt_hashes is not None and len(prompt_hashes) != len(self._script):
            raise ValueError("prompt_hashes must have one entry per scripted response")
        self._prompt_hashes = None if prompt_hashes is None else list(prompt_hashes)

    def __len__(self) -> int:
        return len(self._script)

    def respond(self, step: int, prompt: Any = None) -> Any:
        """Return the response for ``step`` (0-based).

        When ``prompt`` is given and the script pins a hash for this step, a
        mismatch raises :class:`PromptDivergence`.
        """
        if not 0 <= step < len(self._script):
            raise ScriptExhausted(
                f"step {step} is outside the script of {len(self._script)} responses"
            )
        expected = None if self._prompt_hashes is None else self._prompt_hashes[step]
        if expected is not None and prompt is not None:
            actual = state_hash(prompt)
            if actual != expected:
                raise PromptDivergence(
                    f"step {step}: prompt hash {actual[:12]} != expected {expected[:12]}"
                )
        return self._script[step]
