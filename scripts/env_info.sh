#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="${1:-results}"
mkdir -p "$OUT_DIR"

OUT_FILE="$OUT_DIR/env.txt"

{
  echo "=== Date ==="
  date -Iseconds
  echo

  echo "=== OS ==="
  uname -a
  echo
  if command -v lsb_release >/dev/null 2>&1; then
    lsb_release -a 2>/dev/null || true
    echo
  fi

  echo "=== CPU ==="
  if command -v lscpu >/dev/null 2>&1; then
    lscpu
  else
    echo "lscpu not available"
  fi
  echo

  echo "=== Memory ==="
  if command -v free >/dev/null 2>&1; then
    free -h
  else
    echo "free not available"
  fi
  echo

  echo "=== Tool Versions ==="
  echo -n "python: "; python3 --version 2>&1 || true
  echo -n "go: "; go version 2>&1 || true
  echo -n "rustc: "; rustc --version 2>&1 || true
  echo -n "cargo: "; cargo --version 2>&1 || true
  echo

  echo "=== Git ==="
  if command -v git >/dev/null 2>&1; then
    git rev-parse HEAD 2>/dev/null || true
    git status --porcelain 2>/dev/null || true
  else
    echo "git not available"
  fi
} > "$OUT_FILE"

echo "Wrote $OUT_FILE"
