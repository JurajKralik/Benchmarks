package bench;

import java.io.*;
import java.nio.*;
import java.nio.file.*;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.Arrays;

public final class Main {
	private static final DateTimeFormatter TS_FMT = DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss");

	private static final class Args {
		String dataset;
		String algo = "builtin";
		int warmup = 5;
		int reps = 30;
		String out = "results/raw.csv";
		boolean validate = true;
	}

	private static void usageAndExit() {
		System.err.println(
			"Usage:\n" +
			"  java -cp java/out bench.Main --dataset <path> [--algo builtin] [--warmup N] [--reps N] [--out <csv>] [--no-validate]\n\n" +
			"Example:\n" +
			"  java -cp java/out bench.Main --dataset datasets/ints/random_n100000_seed1.bin --warmup 5 --reps 30 --out results/raw.csv\n"
		);
		System.exit(2);
	}

    private static Args parseArgs(String[] argv) {
        Args a = new Args();

        for (int i = 0; i < argv.length; i++) {
            String arg = argv[i];

            if ("--dataset".equals(arg)) {
                if (++i >= argv.length) usageAndExit();
                a.dataset = argv[i];

            } else if ("--algo".equals(arg)) {
                if (++i >= argv.length) usageAndExit();
                a.algo = argv[i];

            } else if ("--warmup".equals(arg)) {
                if (++i >= argv.length) usageAndExit();
                a.warmup = Integer.parseInt(argv[i]);

            } else if ("--reps".equals(arg)) {
                if (++i >= argv.length) usageAndExit();
                a.reps = Integer.parseInt(argv[i]);

            } else if ("--out".equals(arg)) {
                if (++i >= argv.length) usageAndExit();
                a.out = argv[i];

            } else if ("--no-validate".equals(arg)) {
                a.validate = false;

            } else {
                System.err.println("Unknown arg: " + arg);
                usageAndExit();
            }
        }

        if (a.dataset == null || a.dataset.isEmpty()) {
            System.err.println("--dataset is required");
            usageAndExit();
        }
        if (a.warmup < 0 || a.reps <= 0) {
            System.err.println("warmup must be >= 0 and reps must be > 0");
            System.exit(2);
        }
        if (!"builtin".equals(a.algo)) {
            System.err.println("only --algo builtin is supported right now");
            System.exit(2);
        }

        return a;
    }

	private static String nowIsoLocal() {
		return LocalDateTime.now().format(TS_FMT);
	}

	private static String inferDistribution(String datasetPath) {
		String name = Paths.get(datasetPath).getFileName().toString();
		int idx = name.indexOf("_n");
		if (idx <= 0) return "unknown";
		return name.substring(0, idx);
	}

	private static int[] readBinInt32LE(String path) throws IOException {
		byte[] all = Files.readAllBytes(Paths.get(path));
		if (all.length < 4) throw new IOException("File too small (missing n header): " + path);

		ByteBuffer bb = ByteBuffer.wrap(all).order(ByteOrder.LITTLE_ENDIAN);
		long nUnsigned = Integer.toUnsignedLong(bb.getInt());
		if (nUnsigned > Integer.MAX_VALUE) throw new IOException("n too large: " + nUnsigned);
		int n = (int)nUnsigned;

		int expected = 4 + n * 4;
		if (all.length != expected) {
			throw new IOException("Expected " + expected + " bytes total, got " + all.length + " (" + path + ")");
		}

		int[] values = new int[n];
		for (int i = 0; i < n; i++) {
			values[i] = bb.getInt();
		}
		return values;
	}

	private static boolean isSortedNonDecreasing(int[] a) {
		for (int i = 0; i + 1 < a.length; i++) {
			if (a[i] > a[i + 1]) return false;
		}
		return true;
	}

	private static void ensureParentDir(String outPath) throws IOException {
		Path p = Paths.get(outPath).toAbsolutePath().getParent();
		if (p != null) Files.createDirectories(p);
	}

	private static boolean fileExists(String p) {
		return Files.exists(Paths.get(p));
	}

	private static void appendRow(String csvPath, String[] row) throws IOException {
		ensureParentDir(csvPath);
		boolean newFile = !fileExists(csvPath);

		try (FileWriter fw = new FileWriter(csvPath, true);
		     BufferedWriter bw = new BufferedWriter(fw);
		     PrintWriter out = new PrintWriter(bw)) {

			if (newFile) {
				out.println(String.join(",",
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
					"ok"
				));
			}
			out.println(String.join(",", row));
		}
	}

	public static void main(String[] argv) throws Exception {
		Args args = parseArgs(argv);

		int[] values = readBinInt32LE(args.dataset);
		int n = values.length;
		String dist = inferDistribution(args.dataset);

		String lang = "java";
		String langVer = System.getProperty("java.version");

		// Warmup (important for JIT)
		for (int i = 0; i < args.warmup; i++) {
			int[] tmp = Arrays.copyOf(values, n);
			Arrays.sort(tmp);
		}

		// Measured runs
		for (int rep = 0; rep < args.reps; rep++) {
			int[] tmp = Arrays.copyOf(values, n);

			long t0 = System.nanoTime();
			Arrays.sort(tmp);
			long t1 = System.nanoTime();

			double timeMs = (t1 - t0) / 1_000_000.0;

			boolean ok = true;
			if (args.validate) ok = isSortedNonDecreasing(tmp);

			String[] row = new String[] {
				nowIsoLocal(),
				"sort",
				lang,
				langVer,
				args.algo,
				args.dataset,
				dist,
				Integer.toString(n),
				Integer.toString(args.warmup),
				Integer.toString(rep),
				String.format(java.util.Locale.ROOT, "%.3f", timeMs),
				ok ? "true" : "false"
			};

			System.out.println(String.join(",", row));
			appendRow(args.out, row);
		}
	}
}
