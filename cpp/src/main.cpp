#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <optional>
#include <sstream>
#include <string>
#include <string_view>
#include <vector>
#include <filesystem>

namespace fs = std::filesystem;

struct Args {
	std::string dataset;
	std::string algo{"builtin"};
	int warmup{5};
	int reps{30};
	std::string out{"results/raw.csv"};
	bool validate{true};
};

[[noreturn]] void usage_and_exit() {
	std::cerr <<
R"(Usage:
  bench_cpp --dataset <path> [--algo builtin] [--warmup N] [--reps N] [--out <csv>] [--no-validate]

Example:
  bench_cpp --dataset datasets/ints/random_n100000_seed1.bin --warmup 5 --reps 30 --out results/raw.csv
)";
	std::exit(2);
}

std::string infer_distribution(const std::string& dataset_path) {
	auto base = fs::path(dataset_path).filename().string();
	auto pos = base.find("_n");
	if (pos == std::string::npos) return "unknown";
	return base.substr(0, pos);
}

std::string now_iso_local() {
	// Produce YYYY-MM-DDTHH:MM:SS in local time
	std::time_t t = std::time(nullptr);
	std::tm tm{};
	#if defined(_WIN32)
		localtime_s(&tm, &t);
	#else
		localtime_r(&t, &tm);
	#endif
	std::ostringstream oss;
	oss << std::put_time(&tm, "%Y-%m-%dT%H:%M:%S");
	return oss.str();
}

bool is_sorted_non_decreasing(const std::vector<int32_t>& a) {
	for (size_t i = 0; i + 1 < a.size(); i++) {
		if (a[i] > a[i + 1]) return false;
	}
	return true;
}

std::vector<int32_t> read_bin_int32_le(const std::string& path) {
	std::ifstream f(path, std::ios::binary);
	if (!f) {
		throw std::runtime_error("Failed to open: " + path);
	}

	uint32_t n = 0;
	f.read(reinterpret_cast<char*>(&n), sizeof(n));
	if (!f) throw std::runtime_error("Failed to read header from: " + path);

	// Header written little-endian; most machines are LE. If you care about BE,
	// you'd byte-swap here. (Almost certainly unnecessary.)
	std::vector<int32_t> values(n);
	f.read(reinterpret_cast<char*>(values.data()), static_cast<std::streamsize>(n * sizeof(int32_t)));
	if (!f) {
		throw std::runtime_error("Failed to read payload from: " + path);
	}

	// Ensure EOF (optional strictness)
	char extra;
	if (f.read(&extra, 1)) {
		throw std::runtime_error("File has extra trailing bytes: " + path);
	}

	return values;
}

void ensure_parent_dir(const std::string& out_path) {
	auto p = fs::path(out_path).parent_path();
	if (!p.empty()) fs::create_directories(p);
}

bool file_exists(const std::string& path) {
	return fs::exists(fs::path(path));
}

void append_row(const std::string& csv_path, const std::vector<std::string>& row) {
	ensure_parent_dir(csv_path);
	bool new_file = !file_exists(csv_path);

	std::ofstream f(csv_path, std::ios::app);
	if (!f) throw std::runtime_error("Failed to open output CSV: " + csv_path);

	if (new_file) {
		f << "timestamp_iso,task,language,language_version,algo,dataset_file,distribution,n,warmup_runs,rep_idx,time_ms,ok\n";
	}
	for (size_t i = 0; i < row.size(); i++) {
		if (i) f << ",";
		f << row[i];
	}
	f << "\n";
}

Args parse_args(int argc, char** argv) {
	Args a;
	for (int i = 1; i < argc; i++) {
		std::string_view arg(argv[i]);
		auto need_value = [&](const char* name) -> const char* {
            (void)name;
			if (i + 1 >= argc) usage_and_exit();
			return argv[++i];
		};

		if (arg == "--dataset") a.dataset = need_value("--dataset");
		else if (arg == "--algo") a.algo = need_value("--algo");
		else if (arg == "--warmup") a.warmup = std::stoi(need_value("--warmup"));
		else if (arg == "--reps") a.reps = std::stoi(need_value("--reps"));
		else if (arg == "--out") a.out = need_value("--out");
		else if (arg == "--no-validate") a.validate = false;
		else {
			std::cerr << "Unknown arg: " << arg << "\n";
			usage_and_exit();
		}
	}

	if (a.dataset.empty()) {
		std::cerr << "--dataset is required\n";
		usage_and_exit();
	}
	if (a.warmup < 0 || a.reps <= 0) {
		std::cerr << "warmup must be >= 0 and reps must be > 0\n";
		std::exit(2);
	}
	if (a.algo != "builtin") {
		std::cerr << "only --algo builtin is supported right now\n";
		std::exit(2);
	}
	return a;
}

int main(int argc, char** argv) {
	try {
		Args args = parse_args(argc, argv);

		auto values = read_bin_int32_le(args.dataset);
		const int n = static_cast<int>(values.size());
		const std::string dist = infer_distribution(args.dataset);

		const std::string lang = "cpp";
		const std::string lang_ver = "c++20"; // actual compiler captured in env_info.sh

		// Warmup
		for (int i = 0; i < args.warmup; i++) {
			auto tmp = values;
			std::sort(tmp.begin(), tmp.end());
		}

		// Measured
		for (int rep = 0; rep < args.reps; rep++) {
			auto tmp = values;

			auto t0 = std::chrono::steady_clock::now();
			std::sort(tmp.begin(), tmp.end());
			auto t1 = std::chrono::steady_clock::now();

			double time_ms = std::chrono::duration<double, std::milli>(t1 - t0).count();
			bool ok = args.validate ? is_sorted_non_decreasing(tmp) : true;

			std::vector<std::string> row = {
				now_iso_local(),
				"sort",
				lang,
				lang_ver,
				args.algo,
				args.dataset,
				dist,
				std::to_string(n),
				std::to_string(args.warmup),
				std::to_string(rep),
				([](double v){
					std::ostringstream oss;
					oss << std::fixed << std::setprecision(3) << v;
					return oss.str();
				})(time_ms),
				ok ? "true" : "false"
			};

			// Print + append
			for (size_t i = 0; i < row.size(); i++) {
				if (i) std::cout << ",";
				std::cout << row[i];
			}
			std::cout << "\n";

			append_row(args.out, row);
		}

		return 0;
	} catch (const std::exception& e) {
		std::cerr << "Error: " << e.what() << "\n";
		return 1;
	}
}
