using System;
using System.Buffers.Binary;
using System.Globalization;
using System.IO;
using System.Linq;

static void UsageAndExit()
{
	Console.Error.WriteLine(
@"Usage:
  dotnet run -c Release -- --dataset <path> [--algo builtin] [--warmup N] [--reps N] [--out <csv>] [--no-validate]

Example:
  dotnet run -c Release -- --dataset datasets/ints/random_n100000_seed1.bin --warmup 5 --reps 30 --out results/raw.csv
");
	Environment.Exit(2);
}

static string NowIsoLocal() =>
	DateTime.Now.ToString("yyyy-MM-dd'T'HH:mm:ss", CultureInfo.InvariantCulture);

static string InferDistribution(string datasetPath)
{
	var name = Path.GetFileName(datasetPath);
	var idx = name.IndexOf("_n", StringComparison.Ordinal);
	return idx > 0 ? name.Substring(0, idx) : "unknown";
}

static int[] ReadBinInt32LE(string path)
{
	var bytes = File.ReadAllBytes(path);
	if (bytes.Length < 4) throw new Exception("File too small (missing n header)");

	uint n = BinaryPrimitives.ReadUInt32LittleEndian(bytes.AsSpan(0, 4));
	checked
	{
		int ni = (int)n;
		int expected = 4 + ni * 4;
		if (bytes.Length != expected)
			throw new Exception($"Expected {expected} bytes total, got {bytes.Length}");

		var values = new int[ni];
		var span = bytes.AsSpan(4);
		for (int i = 0; i < ni; i++)
			values[i] = BinaryPrimitives.ReadInt32LittleEndian(span.Slice(i * 4, 4));
		return values;
	}
}

static bool IsSortedNonDecreasing(int[] a)
{
	for (int i = 0; i + 1 < a.Length; i++)
		if (a[i] > a[i + 1]) return false;
	return true;
}

static void EnsureParentDir(string path)
{
	var dir = Path.GetDirectoryName(Path.GetFullPath(path));
	if (!string.IsNullOrEmpty(dir)) Directory.CreateDirectory(dir);
}

static bool FileExists(string path) => File.Exists(path);

static void AppendRow(string csvPath, string[] row)
{
	EnsureParentDir(csvPath);
	bool newFile = !FileExists(csvPath);

	using var fs = new FileStream(csvPath, FileMode.Append, FileAccess.Write, FileShare.Read);
	using var sw = new StreamWriter(fs);

	if (newFile)
	{
		sw.WriteLine(string.Join(",",
			"timestamp_iso","task","language","language_version","algo","dataset_file",
			"distribution","n","warmup_runs","rep_idx","time_ms","ok"
		));
	}

	sw.WriteLine(string.Join(",", row));
}

string? dataset = null;
string algo = "builtin";
int warmup = 5;
int reps = 30;
string outCsv = "results/raw.csv";
bool validate = true;

// Parse args
for (int i = 0; i < args.Length; i++)
{
	var arg = args[i];
	string NeedValue()
	{
		if (++i >= args.Length) UsageAndExit();
		return args[i];
	}

	if (arg == "--dataset") dataset = NeedValue();
	else if (arg == "--algo") algo = NeedValue();
	else if (arg == "--warmup") warmup = int.Parse(NeedValue(), CultureInfo.InvariantCulture);
	else if (arg == "--reps") reps = int.Parse(NeedValue(), CultureInfo.InvariantCulture);
	else if (arg == "--out") outCsv = NeedValue();
	else if (arg == "--no-validate") validate = false;
	else { Console.Error.WriteLine($"Unknown arg: {arg}"); UsageAndExit(); }
}

if (string.IsNullOrWhiteSpace(dataset)) { Console.Error.WriteLine("--dataset is required"); UsageAndExit(); }
if (warmup < 0 || reps <= 0) { Console.Error.WriteLine("warmup must be >= 0 and reps must be > 0"); Environment.Exit(2); }
if (algo != "builtin") { Console.Error.WriteLine("only --algo builtin is supported right now"); Environment.Exit(2); }

var values = ReadBinInt32LE(dataset!);
int n = values.Length;
string dist = InferDistribution(dataset!);

string lang = "csharp";
string langVer = Environment.Version.ToString(); // actual dotnet version also captured by env_info.sh

// Warmup
for (int i = 0; i < warmup; i++)
{
	var tmp = (int[])values.Clone();
	Array.Sort(tmp);
}

// Measured
for (int rep = 0; rep < reps; rep++)
{
	var tmp = (int[])values.Clone();
	long t0 = System.Diagnostics.Stopwatch.GetTimestamp();
	Array.Sort(tmp);
	long t1 = System.Diagnostics.Stopwatch.GetTimestamp();

	double timeMs = (t1 - t0) * 1000.0 / System.Diagnostics.Stopwatch.Frequency;
	bool ok = validate ? IsSortedNonDecreasing(tmp) : true;

	var row = new[]
	{
		NowIsoLocal(),
		"sort",
		lang,
		langVer,
		algo,
		dataset,
		dist,
		n.ToString(CultureInfo.InvariantCulture),
		warmup.ToString(CultureInfo.InvariantCulture),
		rep.ToString(CultureInfo.InvariantCulture),
		timeMs.ToString("0.000", CultureInfo.InvariantCulture),
		ok ? "true" : "false"
	};

	Console.WriteLine(string.Join(",", row));
	AppendRow(outCsv, row!);
}
