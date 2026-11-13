"""Mutant: checkpoints a step before performing its effect.

A kill between the checkpoint and the effect makes resume believe the step is
done, so the effect never happens. In mid-step mode this mutant dies in exactly
that window; the sweep must report a missing effect.
"""

from __future__ import annotations

from revenant.adapters.reference import ReferenceAdapter, main


class CheckpointFirstMutant(ReferenceAdapter):
    name = "mutant_checkpoint_first"
    checkpoint_before_effect = True


if __name__ == "__main__":
    raise SystemExit(main(adapter_cls=CheckpointFirstMutant))
