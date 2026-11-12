"""Side-effecting tools and the ledgered invocation path.

A tool performs its effect by writing to the :class:`~revenant.sink.EffectSink`.
``invoke`` wraps it in the ledger protocol: record intent, perform, commit.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from revenant.canon import state_hash
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


class AttemptCounter:
    """Counts every tool call, whether or not it was suppressed or performed.

    It is deliberately separate from the ledger and the sink: attempts are what
    the runtime tried, effects are what happened, and reports show both.
    """

    def __init__(self) -> None:
        self._counts: Counter[str] = Counter()

    def record(self, tool_name: str) -> None:
        self._counts[tool_name] += 1

    def count(self, tool_name: str) -> int:
        return self._counts[tool_name]

    @property
    def total(self) -> int:
        return sum(self._counts.values())

    def by_tool(self) -> dict[str, int]:
        return dict(self._counts)


@dataclass(frozen=True)
class Invocation:
    """Outcome of one ledgered call."""

    key: str
    executed: bool
    result: Any = None


def invoke(
    tool: Tool,
    args: dict[str, Any],
    sink: EffectSink,
    ledger: Ledger,
    attempts: AttemptCounter | None = None,
    naive: bool = False,
) -> Invocation:
    """Run ``tool`` through the ledger: ``begin`` -> ``perform`` -> ``commit``.

    A suppressed attempt (the key is already committed) performs nothing.
    With ``naive=True`` the ledger is bypassed entirely: every call performs
    its effect, which is how a runtime without idempotency keys behaves.
    """
    if attempts is not None:
        attempts.record(tool.name)
    key = tool.idempotency_key(args)
    if naive:
        return Invocation(key, executed=True, result=tool.perform(args, sink))
    if ledger.begin(key, {"tool": tool.name, "args": args}) is Decision.SUPPRESS:
        return Invocation(key, executed=False)
    result = tool.perform(args, sink)
    ledger.commit(key)
    return Invocation(key, executed=True, result=result)


class SendEmail(Tool):
    """``send_email(to, subject, body)``: key is derived from the whole message."""

    name = "send_email"

    def idempotency_key(self, args: dict[str, Any]) -> str:
        return f"{self.name}:{state_hash(self._message(args))[:16]}"

    @staticmethod
    def _message(args: dict[str, Any]) -> dict[str, str]:
        try:
            msg = {k: args[k] for k in ("to", "subject", "body")}
        except KeyError as exc:
            raise ToolError(
                f"send_email requires 'to', 'subject' and 'body'; missing {exc}"
            ) from exc
        for field, value in msg.items():
            if not isinstance(value, str):
                raise ToolError(
                    f"send_email {field!r} must be a string, got {type(value).__name__}"
                )
        return msg

    def perform(self, args: dict[str, Any], sink: EffectSink) -> Any:
        sink.append({"tool": self.name, **self._message(args)})
        return "sent"


class ChargeCard(Tool):
    """``charge_card(customer, amount_cents)``: positive integer cents only."""

    name = "charge_card"

    def idempotency_key(self, args: dict[str, Any]) -> str:
        return f"{self.name}:{state_hash(self._charge(args))[:16]}"

    @staticmethod
    def _charge(args: dict[str, Any]) -> dict[str, Any]:
        try:
            customer, amount = args["customer"], args["amount_cents"]
        except KeyError as exc:
            raise ToolError(
                f"charge_card requires 'customer' and 'amount_cents'; missing {exc}"
            ) from exc
        if not isinstance(customer, str) or not customer:
            raise ToolError("charge_card 'customer' must be a non-empty string")
        if isinstance(amount, bool) or not isinstance(amount, int):
            raise ToolError(
                f"charge_card 'amount_cents' must be an int, got {type(amount).__name__}"
            )
        if amount <= 0:
            raise ToolError(f"charge_card 'amount_cents' must be positive, got {amount}")
        return {"customer": customer, "amount_cents": amount}

    def perform(self, args: dict[str, Any], sink: EffectSink) -> Any:
        sink.append({"tool": self.name, **self._charge(args)})
        return "charged"


class WriteFile(Tool):
    """``write_file(relpath, content)``: writes under a sandbox directory only."""

    name = "write_file"

    def __init__(self, sandbox: str | Path) -> None:
        self.sandbox = Path(sandbox)

    def idempotency_key(self, args: dict[str, Any]) -> str:
        relpath, content = self._parse(args)
        return f"{self.name}:{state_hash({'relpath': relpath, 'content': content})[:16]}"

    @staticmethod
    def _parse(args: dict[str, Any]) -> tuple[str, str]:
        try:
            relpath, content = args["relpath"], args["content"]
        except KeyError as exc:
            raise ToolError(
                f"write_file requires 'relpath' and 'content'; missing {exc}"
            ) from exc
        if not isinstance(relpath, str) or not relpath:
            raise ToolError("write_file 'relpath' must be a non-empty string")
        if not isinstance(content, str):
            raise ToolError(
                f"write_file 'content' must be a string, got {type(content).__name__}"
            )
        return relpath, content

    def _resolve(self, relpath: str) -> Path:
        if (
            relpath.startswith(("/", "\\"))
            or PurePosixPath(relpath).is_absolute()
            or PureWindowsPath(relpath).is_absolute()
            or PureWindowsPath(relpath).drive
        ):
            raise ToolError(f"write_file path must be relative, got {relpath!r}")
        if ".." in PurePosixPath(relpath.replace("\\", "/")).parts:
            raise ToolError(f"write_file path may not contain '..': {relpath!r}")
        root = self.sandbox.resolve()
        target = (root / relpath).resolve()
        if not target.is_relative_to(root):
            raise ToolError(f"write_file path escapes the sandbox: {relpath!r}")
        return target

    def perform(self, args: dict[str, Any], sink: EffectSink) -> Any:
        relpath, content = self._parse(args)
        target = self._resolve(relpath)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        sink.append({"tool": self.name, "relpath": relpath, "content": content})
        return str(target)
