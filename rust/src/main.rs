use std::env;
use std::fs::{self, OpenOptions};
use std::io::{self, Read, Write};
use std::path::Path;
use std::time::Instant;

fn usage_and_exit() -> ! {
	eprintln!(
		"Usage:
  cargo run -- --dataset <path> [--algo builtin] [--warmup N] [--reps N] [--out <csv>] [--no-validate]

Example:
  cargo run -- --dataset ../datasets/ints/random_n100000_seed1.bin --warmup 5 --reps 30 --out ../results/raw.csv"
	);
	std::process::exit(2);
}

#[derive(Clone)]
struct Args {
	dataset: String,
	algo: String,
	warmup: usize,
	reps: usize,
	out: String,
	validate: bool,
}

fn parse_args() -> Args {
	let mut dataset: Option<String> = None;
	let mut algo = "builtin".to_string();
	let mut warmup: usize = 5;
	let mut reps: usize = 30;
	let mut out = "results/raw.csv".to_string();
	let mut validate = true;

	let mut it = env::args().skip(1);
	while let Some(arg) = it.next() {
		match arg.as_str() {
			"--dataset" => {
				dataset = it.next();
				if dataset.is_none() {
					usage_and_exit();
				}
			}
			"--algo" => {
				algo = it.next().unwrap_or_else(|| usage_and_exit());
			}
			"--warmup" => {
				warmup = it.next().unwrap_or_else(|| usage_and_exit()).parse().unwrap_or_else(|_| usage_and_exit());
			}
			"--reps" => {
				reps = it.next().unwrap_or_else(|| usage_and_exit()).parse().unwrap_or_else(|_| usage_and_exit());
			}
			"--out" => {
				out = it.next().unwrap_or_else(|| usage_and_exit());
			}
			"--no-validate" => {
				validate = false;
			}
			_ => {
				eprintln!("Unknown arg: {}", arg);
				usage_and_exit();
			}
		}
	}

	let dataset = dataset.unwrap_or_else(|| usage_and_exit());

	if warmup > 1_000_000 || reps == 0 {
		eprintln!("warmup must be >= 0 and reps must be > 0");
		std::process::exit(2);
	}
	if algo != "builtin" {
		eprintln!("only --algo builtin is supported right now");
		std::process::exit(2);
	}

	Args { dataset, algo, warmup, reps, out, validate }
}

fn infer_distribution(dataset_path: &str) -> String {
	let base = Path::new(dataset_path)
		.file_name()
		.map(|s| s.to_string_lossy().to_string())
		.unwrap_or_else(|| "unknown".to_string());

	// expects: "<dist>_n<...>_seed<...>.bin"
	base.split("_n").next().unwrap_or("unknown").to_string()
}

fn now_iso_local() -> String {
	use chrono::Local;
	Local::now().format("%Y-%m-%dT%H:%M:%S").to_string()
}

fn ensure_parent_dir(path: &str) -> io::Result<()> {
	if let Some(parent) = Path::new(path).parent() {
		if !parent.as_os_str().is_empty() {
			fs::create_dir_all(parent)?;
		}
	}
	Ok(())
}

fn file_exists(path: &str) -> bool {
	Path::new(path).exists()
}

fn append_row(csv_path: &str, row: &[String]) -> io::Result<()> {
	ensure_parent_dir(csv_path)?;
	let new_file = !file_exists(csv_path);

	let mut f = OpenOptions::new()
		.create(true)
		.append(true)
		.open(csv_path)?;

	if new_file {
		let header = [
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
		];
		writeln!(f, "{}", header.join(","))?;
	}

	writeln!(f, "{}", row.join(","))?;
	Ok(())
}

fn read_bin_int32_le(path: &str) -> io::Result<Vec<i32>> {
	let mut f = fs::File::open(path)?;
	let mut buf = Vec::new();
	f.read_to_end(&mut buf)?;

	if buf.len() < 4 {
		return Err(io::Error::new(io::ErrorKind::InvalidData, "File too small (missing n header)"));
	}

	let n = u32::from_le_bytes([buf[0], buf[1], buf[2], buf[3]]) as usize;
	let expected = 4 + n * 4;
	if buf.len() != expected {
		return Err(io::Error::new(
			io::ErrorKind::InvalidData,
			format!("Expected {} bytes total, got {}", expected, buf.len()),
		));
	}

	let mut out = Vec::with_capacity(n);
	let mut i = 4;
	for _ in 0..n {
		let v = i32::from_le_bytes([buf[i], buf[i + 1], buf[i + 2], buf[i + 3]]);
		out.push(v);
		i += 4;
	}
	Ok(out)
}

fn is_sorted_non_decreasing(a: &[i32]) -> bool {
	a.windows(2).all(|w| w[0] <= w[1])
}

fn rust_version() -> String {
	// No stable std API to query rustc version at runtime without external crates/build scripts.
	// We'll output "rust" + package version. Good enough for benchmarks, and you can record rustc in env_info.
	format!("rust/{}", env!("CARGO_PKG_VERSION"))
}

fn main() -> io::Result<()> {
	let args = parse_args();

	let values = read_bin_int32_le(&args.dataset)?;
	let n = values.len();
	let dist = infer_distribution(&args.dataset);

	let lang = "rust".to_string();
	let lang_ver = rust_version();

	// Warmup
	for _ in 0..args.warmup {
		let mut tmp = values.clone();
		tmp.sort_unstable();
	}

	// Measured
	for rep in 0..args.reps {
		let mut tmp = values.clone();

		let t0 = Instant::now();
		tmp.sort_unstable();
		let elapsed = t0.elapsed();
		let time_ms = (elapsed.as_nanos() as f64) / 1_000_000.0;

		let ok = if args.validate {
			is_sorted_non_decreasing(&tmp)
		} else {
			true
		};

		let row = vec![
			now_iso_local(),
			"sort".to_string(),
			lang.clone(),
			lang_ver.clone(),
			args.algo.clone(),
			args.dataset.clone(),
			dist.clone(),
			n.to_string(),
			args.warmup.to_string(),
			rep.to_string(),
			format!("{:.3}", time_ms),
			if ok { "true".to_string() } else { "false".to_string() },
		];

		println!("{}", row.join(","));
		append_row(&args.out, &row)?;
	}

	Ok(())
}
