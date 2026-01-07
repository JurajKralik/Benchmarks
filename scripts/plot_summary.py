#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt


def read_summary(path: Path) -> List[dict]:
	with path.open(newline="") as f:
		r = csv.DictReader(f)
		required = {"language", "algo", "distribution", "n", "runs", "median_ms", "iqr_ms", "mean_ms", "std_ms"}
		if not required.issubset(set(r.fieldnames or [])):
			raise SystemExit(f"{path} missing required columns: {sorted(required)}")
		rows = []
		for row in r:
			# normalize types
			row["n"] = int(row["n"])
			row["runs"] = int(row["runs"])
			row["median_ms"] = float(row["median_ms"])
			row["iqr_ms"] = float(row["iqr_ms"])
			row["mean_ms"] = float(row["mean_ms"])
			row["std_ms"] = float(row["std_ms"])
			rows.append(row)
		return rows


def safe_div(a: float, b: float) -> float:
	if b == 0.0:
		return float("nan")
	return a / b


def plot_runtime(rows: List[dict], outdir: Path, algo: str) -> None:
	# dist -> lang -> list[(n, median)]
	by_dist: Dict[str, Dict[str, List[Tuple[int, float]]]] = defaultdict(lambda: defaultdict(list))
	for r in rows:
		if r["algo"] != algo:
			continue
		by_dist[r["distribution"]][r["language"]].append((r["n"], r["median_ms"]))

	for dist, by_lang in sorted(by_dist.items()):
		plt.figure()
		for lang, pts in sorted(by_lang.items()):
			pts_sorted = sorted(pts, key=lambda x: x[0])
			x = [p[0] for p in pts_sorted]
			y = [p[1] for p in pts_sorted]
			plt.plot(x, y, marker="o", label=lang)

		plt.xscale("log")
		plt.yscale("log")
		plt.xlabel("n (log scale)")
		plt.ylabel("median runtime (ms, log scale)")
		plt.title(f"Sorting runtime vs n — dist={dist}, algo={algo}")
		plt.legend()
		plt.grid(True, which="both", linestyle="--", linewidth=0.5)

		out = outdir / f"runtime_{algo}_{dist}.png"
		plt.tight_layout()
		plt.savefig(out, dpi=160)
		plt.close()


def plot_speedup(rows: List[dict], outdir: Path, algo: str, baseline_lang: str) -> None:
	# dist -> n -> lang -> median
	by_dist: Dict[str, Dict[int, Dict[str, float]]] = defaultdict(lambda: defaultdict(dict))
	for r in rows:
		if r["algo"] != algo:
			continue
		by_dist[r["distribution"]][r["n"]][r["language"]] = r["median_ms"]

	for dist, by_n in sorted(by_dist.items()):
		# For each lang, collect speedup points where baseline exists
		lang_pts: Dict[str, List[Tuple[int, float]]] = defaultdict(list)

		for n, medians in sorted(by_n.items()):
			if baseline_lang not in medians:
				continue
			base = medians[baseline_lang]
			for lang, m in medians.items():
				# speedup > 1 means faster than baseline
				sp = safe_div(base, m)
				lang_pts[lang].append((n, sp))

		# If baseline missing everywhere, skip
		if not lang_pts:
			continue

		plt.figure()
		for lang, pts in sorted(lang_pts.items()):
			pts_sorted = sorted(pts, key=lambda x: x[0])
			x = [p[0] for p in pts_sorted]
			y = [p[1] for p in pts_sorted]
			plt.plot(x, y, marker="o", label=lang)

		plt.xscale("log")
		plt.xlabel("n (log scale)")
		plt.ylabel(f"speedup vs {baseline_lang} (baseline_median / lang_median)")
		plt.title(f"Speedup vs {baseline_lang} — dist={dist}, algo={algo}")
		plt.axhline(1.0, linewidth=1.0)
		plt.legend()
		plt.grid(True, which="both", linestyle="--", linewidth=0.5)

		out = outdir / f"speedup_vs_{baseline_lang}_{algo}_{dist}.png"
		plt.tight_layout()
		plt.savefig(out, dpi=160)
		plt.close()


def plot_variability(rows: List[dict], outdir: Path, algo: str) -> None:
	# dist -> lang -> list[(n, iqr/median)]
	by_dist: Dict[str, Dict[str, List[Tuple[int, float]]]] = defaultdict(lambda: defaultdict(list))
	for r in rows:
		if r["algo"] != algo:
			continue
		rel = safe_div(r["iqr_ms"], r["median_ms"])
		by_dist[r["distribution"]][r["language"]].append((r["n"], rel))

	for dist, by_lang in sorted(by_dist.items()):
		plt.figure()
		for lang, pts in sorted(by_lang.items()):
			pts_sorted = sorted(pts, key=lambda x: x[0])
			x = [p[0] for p in pts_sorted]
			y = [p[1] for p in pts_sorted]
			plt.plot(x, y, marker="o", label=lang)

		plt.xscale("log")
		plt.xlabel("n (log scale)")
		plt.ylabel("relative variability (IQR / median)")
		plt.title(f"Stability (IQR/median) vs n — dist={dist}, algo={algo}")
		plt.legend()
		plt.grid(True, which="both", linestyle="--", linewidth=0.5)

		out = outdir / f"variability_{algo}_{dist}.png"
		plt.tight_layout()
		plt.savefig(out, dpi=160)
		plt.close()


def main() -> None:
	ap = argparse.ArgumentParser()
	ap.add_argument("--summary", default="results/summary.csv", help="Path to summary.csv")
	ap.add_argument("--outdir", default="results/plots", help="Output directory for plots")
	ap.add_argument("--algo", default="builtin", help="Algorithm name to plot (e.g., builtin)")
	ap.add_argument("--baseline", default="cpp", help="Baseline language for speedup plots (e.g., cpp, rust)")
	args = ap.parse_args()

	summary_path = Path(args.summary)
	if not summary_path.exists():
		raise SystemExit(f"Missing {summary_path}. Run scripts/summarize.py first.")

	outdir = Path(args.outdir)
	outdir.mkdir(parents=True, exist_ok=True)

	rows = read_summary(summary_path)

	plot_runtime(rows, outdir, args.algo)
	plot_speedup(rows, outdir, args.algo, args.baseline)
	plot_variability(rows, outdir, args.algo)

	print(f"Wrote plots to {outdir}")


if __name__ == "__main__":
	main()
