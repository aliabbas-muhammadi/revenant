"""Scripted model: fixed responses by step index, never random."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any

from revenant.canon import short_hash, state_hash


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

    def __repr__(self) -> str:
        pinned = self._prompt_hashes is not None
        return f"ScriptedModel(responses={len(self._script)}, prompts_pinned={pinned})"

    def __iter__(self) -> Iterator[Any]:
        """Iterate over the scripted responses in step order."""
        return iter(self._script)

    def responses(self) -> list[Any]:
        """Return a copy of the script as a list, in step order."""
        return list(self._script)

    def remaining(self, step: int) -> int:
        """Return how many responses are left from ``step`` onward (0 past the end)."""
        return max(0, len(self._script) - max(0, step))

    def is_exhausted(self, step: int) -> bool:
        """True when ``step`` is past the end of the script."""
        return self.remaining(step) == 0

    def is_pinned(self, step: int) -> bool:
        """True when the script pins an expected prompt hash for ``step``."""
        if self._prompt_hashes is None or not 0 <= step < len(self._script):
            return False
        return self._prompt_hashes[step] is not None

    def window(self, start: int, stop: int) -> list[Any]:
        """Return the scripted responses for steps ``start`` up to (not including) ``stop``.

        Both bounds are clamped to the script, like slicing; negatives raise ``ValueError``.
        """
        if start < 0 or stop < 0:
            raise ValueError("window bounds must not be negative")
        return self._script[start:stop]

    def contains(self, response: Any) -> bool:
        """True when any scripted step has a response equal to ``response``."""
        return self.find(response) is not None

    def head(self, n: int) -> list[Any]:
        """Return the first ``n`` scripted responses, in step order; ``n`` must not be negative."""
        if n < 0:
            raise ValueError("head() count must not be negative")
        return self._script[:n]

    def tail(self, n: int) -> list[Any]:
        """Return the last ``n`` scripted responses, in step order; ``n`` must not be negative."""
        if n < 0:
            raise ValueError("tail() count must not be negative")
        if n == 0:
            return []
        return self._script[-n:]

    def find(self, response: Any) -> int | None:
        """Return the first step whose scripted response equals ``response``, or None."""
        for step, scripted in enumerate(self._script):
            if scripted == response:
                return step
        return None

    def indices_of(self, response: Any) -> list[int]:
        """Return every step whose scripted response equals ``response``, in step order."""
        return [step for step, scripted in enumerate(self._script) if scripted == response]

    def count(self, response: Any) -> int:
        """Return how many scripted steps have a response equal to ``response``."""
        return sum(1 for scripted in self._script if scripted == response)

    def distinct_count(self) -> int:
        """Count distinct scripted responses, comparing by canonical hash."""
        return len({state_hash(response) for response in self._script})

    def is_empty(self) -> bool:
        """True for a zero-step script."""
        return not self._script

    def last_step(self) -> int | None:
        """Return the index of the final scripted step, or None for an empty script."""
        return len(self._script) - 1 if self._script else None

    def peek(self, step: int) -> Any:
        """Return the scripted response for ``step`` without any prompt check."""
        return self.respond(step)

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
                    f"step {step}: prompt hash {short_hash(prompt)} != expected {expected[:12]}"
                )
        return self._script[step]
