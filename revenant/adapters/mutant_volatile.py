"""Mutant: records a wall-clock timestamp in state without declaring it volatile.

The checkpointing is correct, but ``wall_time`` differs on every run, so no two
runs of the same workload hash alike. Resume determinism must flag it; the fix is
to keep the field out of state or list it in the workload's ``volatile_fields``.
"""

from __future__ import annotations

import time
from typing import Any

from revenant.adapters.reference import ReferenceAdapter, main

FIELD = "wall_time"


class VolatileMutant(ReferenceAdapter):
    name = "mutant_volatile"

    def _stamp(self, state: dict[str, Any]) -> None:
        state[FIELD] = time.time_ns()


if __name__ == "__main__":
    raise SystemExit(main(adapter_cls=VolatileMutant))
