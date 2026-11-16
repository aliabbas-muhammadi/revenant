#!/usr/bin/env bash
# Reduced conformance check for CI: `linear` on the reference adapter must pass,
# and on every mutant it must fail. Exits non-zero on any deviation.
set -u
OUT="${1:-ci-results}"
mkdir -p "$OUT"
run() { uv run revenant run --workload linear --jobs 2 "$@"; }
status=0

run --adapter reference --out "$OUT/reference-linear.json" || { echo "reference failed" >&2; status=1; }

for m in mutant_nocheckpoint mutant_inplace mutant_volatile; do
  if run --adapter "$m" --mode boundary --out "$OUT/$m-linear.json"; then
    echo "$m unexpectedly passed" >&2; status=1
  fi
done
for m in mutant_checkpoint_first mutant_noledger; do
  if run --adapter "$m" --mode mid --out "$OUT/$m-linear.json"; then
    echo "$m unexpectedly passed" >&2; status=1
  fi
done

# Generated workloads: three fixed seeds must pass on the reference adapter.
for seed in 1 2 3; do
  uv run revenant run --adapter reference --workload "gen-$seed" --jobs 2 \
    --out "$OUT/reference-gen-$seed.json" || { echo "reference failed on gen-$seed" >&2; status=1; }
done
exit $status
