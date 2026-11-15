.PHONY: test lint conformance table ci-conformance

WORKLOADS := linear branching fanout
BOUNDARY_MUTANTS := mutant_nocheckpoint mutant_inplace mutant_volatile
MID_MUTANTS := mutant_checkpoint_first mutant_noledger
VARIANTS := reference_sqlite reference_outbox
CHAOS := none dup timeout corrupt all
RUN := uv run revenant run

test:
	uv run pytest

lint:
	uv run ruff check
	uv run mypy

# Full conformance matrix: regenerates every report under results/ by running the CLI.
conformance:
	mkdir -p results/mutants results/langgraph results/chaos results/outbox
	for w in $(WORKLOADS); do \
	  $(RUN) --adapter reference --workload $$w --jobs 4 --out results/reference-$$w.json; \
	  uv run revenant report --format md results/reference-$$w.json > results/reference-$$w.md; \
	  for c in $(filter-out none,$(CHAOS)); do \
	    $(RUN) --adapter reference --workload $$w --chaos $$c --jobs 4 --out results/chaos/reference-$$w-$$c.json; \
	    uv run revenant report --format md results/chaos/reference-$$w-$$c.json > results/chaos/reference-$$w-$$c.md; \
	  done; \
	  for a in $(VARIANTS); do \
	    $(RUN) --adapter $$a --workload $$w --jobs 4 --out results/outbox/$$a-$$w.json; \
	    uv run revenant report --format md results/outbox/$$a-$$w.json > results/outbox/$$a-$$w.md; \
	    $(RUN) --adapter $$a --workload $$w --mode mid --jobs 4 --out results/outbox/$$a-$$w-mid.json; \
	    uv run revenant report --format md results/outbox/$$a-$$w-mid.json > results/outbox/$$a-$$w-mid.md; \
	  done; \
	done
	for m in $(BOUNDARY_MUTANTS) $(MID_MUTANTS); do \
	  mode=boundary; case " $(MID_MUTANTS) " in *" $$m "*) mode=mid;; esac; \
	  $(RUN) --adapter $$m --workload linear --mode $$mode --jobs 4 --out results/mutants/$$m-linear.json || true; \
	  uv run revenant report --format md results/mutants/$$m-linear.json > results/mutants/$$m-linear.md; \
	done
	for w in $(WORKLOADS); do \
	  $(RUN) --adapter langgraph_sqlite --workload $$w --mode mid --jobs 4 --out results/langgraph/ledgered-$$w.json; \
	  uv run revenant report --format md results/langgraph/ledgered-$$w.json > results/langgraph/ledgered-$$w.md; \
	  $(RUN) --adapter langgraph_sqlite --workload $$w --mode mid --naive-tools --jobs 4 --out results/langgraph/naive-$$w.json || true; \
	  uv run revenant report --format md results/langgraph/naive-$$w.json > results/langgraph/naive-$$w.md; \
	done
	$(MAKE) table

table:
	uv run python scripts/render_tables.py

# Reduced matrix used by CI: reference passes, every mutant fails.
ci-conformance:
	scripts/ci_conformance.sh ci-results
