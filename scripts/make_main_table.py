#!/usr/bin/env python3
from __future__ import annotations

import csv
from pathlib import Path

SUMMARY = Path("results/summary.csv")
OUT = Path("results/main_table_random_n1e6.csv")

TARGET_DIST = "random"
TARGET_N = 1_000_000
TARGET_ALGO = "builtin"


def main() -> None:
	if not SUMMARY.exists():
		raise SystemExit("Missing results/summary.csv")

	rows = []
	with SUMMARY.open(newline="") as f:
		r = csv.DictReader(f)
		for row in r:
			if (
				row["distribution"] == TARGET_DIST
				and int(row["n"]) == TARGET_N
				and row["algo"] == TARGET_ALGO
			):
				rows.append(row)

	if not rows:
		raise SystemExit("No matching rows found")

	# Sort by median runtime (fastest first)
	rows.sort(key=lambda r: float(r["median_ms"]))

	OUT.parent.mkdir(parents=True, exist_ok=True)
	with OUT.open("w", newline="") as f:
		w = csv.writer(f)
		w.writerow([
			"language",
			"median_ms",
			"iqr_ms",
			"mean_ms",
			"std_ms",
			"runs",
		])
		for r in rows:
			w.writerow([
				r["language"],
				r["median_ms"],
				r["iqr_ms"],
				r["mean_ms"],
				r["std_ms"],
				r["runs"],
			])

	print(f"Wrote {OUT}")


if __name__ == "__main__":
	main()
