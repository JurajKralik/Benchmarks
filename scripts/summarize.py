#!/usr/bin/env python3
"""
summarize.py

Reads results/raw.csv and produces results/summary.csv with:
- count
- median
- IQR (Q3 - Q1)
- mean
- std

Groups by:
(language, algo, distribution, n)

Usage:
  python3 scripts/summarize.py
"""

from __future__ import annotations

import csv
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean, median
from typing import List


RAW_PATH = Path("results/raw.csv")
OUT_PATH = Path("results/summary.csv")


def percentile(sorted_vals: List[float], p: float) -> float:
	"""
	Simple percentile with linear interpolation.
	p in [0, 100]
	"""
	if not sorted_vals:
		return float("nan")
	if len(sorted_vals) == 1:
		return sorted_vals[0]

	k = (len(sorted_vals) - 1) * (p / 100.0)
	f = math.floor(k)
	c = math.ceil(k)

	if f == c:
		return sorted_vals[int(k)]
	return sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f)


def stddev(vals: List[float], m: float) -> float:
	if len(vals) < 2:
		return 0.0
	return math.sqrt(sum((x - m) ** 2 for x in vals) / (len(vals) - 1))


def main() -> None:
	if not RAW_PATH.exists():
		raise SystemExit(f"Missing {RAW_PATH}")

	groups: dict[tuple, List[float]] = defaultdict(list)

	with RAW_PATH.open(newline="") as f:
		reader = csv.DictReader(f)
		required = {
			"language",
			"algo",
			"distribution",
			"n",
			"time_ms",
			"ok",
		}
		if not required.issubset(reader.fieldnames or []):
			raise SystemExit(f"raw.csv missing required columns: {required}")

		for row in reader:
			if row["ok"].lower() != "true":
				continue

			key = (
				row["language"],
				row["algo"],
				row["distribution"],
				int(row["n"]),
			)
			groups[key].append(float(row["time_ms"]))

	OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

	with OUT_PATH.open("w", newline="") as f:
		writer = csv.writer(f)
		writer.writerow([
			"language",
			"algo",
			"distribution",
			"n",
			"runs",
			"median_ms",
			"iqr_ms",
			"mean_ms",
			"std_ms",
		])

		for (language, algo, dist, n), times in sorted(groups.items()):
			times.sort()
			m = median(times)
			q1 = percentile(times, 25)
			q3 = percentile(times, 75)
			iqr = q3 - q1
			mu = mean(times)
			sd = stddev(times, mu)

			writer.writerow([
				language,
				algo,
				dist,
				n,
				len(times),
				f"{m:.3f}",
				f"{iqr:.3f}",
				f"{mu:.3f}",
				f"{sd:.3f}",
			])

	print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
	main()
