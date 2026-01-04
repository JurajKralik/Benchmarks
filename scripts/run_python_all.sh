#!/usr/bin/env bash
set -euo pipefail

OUT="results/raw.csv"
REPS="${REPS:-30}"
WARMUP="${WARMUP:-5}"

tail -n +2 datasets/meta/datasets.csv | while IFS=, read -r dist n seed path; do
  path="${path//$'\r'/}"

  python3 python/bench/main.py \
    --dataset "$path" \
    --algo builtin \
    --warmup "$WARMUP" \
    --reps "$REPS" \
    --out "$OUT"
done

