#!/usr/bin/env bash
set -euo pipefail

# --------------------
# Configuration
# --------------------
OUT="${OUT:-results/raw.csv}"
REPS="${REPS:-30}"
WARMUP="${WARMUP:-5}"

DATASETS_CSV="datasets/meta/datasets.csv"

# --------------------
# Sanity checks
# --------------------
if [[ ! -f "$DATASETS_CSV" ]]; then
  echo "Missing $DATASETS_CSV. Run gen_datasets.py first." >&2
  exit 1
fi

mkdir -p "$(dirname "$OUT")"

# --------------------
# Build steps (once)
# --------------------

echo "== Building C++ =="
cmake -S cpp -B cpp/build -DCMAKE_BUILD_TYPE=Release
cmake --build cpp/build -j

echo "== Compiling Java =="
mkdir -p java/out
javac -d java/out $(find java/src/main/java -name "*.java")

# --------------------
# Benchmark loop
# --------------------

tail -n +2 "$DATASETS_CSV" | while IFS=, read -r dist n seed path; do
  # Strip CRLF if present
  path="${path//$'\r'/}"

  echo
  echo "======================================================"
  echo "Dataset: $path | n=$n | dist=$dist | seed=$seed"
  echo "======================================================"

  # -------- Python --------
  echo "[Python]"
  python3 python/bench/main.py \
    --dataset "$path" \
    --algo builtin \
    --warmup "$WARMUP" \
    --reps "$REPS" \
    --out "$OUT"

  # -------- Go --------
  echo "[Go]"
  (cd go && go run ./cmd/bench \
    --dataset "../$path" \
    --algo builtin \
    --warmup "$WARMUP" \
    --reps "$REPS" \
    --out "../$OUT")

  # -------- Rust --------
  echo "[Rust]"
  (cd rust && cargo run --release -- \
    --dataset "../$path" \
    --algo builtin \
    --warmup "$WARMUP" \
    --reps "$REPS" \
    --out "../$OUT")

  # -------- C++ --------
  echo "[C++]"
  ./cpp/build/bench_cpp \
    --dataset "$path" \
    --algo builtin \
    --warmup "$WARMUP" \
    --reps "$REPS" \
    --out "$OUT"

  # -------- Java --------
  echo "[Java]"
  java -cp java/out bench.Main \
    --dataset "$path" \
    --algo builtin \
    --warmup "$WARMUP" \
    --reps "$REPS" \
    --out "$OUT"

done

echo
echo "All benchmarks completed."
echo "Results written to: $OUT"
