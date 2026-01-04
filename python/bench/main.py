#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import platform
import struct
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List


def read_bin_int32_le(path: str) -> List[int]:
	with open(path, "rb") as f:
		header = f.read(4)
		if len(header) != 4:
			raise ValueError("File too small (missing n header)")
		(n,) = struct.unpack("<I", header)
		data = f.read()
		expected = n * 4
		if len(data) != expected:
			raise ValueError(f"Expected {expected} bytes of payload, got {len(data)}")
		# '<' little-endian, 'i' int32
		values = list(struct.unpack("<" + "i" * n, data))
		return values


def is_sorted_non_decreasing(a: List[int]) -> bool:
	return all(a[i] <= a[i + 1] for i in range(len(a) - 1))


def infer_distribution(dataset_path: str) -> str:
	name = Path(dataset_path).name
	# expects: "<dist>_n<...>_seed<...>.bin"
	dist = name.split("_n", 1)[0]
	return dist


def now_iso() -> str:
	# ISO-like (no timezone handling needed for CSV)
	return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())


def monotonic_ns() -> int:
	return time.perf_counter_ns()


def detect_python_version() -> str:
	return platform.python_version()


@dataclass
class Args:
	dataset: str
	algo: str
	warmup: int
	reps: int
	out: str
	validate: bool


def parse_args() -> Args:
	p = argparse.ArgumentParser(description="Python sorting benchmark runner")
	p.add_argument("--dataset", required=True, help="Path to .bin dataset")
	p.add_argument("--algo", default="builtin", choices=["builtin"], help="Sorting algorithm")
	p.add_argument("--warmup", type=int, default=5, help="Warmup runs (not recorded)")
	p.add_argument("--reps", type=int, default=30, help="Measured repetitions")
	p.add_argument("--out", default="results/raw.csv", help="CSV output path")
	p.add_argument("--no-validate", action="store_true", help="Disable sortedness validation")
	a = p.parse_args()

	if a.warmup < 0 or a.reps <= 0:
		raise SystemExit("warmup must be >= 0 and reps must be > 0")

	return Args(
		dataset=a.dataset,
		algo=a.algo,
		warmup=a.warmup,
		reps=a.reps,
		out=a.out,
		validate=not a.no_validate,
	)


def ensure_parent_dir(path: str) -> None:
	Path(path).parent.mkdir(parents=True, exist_ok=True)


def append_row(csv_path: str, row: List[str]) -> None:
	ensure_parent_dir(csv_path)
	file_exists = Path(csv_path).exists()

	with open(csv_path, "a", newline="") as f:
		w = csv.writer(f)
		if not file_exists:
			w.writerow([
				"timestamp_iso",
				"task",
				"language",
				"language_version",
				"algo",
				"dataset_file",
				"distribution",
				"n",
				"warmup_runs",
				"rep_idx",
				"time_ms",
				"ok",
			])
		w.writerow(row)


def main() -> int:
	args = parse_args()

	values = read_bin_int32_le(args.dataset)
	n = len(values)
	dist = infer_distribution(args.dataset)

	lang = "python"
	lang_ver = detect_python_version()

	# Warmup
	for _ in range(args.warmup):
		tmp = values.copy()
		tmp.sort()

	# Measured runs
	for rep in range(args.reps):
		tmp = values.copy()
		t0 = monotonic_ns()
		tmp.sort()
		t1 = monotonic_ns()

		ok = True
		if args.validate:
			ok = is_sorted_non_decreasing(tmp)

		time_ms = (t1 - t0) / 1_000_000.0

		row = [
			now_iso(),
			"sort",
			lang,
			lang_ver,
			args.algo,
			args.dataset,
			dist,
			str(n),
			str(args.warmup),
			str(rep),
			f"{time_ms:.3f}",
			"true" if ok else "false",
		]

		# Print + append
		print(",".join(row))
		append_row(args.out, row)

	return 0


if __name__ == "__main__":
	raise SystemExit(main())
