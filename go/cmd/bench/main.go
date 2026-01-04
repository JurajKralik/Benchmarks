package main

import (
	"encoding/binary"
	"encoding/csv"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"sort"
	"strings"
	"time"
)

func inferDistribution(datasetPath string) string {
	base := filepath.Base(datasetPath)
	parts := strings.SplitN(base, "_n", 2)
	if len(parts) > 0 {
		return parts[0]
	}
	return "unknown"
}

func nowISO() string {
	return time.Now().Format("2006-01-02T15:04:05")
}

func ensureParentDir(path string) error {
	return os.MkdirAll(filepath.Dir(path), 0o755)
}

func fileExists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}

func appendRow(csvPath string, row []string) error {
	if err := ensureParentDir(csvPath); err != nil {
		return err
	}
	newFile := !fileExists(csvPath)

	f, err := os.OpenFile(csvPath, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o644)
	if err != nil {
		return err
	}
	defer f.Close()

	w := csv.NewWriter(f)
	defer w.Flush()

	if newFile {
		header := []string{
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
		}
		if err := w.Write(header); err != nil {
			return err
		}
	}

	return w.Write(row)
}

func readBinInt32LE(path string) ([]int32, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()

	var n uint32
	if err := binary.Read(f, binary.LittleEndian, &n); err != nil {
		return nil, fmt.Errorf("read header: %w", err)
	}

	values := make([]int32, n)
	if err := binary.Read(f, binary.LittleEndian, &values); err != nil {
		return nil, fmt.Errorf("read payload: %w", err)
	}

	return values, nil
}

func isSortedNonDecreasing(a []int32) bool {
	for i := 0; i < len(a)-1; i++ {
		if a[i] > a[i+1] {
			return false
		}
	}
	return true
}

func main() {
	dataset := flag.String("dataset", "", "Path to .bin dataset")
	algo := flag.String("algo", "builtin", "Sorting algorithm (builtin)")
	warmup := flag.Int("warmup", 5, "Warmup runs (not recorded)")
	reps := flag.Int("reps", 30, "Measured repetitions")
	out := flag.String("out", "results/raw.csv", "CSV output path")
	noValidate := flag.Bool("no-validate", false, "Disable sortedness validation")
	flag.Parse()

	if *dataset == "" {
		fmt.Fprintln(os.Stderr, "--dataset is required")
		os.Exit(2)
	}
	if *warmup < 0 || *reps <= 0 {
		fmt.Fprintln(os.Stderr, "warmup must be >= 0 and reps must be > 0")
		os.Exit(2)
	}
	if *algo != "builtin" {
		fmt.Fprintln(os.Stderr, "only --algo builtin is supported right now")
		os.Exit(2)
	}

	values, err := readBinInt32LE(*dataset)
	if err != nil {
		fmt.Fprintln(os.Stderr, "read dataset:", err)
		os.Exit(1)
	}

	n := len(values)
	dist := inferDistribution(*dataset)

	lang := "go"
	langVer := runtime.Version()
	validate := !*noValidate

	// Warmup
	for i := 0; i < *warmup; i++ {
		tmp := make([]int32, n)
		copy(tmp, values)
		sort.Slice(tmp, func(i, j int) bool { return tmp[i] < tmp[j] })
	}

	// Measured
	for rep := 0; rep < *reps; rep++ {
		tmp := make([]int32, n)
		copy(tmp, values)

		t0 := time.Now()
		sort.Slice(tmp, func(i, j int) bool { return tmp[i] < tmp[j] })
		elapsed := time.Since(t0)

		ok := true
		if validate {
			ok = isSortedNonDecreasing(tmp)
		}

		timeMs := float64(elapsed.Nanoseconds()) / 1_000_000.0

		row := []string{
			nowISO(),
			"sort",
			lang,
			langVer,
			*algo,
			*dataset,
			dist,
			fmt.Sprintf("%d", n),
			fmt.Sprintf("%d", *warmup),
			fmt.Sprintf("%d", rep),
			fmt.Sprintf("%.3f", timeMs),
			func() string {
				if ok {
					return "true"
				}
				return "false"
			}(),
		}

		fmt.Println(strings.Join(row, ","))
		if err := appendRow(*out, row); err != nil {
			fmt.Fprintln(os.Stderr, "write csv:", err)
			os.Exit(1)
		}
	}
}
