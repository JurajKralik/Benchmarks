#!/usr/bin/env bash
set -euo pipefail

OUT="${OUT:-results/raw.csv}"
REPS="${REPS:-30}"
WARMUP="${WARMUP:-5}"

DATASETS_CSV="datasets/meta/datasets.csv"
JAVA_OUT="java/out"

if [[ ! -f "$DATASETS_CSV" ]]; then
  echo "Missing $DATASETS_CSV. Run gen_datasets.py first." >&2
  exit 1
fi

# Compile Java once
echo "== Compiling Java =="
mkdir -p "$JAVA_OUT"
javac -d "$JAVA_OUT" $(find java/src/main/java -name "*.java")

# Run benchmarks
tail -n +2 "$DATASETS_CSV" | while IFS=, read -r dist n seed path; do
  path="${path//$'\r'/}"

  echo "== Java | Dataset: $path (n=$n dist=$dist) =="

  java -cp "$JAVA_OUT" bench.Main \
    --dataset "$path" \
    --algo builtin \
    --warmup "$WARMUP" \
    --reps "$REPS" \
    --out "$OUT"
done
