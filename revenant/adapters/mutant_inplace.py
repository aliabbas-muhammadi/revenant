"""Mutant: writes the checkpoint in place instead of temp file + rename.

Rewriting the live file is not atomic, so a kill part-way through the write leaves
a truncated checkpoint and the previous good one is gone. When the kill boundary
is reached this mutant dies mid-write, which is the window the atomic protocol
exists to close. Resume must fail loudly with ``CheckpointCorrupt``.
"""

from __future__ import annotations

import json
import os
import signal
from pathlib import Path
from typing import Any

from revenant.adapters.reference import ReferenceAdapter, main
from revenant.checkpoint import SCHEMA_VERSION, _digest


class InPlaceMutant(ReferenceAdapter):
    name = "mutant_inplace"

    def _write_checkpoint(self, path: Path, data: dict[str, Any], dying: bool) -> None:
        body = {"schema_version": SCHEMA_VERSION, **data}
        raw = json.dumps({"body": body, "digest": _digest(body)}, sort_keys=True).encode("utf-8")
        with open(path, "wb") as fh:  # truncates the live checkpoint immediately
            if dying:
                fh.write(raw[: len(raw) // 2])
                fh.flush()
                os.fsync(fh.fileno())
                os.kill(os.getpid(), signal.SIGKILL)
            fh.write(raw)
            fh.flush()
            os.fsync(fh.fileno())


if __name__ == "__main__":
    raise SystemExit(main(adapter_cls=InPlaceMutant))
