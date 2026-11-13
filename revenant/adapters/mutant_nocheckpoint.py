"""Mutant: never reads its checkpoint, so every run restarts from step 0.

A runtime with no durable memory also forgets its ledger, so re-run tools repeat
their effects in the outside world. The sweep must catch it.
"""

from __future__ import annotations

from revenant.adapters.reference import ReferenceAdapter, main


class NoCheckpointMutant(ReferenceAdapter):
    name = "mutant_nocheckpoint"
    resume_from_checkpoint = False


if __name__ == "__main__":
    raise SystemExit(main(adapter_cls=NoCheckpointMutant))
