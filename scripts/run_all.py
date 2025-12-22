#!/usr/bin/env python3
"""
gen_datasets.py

Generates integer datasets for sorting benchmarks in a simple binary format:

Binary format (little-endian):
- u32 n
- n * i32 values

Distributions:
- random         : uniform random int32
- sorted         : sorted ascending
- reversed       : sorted descending
- dups           : many duplicates (values from a small range)
- nearly_sorted  : mostly sorted, with a small fraction of random swaps

Also writes:
- datasets/meta/datasets.csv  (distribution,n,seed,path)

Example:
  python3 scripts/gen_datasets.py --outdir datasets/ints --sizes 1000,10000,100000 --seeds 1,2
"""

from __future__ import annotations

import argparse
import csv
import os
import random
import struct
import sys
from array import array
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Tuple


INT32_MIN = -(2**31)
INT32_MAX = 2**31 - 1


@dataclass(frozen=True)
class DatasetSpec:
	distribution: str
	n: int
	seed: int


def parse_int_list(value: str) -> List[int]:
	parts = [p.strip() for p in value.split(",") if p.strip()]
	if not parts:
		raise argparse.ArgumentTypeError("Empty list")
	try:
		return [int(p) for p in parts]
	except ValueError as e:
		raise argparse.ArgumentTypeError(f"Invalid int list: {value}") from e


def ensure_dir(p: Path) -> None:
	p.mkdir(parents=True, exist_ok=True)


def write_bin_int32_le(path: Path, values: array) -> None:
	"""
	Write values as:
	- u32 n (little-endian)
	- i32[n] values (little-endian)
	"""
	n = len(values)
	with path.open("wb") as f:
		f.write(struct.pack("<I", n))

		# array('i') is native-endian; ensure little-endian on disk.
		out = values
		if sys.byteorder != "little":
			out = array("i", values)  # copy
			out.byteswap()

		out.tofile(f)


def gen_random(rng: random.Random, n: int) -> array:
	# Full int32 range; plenty of variety.
	a = array("i", (rng.randint(INT32_MIN, INT32_MAX) for _ in range(n)))
	return a


def gen_sorted(rng: random.Random, n: int) -> array:
	a = gen_random(rng, n)
	a = array("i", sorted(a))
	return a


def gen_reversed(rng: random.Random, n: int) -> array:
	a = gen_sorted(rng, n)
	a.reverse()
	return a


def gen_dups(rng: random.Random, n: int, distinct: int = 128) -> array:
	# Many duplicates: values from 0..distinct-1
	a = array("i", (rng.randrange(distinct) for _ in range(n)))
	return a


def gen_nearly_sorted(rng: random.Random, n: int, swap_fraction: float = 0.01) -> array:
	# Start sorted, then do k random swaps.
	a = gen_sorted(rng, n)
	k = int(n * swap_fraction)
	if n <= 1 or k <= 0:
		return a
	for _ in range(k):
		i = rng.randrange(n)
		j = rng.randrange(n)
		a[i], a[j] = a[j], a[i]
	return a


def build_dataset(spec: DatasetSpec) -> array:
	rng = random.Random(spec.seed)

	dist = spec.distribution
	if dist == "random":
		return gen_random(rng, spec.n)
	if dist == "sorted":
		return gen_sorted(rng, spec.n)
	if dist == "reversed":
		return gen_reversed(rng, spec.n)
	if dist == "dups":
		return gen_dups(rng, spec.n)
	if dist == "nearly_sorted":
		return gen_nearly_sorted(rng, spec.n)

	raise ValueError(f"Unknown distribution: {dist}")


def dataset_filename(spec: DatasetSpec) -> str:
	return f"{spec.distribution}_n{spec.n}_seed{spec.seed}.bin"


def main() -> int:
	parser = argparse.ArgumentParser(description="Generate sorting benchmark datasets.")
	parser.add_argument("--outdir", default="datasets/ints", help="Output directory for .bin datasets")
	parser.add_argument("--meta-dir", default="datasets/meta", help="Directory for datasets.csv")
	parser.add_argument(
		"--sizes",
		type=parse_int_list,
		default=[1_000, 10_000, 100_000, 1_000_000],
		help="Comma-separated sizes, e.g. 1000,10000,100000",
	)
	parser.add_argument(
		"--seeds",
		type=parse_int_list,
		default=[1],
		help="Comma-separated seeds, e.g. 1,2,3",
	)
	parser.add_argument(
		"--dists",
		default="random,sorted,reversed,dups,nearly_sorted",
		help="Comma-separated distributions",
	)
	parser.add_argument(
		"--force",
		action="store_true",
		help="Overwrite existing dataset files",
	)
	parser.add_argument(
		"--dry-run",
		action="store_true",
		help="Print what would be generated without writing files",
	)

	args = parser.parse_args()

	outdir = Path(args.outdir)
	metadir = Path(args.meta_dir)
	ensure_dir(outdir)
	ensure_dir(metadir)

	dists = [d.strip() for d in args.dists.split(",") if d.strip()]
	if not dists:
		print("No distributions provided.", file=sys.stderr)
		return 2

	# Build all specs
	specs: List[DatasetSpec] = []
	for dist in dists:
		for n in args.sizes:
			for seed in args.seeds:
				if n < 0:
					print(f"Invalid size: {n}", file=sys.stderr)
					return 2
				specs.append(DatasetSpec(dist, n, seed))

	rows: List[Tuple[str, int, int, str]] = []

	for spec in specs:
		filename = dataset_filename(spec)
		path = outdir / filename

		rel_path = str(path.as_posix())
		rows.append((spec.distribution, spec.n, spec.seed, rel_path))

		if args.dry_run:
			print(f"[dry-run] Would generate: {rel_path}")
			continue

		if path.exists() and not args.force:
			print(f"Skip existing (use --force to overwrite): {rel_path}")
			continue

		print(f"Generating: {rel_path}")
		values = build_dataset(spec)
		write_bin_int32_le(path, values)

	# Write datasets.csv
	csv_path = metadir / "datasets.csv"
	if args.dry_run:
		print(f"[dry-run] Would write meta CSV: {csv_path.as_posix()}")
		return 0

	with csv_path.open("w", newline="") as f:
		w = csv.writer(f)
		w.writerow(["distribution", "n", "seed", "path"])
		for dist, n, seed, path in rows:
			w.writerow([dist, n, seed, path])

	print(f"Wrote meta CSV: {csv_path.as_posix()}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
