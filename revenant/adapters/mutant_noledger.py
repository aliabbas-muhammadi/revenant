"""Mutant: reference runtime whose tools bypass the effects ledger.

Checkpointing is intact, so boundary kills pass. A kill after a tool effect but
before its checkpoint makes resume repeat the step, and with no idempotency key
to suppress it the effect is duplicated in the outside world.
"""

from __future__ import annotations

from revenant.adapters.reference import ReferenceAdapter, main


class NoLedgerMutant(ReferenceAdapter):
    name = "mutant_noledger"
    naive_tools = True


if __name__ == "__main__":
    raise SystemExit(main(adapter_cls=NoLedgerMutant))
