import * as fs from "node:fs";
import * as path from "node:path";

function usageAndExit(): never {
	console.error(`Usage:
  node --loader ts-node/esm ts/bench_sort.ts --dataset <path> [--algo builtin] [--warmup N] [--reps N] [--out <csv>] [--no-validate]

Example:
  node --loader ts-node/esm ts/bench_sort.ts --dataset datasets/ints/random_n100000_seed1.bin --warmup 5 --reps 30 --out results/raw.csv
`);
	process.exit(2);
}

function nowIsoLocal(): string {
	const d = new Date();
	const pad = (n: number) => String(n).padStart(2, "0");
	return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function inferDistribution(datasetPath: string): string {
	const base = path.basename(datasetPath);
	const idx = base.indexOf("_n");
	return idx > 0 ? base.slice(0, idx) : "unknown";
}

function readBinInt32LE(p: string): Int32Array {
	const buf = fs.readFileSync(p);
	if (buf.length < 4) throw new Error("File too small (missing n header)");
	const n = buf.readUInt32LE(0);
	const expected = 4 + n * 4;
	if (buf.length !== expected) throw new Error(`Expected ${expected} bytes total, got ${buf.length}`);

	const arr = new Int32Array(n);
	let off = 4;
	for (let i = 0; i < n; i++, off += 4) arr[i] = buf.readInt32LE(off);
	return arr;
}

function isSortedNonDecreasing(a: Array<number> | Int32Array): boolean {
	for (let i = 0; i + 1 < a.length; i++) {
		if (a[i]! > a[i + 1]!) return false;
	}
	return true;
}

function ensureParentDir(p: string): void {
	fs.mkdirSync(path.dirname(p), { recursive: true });
}

function fileExists(p: string): boolean {
	try { fs.accessSync(p); return true; } catch { return false; }
}

function appendRow(csvPath: string, row: string[]): void {
	ensureParentDir(csvPath);
	const newFile = !fileExists(csvPath);
	const line = row.join(",") + "\n";
	if (newFile) {
		const header = [
			"timestamp_iso","task","language","language_version","algo","dataset_file",
			"distribution","n","warmup_runs","rep_idx","time_ms","ok"
		].join(",") + "\n";
		fs.appendFileSync(csvPath, header + line);
	} else {
		fs.appendFileSync(csvPath, line);
	}
}

// ---- args ----
let dataset: string | null = null;
let algo = "builtin";
let warmup = 5;
let reps = 30;
let out = "results/raw.csv";
let validate = true;

const argv = process.argv.slice(2);
for (let i = 0; i < argv.length; i++) {
	const arg = argv[i]!;
	const need = (): string => {
		if (++i >= argv.length) usageAndExit();
		return argv[i]!;
	};

	if (arg === "--dataset") dataset = need();
	else if (arg === "--algo") algo = need();
	else if (arg === "--warmup") warmup = Number(need());
	else if (arg === "--reps") reps = Number(need());
	else if (arg === "--out") out = need();
	else if (arg === "--no-validate") validate = false;
	else { console.error(`Unknown arg: ${arg}`); usageAndExit(); }
}

if (!dataset) { console.error("--dataset is required"); usageAndExit(); }
if (warmup < 0 || reps <= 0) { console.error("warmup must be >= 0 and reps must be > 0"); process.exit(2); }
if (algo !== "builtin") { console.error("only --algo builtin is supported right now"); process.exit(2); }

const values = readBinInt32LE(dataset);
const n = values.length;
const dist = inferDistribution(dataset);

const lang = "ts";
const langVer = process.version;

// Warmup (TypeScript still runs on Node/V8, but warmup helps)
for (let i = 0; i < warmup; i++) {
	const arr = Array.from(values);
	arr.sort((a, b) => a - b);
}

// Measured
for (let rep = 0; rep < reps; rep++) {
	const arr = Array.from(values);

	const t0 = process.hrtime.bigint();
	arr.sort((a, b) => a - b);
	const t1 = process.hrtime.bigint();

	const timeMs = Number(t1 - t0) / 1_000_000.0;
	const ok = validate ? isSortedNonDecreasing(arr) : true;

	const row = [
		nowIsoLocal(),
		"sort",
		lang,
		langVer,
		algo,
		dataset,
		dist,
		String(n),
		String(warmup),
		String(rep),
		timeMs.toFixed(3),
		ok ? "true" : "false",
	];

	console.log(row.join(","));
	appendRow(out, row);
}
