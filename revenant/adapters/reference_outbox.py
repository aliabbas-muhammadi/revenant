"""Entry point for the outbox variant: ``python -m revenant.adapters.reference_outbox``."""

from __future__ import annotations

from revenant.adapters.reference import main
from revenant.adapters.reference_sqlite import SqliteOutboxAdapter

if __name__ == "__main__":
    raise SystemExit(main(adapter_cls=SqliteOutboxAdapter))
