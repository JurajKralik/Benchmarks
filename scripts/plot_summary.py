#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path
from statistics import median, mean
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
			row["n"] = int(row["n"])
			row["runs"] = int(row["runs"])
			row["median_ms"] = float(row["median_ms"])
			row["iqr_ms"] = float(row["iqr_ms"])
			row["mean_ms"] = float(row["mean_ms"])
			row["std_ms"] = float(row["std_ms"])
			rows.append(row)
		return rows


def safe_div(a: float, b: float) -> float:
	return float("nan") if b == 0.0 else a / b


def geom_mean(vals: List[float]) -> float:
	"""
	Geometric mean for positive values.
	We ignore non-positive and NaN values (shouldn't happen for runtimes).
	"""
	clean = [v for v in vals if v > 0.0 and math.isfinite(v)]
	if not clean:
		return float("nan")
	return math.exp(sum(math.log(v) for v in clean) / len(clean))


def plot_runtime_by_distribution(rows: List[dict], outdir: Path, algo: str) -> None:
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


def plot_speedup_by_distribution(rows: List[dict], outdir: Path, algo: str, baseline_lang: str) -> None:
	by_dist: Dict[str, Dict[int, Dict[str, float]]] = defaultdict(lambda: defaultdict(dict))
	for r in rows:
		if r["algo"] != algo:
			continue
		by_dist[r["distribution"]][r["n"]][r["language"]] = r["median_ms"]

	for dist, by_n in sorted(by_dist.items()):
		lang_pts: Dict[str, List[Tuple[int, float]]] = defaultdict(list)

		for n, medians in sorted(by_n.items()):
			if baseline_lang not in medians:
				continue
			base = medians[baseline_lang]
			for lang, m in medians.items():
				sp = safe_div(base, m)  # >1 means faster than baseline
				lang_pts[lang].append((n, sp))

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


def plot_variability_by_distribution(rows: List[dict], outdir: Path, algo: str) -> None:
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


def plot_runtime_agg_geom(rows: List[dict], outdir: Path, algo: str) -> None:
	"""
	Aggregate across distributions using geometric mean of medians.
	One curve per language.
	"""
	# lang -> n -> list[median_ms across dists]
	acc: Dict[str, Dict[int, List[float]]] = defaultdict(lambda: defaultdict(list))

	for r in rows:
		if r["algo"] != algo:
			continue
		acc[r["language"]][r["n"]].append(r["median_ms"])

	plt.figure()
	for lang, by_n in sorted(acc.items()):
		pts = []
		for n, vals in by_n.items():
			gm = geom_mean(vals)
			if math.isfinite(gm):
				pts.append((n, gm))
		if not pts:
			continue
		pts.sort(key=lambda x: x[0])
		x = [p[0] for p in pts]
		y = [p[1] for p in pts]
		plt.plot(x, y, marker="o", label=lang)

	plt.xscale("log")
	plt.yscale("log")
	plt.xlabel("n (log scale)")
	plt.ylabel("geom. mean median runtime across dists (ms, log scale)")
	plt.title(f"Aggregate runtime vs n (geometric mean over distributions) — algo={algo}")
	plt.legend()
	plt.grid(True, which="both", linestyle="--", linewidth=0.5)

	out = outdir / f"runtime_agg_geom_{algo}.png"
	plt.tight_layout()
	plt.savefig(out, dpi=160)
	plt.close()


def plot_speedup_agg_geom(rows: List[dict], outdir: Path, algo: str, baseline_lang: str) -> None:
	"""
	Aggregate speedup using geometric mean across distributions:
	1) compute geom mean runtime per (lang, n) over distributions
	2) speedup(lang,n) = gm(baseline,n) / gm(lang,n)
	"""
	acc: Dict[str, Dict[int, List[float]]] = defaultdict(lambda: defaultdict(list))
	for r in rows:
		if r["algo"] != algo:
			continue
		acc[r["language"]][r["n"]].append(r["median_ms"])

	if baseline_lang not in acc:
		print(f"[warn] baseline language '{baseline_lang}' not found in summary; skipping aggregate speedup plot")
		return

	# gm per (lang,n)
	gm_rt: Dict[str, Dict[int, float]] = defaultdict(dict)
	for lang, by_n in acc.items():
		for n, vals in by_n.items():
			gm_rt[lang][n] = geom_mean(vals)

	plt.figure()
	for lang, by_n in sorted(gm_rt.items()):
		pts = []
		for n, gm in by_n.items():
			base = gm_rt[baseline_lang].get(n)
			if base is None or not math.isfinite(base) or not math.isfinite(gm) or gm == 0.0:
				continue
			pts.append((n, base / gm))
		if not pts:
			continue
		pts.sort(key=lambda x: x[0])
		x = [p[0] for p in pts]
		y = [p[1] for p in pts]
		plt.plot(x, y, marker="o", label=lang)

	plt.xscale("log")
	plt.xlabel("n (log scale)")
	plt.ylabel(f"geom-mean speedup vs {baseline_lang} (baseline_gm / lang_gm)")
	plt.title(f"Aggregate speedup vs {baseline_lang} (geometric mean over distributions) — algo={algo}")
	plt.axhline(1.0, linewidth=1.0)
	plt.legend()
	plt.grid(True, which="both", linestyle="--", linewidth=0.5)

	out = outdir / f"speedup_agg_geom_vs_{baseline_lang}_{algo}.png"
	plt.tight_layout()
	plt.savefig(out, dpi=160)
	plt.close()


def main() -> None:
	ap = argparse.ArgumentParser()
	ap.add_argument("--summary", default="results/summary.csv", help="Path to summary.csv")
	ap.add_argument("--outdir", default="results/plots", help="Output directory for plots")
	ap.add_argument("--algo", default="builtin", help="Algorithm name to plot (e.g., builtin)")
	ap.add_argument("--baseline", default="cpp", help="Baseline language for speedup plots (e.g., cpp, rust)")
	ap.add_argument("--skip-per-dist", action="store_true", help="Only generate aggregate plots")
	args = ap.parse_args()

	summary_path = Path(args.summary)
	if not summary_path.exists():
		raise SystemExit(f"Missing {summary_path}. Run scripts/summarize.py first.")

	outdir = Path(args.outdir)
	outdir.mkdir(parents=True, exist_ok=True)

	rows = read_summary(summary_path)

	# Per-distribution plots (small multiples)
	if not args.skip_per_dist:
		plot_runtime_by_distribution(rows, outdir, args.algo)
		plot_speedup_by_distribution(rows, outdir, args.algo, args.baseline)
		plot_variability_by_distribution(rows, outdir, args.algo)

	# Aggregate plots (single summary)
	plot_runtime_agg_geom(rows, outdir, args.algo)
	plot_speedup_agg_geom(rows, outdir, args.algo, args.baseline)

	print(f"Wrote plots to {outdir}")


if __name__ == "__main__":
	main()
