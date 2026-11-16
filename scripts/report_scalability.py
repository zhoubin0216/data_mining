"""Render measured benchmark data into a report and a standard scientific plot."""

import json
import math
import os
import tempfile
from pathlib import Path
from benchmark_scalability import persist

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "scalability"


def table(headers, rows):
    return "\n".join(["| " + " | ".join(headers) + " |",
                      "| " + " | ".join(["---"] * len(headers)) + " |"] +
                     ["| " + " | ".join(map(str, row)) + " |" for row in rows])


def main():
    data = json.loads((OUT / "benchmark.json").read_text())
    if data["status"] != "complete":
        raise ValueError("Benchmark must complete before reporting")
    # Apply the requested algorithm-only boundary to the separately recorded
    # measurements, including runs collected before that clarification.
    persist(data)
    sizes = data["configuration"]["sizes"]
    summary = data["summary"]
    def median(n, key):
        return summary[str(n)]["seconds"][key]["median"]
    def pct(x):
        return "undefined" if x is None else "%.2f%%" % (100 * x)
    stage_keys = ["setup", "shingling", "minhash", "lsh", "candidate_signature_comparison"]
    rows = []
    for n in sizes:
        s = summary[str(n)]
        rows.append([n] + ["%.6f" % median(n, key) for key in stage_keys] +
                    ["%.6f" % median(n, "algorithm_total")])
    stages = table(["N", "Setup", "Shingling", "MinHash", "LSH", "Signature compare", "Algorithm total"], rows)
    comparison = table(["N", "Algorithm median (s)", "Minimum (s)", "Maximum (s)", "Median ms/document"], [
        [n] + ["%.4f" % summary[str(n)]["seconds"]["algorithm_total"][x] for x in ("median", "min", "max")] +
        ["%.3f" % (1000 * median(n, "algorithm_total") / n)] for n in sizes])
    quality_rows, optional_rows = [], []
    for n in sizes:
        q = summary[str(n)]["quality"]
        quality_rows.append([n, q["all_possible_pairs"], q["true_similar_pairs"], q["lsh_candidates"],
                             q["candidates"]["tp"], q["candidates"]["fp"], q["candidates"]["fn"],
                             pct(q["candidates"]["precision"]), pct(q["candidates"]["recall"]), pct(q["candidate_reduction"])])
        optional_rows.append([n, q["minhash_threshold_pairs"], pct(q["minhash_filtered"]["precision"]),
                              pct(q["minhash_filtered"]["recall"]), q["minhash_filtered"]["fn"]])
    quality = table(["N", "All pairs", "Exact positives", "Candidates", "TP", "FP", "FN", "Candidate precision", "Recall", "Pair reduction"], quality_rows)
    optional = table(["N", "MinHash-filtered candidates", "Precision", "Recall", "Missed true pairs"], optional_rows)
    corpus = table(["N", "Real texts", "Artificial variants", "Source families", "Total words", "Total unique shingles (summed over documents)"], [
        [n, n // 5, n * 4 // 5, n // 5, summary[str(n)]["total_words"], summary[str(n)]["total_shingles"]] for n in sizes])
    largest = sizes[-1]
    source_manifest = json.loads((ROOT / "data" / "election_2026" / "manifests" / ("scale_%d.json" % largest)).read_text())
    families = {x["id"]: x["family_id"] for x in source_manifest["documents"]}
    true_details = json.loads((OUT / ("pairs_%d.json" % largest)).read_text())["true_pairs"]
    cross_family = sum(families[x["left"]] != families[x["right"]] for x in true_details)
    fraction = median(largest, "minhash") / median(largest, "algorithm_total")
    growth = []
    for smaller, larger in zip(sizes, sizes[1:]):
        ratio = median(larger, "algorithm_total") / median(smaller, "algorithm_total")
        growth.append("- %d to %d documents: algorithm-only time increased %.2fx for a %.0fx input increase (two-point exponent %.2f)."
                      % (smaller, larger, ratio, larger / smaller, math.log(ratio) / math.log(larger / smaller)))
    conclusion = "All reported scalability times exclude exact Jaccard and evaluation. Candidate reduction is reported separately as an algorithm property, not as a measured end-to-end speedup."
    env = data["environment"]
    report = f'''# Scalability evaluation: finding similar news documents

## Objective and similarity definition

We measured execution time for 10, 100, and 1,000 documents, as required by the assignment.
Two documents are similar exactly when the Jaccard similarity of their hashed character-shingle
sets is at least **s = 0.8**. Configuration: **k=10**, **120 MinHash components**, **seed=42**,
and **12 LSH bands × 10 rows**. Parameters and corpora were fixed before timing; the algorithms
were not retuned to improve the measured results.

## Data and reproducibility

All corpora concern the November 2026 US midterm election and its immediate coverage.
The largest corpus contains 200 real news texts (44 standalone articles and 156 live-blog updates)
and 800 explicitly labeled sentence-edit variants. These are **not 1,000 independent news articles**.
Each original has four variants; the nested smaller sets contain complete source families.
CBS accounts for most texts. The real-only 20-article corpus is a separate functional test,
not one of the timed scale corpora.

{corpus}

Text lengths were balanced approximately across scales. Length tails, publisher mix, and
natural cross-family reuse still differ. The datasets are nested, not independent samples or
train/test splits. Details and source attribution: [dataset documentation](data/election_2026/README.md).

## Measurement protocol

- Three sequential measured repetitions at every size, preceded by one excluded 10-document warm-up.
- Wall-clock timing uses `time.perf_counter()`. Reported values are medians; raw repetitions and ranges are preserved.
- Every trial rereads documents and rebuilds shingles, signatures, and LSH buckets. No precomputed signatures are reused across trials.
- Manifest/checksum validation runs before timing. Files are loaded outside the algorithm timer; neither cold-disk nor warm-cache file-reading latency enters the reported algorithm time.
- Execution order is 10, 100, 1,000, repeated three times. Other host activity, scheduling, and CPU frequency are not controlled.
- **Algorithm time = setup + shingling + MinHash + LSH + candidate signature comparison.** Signature comparison is the assignment's CompareSignatures stage, using only candidate signatures.
- **Excluded: file reading, every exact Jaccard calculation (including candidate verification), ground-truth construction, precision/recall calculation, writing, printing, and plotting.**
- Exact Jaccard is computed after the algorithm stages solely for offline quality evaluation. Full-corpus ground truth includes cross-family pairs. MinHash-filtered candidates and LSH candidates are evaluated separately.
- Raw files retain separately measured validation and I/O durations as auxiliary diagnostics. They are never added to the reported algorithm time. The requested boundary was applied by summing the recorded algorithm stages per trial, without estimating or subtracting an assumed validation cost.
- Downloading, generation, validation and reporting are excluded. The benchmark does not execute the diagnostic all-pairs signature comparison used by the interactive `pipeline.py`.

Environment: Python {env['python'].splitlines()[0]}; {env['system']} {env['release']};
process architecture {env['machine']}; {env['logical_cpus']} logical CPUs reported, but a single
Python process with no explicit parallelism. Hardware model and RAM were not available from
the sandbox. UTC timestamps, exact configuration, and algorithm/input SHA-256 values are
stored in `results/scalability/benchmark.json`.

## Execution time

All numbers in the stage table are seconds, median of three measurements.

{stages}

Each stage median is calculated independently; their sum need not equal the median total.
Totals are calculated per trial before taking the median. Min/max are observed ranges,
not confidence intervals.

{comparison}

The last column normalizes algorithm time by document count. No exact-Jaccard validation
or file I/O is included in either the tables or the figure.

![Execution time versus corpus size](results/scalability/execution_time.png)

## Detection quality against exhaustive Jaccard

{quality}

TP = candidates whose exact Jaccard is at least 0.8; FP = candidates below 0.8;
FN = true similar pairs not proposed by LSH. Pair reduction compares candidate count
with N(N−1)/2 possible pairs. It is a reduction in exact pair comparisons, not a wall-time speedup.
Offline exact verification would remove all candidate false positives; the verified subset
has precision 1.0, while recall remains the LSH recall shown above. This verification
is excluded from algorithm timing.
Detailed positives, candidates, and missed pairs are in `results/scalability/pairs_N.json`.
At N={largest}, {cross_family} true positive pairs connect different source families;
using only planted within-family labels would miss these ground-truth relationships.

For comparison, filtering candidates solely with the MinHash estimate ≥ 0.8 gives:

{optional}

This optional filtering can add false negatives or retain false positives because MinHash
is an estimate. Repeating timings with the same seed leaves all candidate counts and quality
metrics identical; these repetitions do not measure variability over random hash families.

## Interpretation

{conclusion}

At N={largest}, MinHash construction accounts for approximately {fraction:.1%} of median
algorithm time. The current implementation evaluates each of the 120 arithmetic hash functions
for every unique shingle in Python, making signature construction the dominant cost.

{chr(10).join(growth)}

With average shingle count M and signature length H fixed, signature construction is O(NMH).
Exhaustive exact comparison is O(N²M). LSH bucket insertion reads O(NH) signature components,
but pair enumeration costs the sum of binomial(bucket size, 2) over buckets, including repeated
pairs across bands. Candidate deduplication and exact verification then depend on the emitted
pairs and C unique candidates. Candidate signature comparison costs O(CH). Exact candidate
verification would cost O(CM), but is outside the reported timing. Worst-case LSH work remains
quadratic for large matching buckets.
Only three sizes and three timing repetitions were measured, so the observed slopes do not
prove an asymptotic complexity or predict a crossover at larger N.

Under the ideal independent MinHash model, the probability of retrieving a pair with true
similarity j is 1−(1−j^10)^12, approximately 0.744 at j=0.8. The affine hash family used here
approximates random permutations; the formula is a design model, not a strict guarantee for
this fixed seed. Exact verification cannot recover pairs missed during candidate generation.

## Reproduce

```bash
python3 scripts/dataset_archive.py import --archive /path/to/election_2026_1000.zip
python3 scripts/build_election_dataset.py --verify-only
python3 scripts/benchmark_scalability.py --repeats 3
python3 scripts/report_scalability.py
```

The benchmark uses the standard library and existing algorithm modules. The optional report
figure requires matplotlib (`python3 -m pip install matplotlib`). The fixed 1,000-document
ZIP is distributed separately through a cloud drive; texts and archives are Git-ignored.
Download from the [Google Drive dataset folder](https://drive.google.com/drive/folders/12gJchd3Gv5oO9GsbdZrfX5CRR0VNfaGZ);
import instructions are in `data/election_2026/DOWNLOAD.md`.
The importer verifies the original hashes and restores all subsets without recollection.
The CSV file contains all nine raw trials; the JSON also contains
medians, min/max, quality metrics, environment, and input fingerprints.
'''
    (ROOT / "SCALABILITY_REPORT.md").write_text(report, encoding="utf-8")
    os.environ.setdefault("MPLCONFIGDIR", tempfile.mkdtemp(prefix="id2222-mpl-"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 5), layout="constrained")
    for key, label, color in (("algorithm_total", "Algorithm only (no I/O or exact Jaccard)", "#2356a8"),
                              ("minhash", "MinHash stage", "#be5b20")):
        y = [median(n, key) for n in sizes]
        low = [median(n, key) - summary[str(n)]["seconds"][key]["min"] for n in sizes]
        high = [summary[str(n)]["seconds"][key]["max"] - median(n, key) for n in sizes]
        ax.errorbar(sizes, y, yerr=[low, high], marker="o", capsize=4, linewidth=2, color=color, label=label)
    ax.set(xscale="log", yscale="log", xlabel="Number of documents (log scale)",
           ylabel="Wall-clock seconds (log scale)", title="Scalability: median and min–max of 3 runs")
    ax.set_xticks(sizes, [str(n) for n in sizes])
    ax.grid(True, which="both", alpha=0.2)
    ax.legend(loc="upper left", fontsize=9)
    fig.savefig(OUT / "execution_time.png", dpi=180)
    fig.savefig(OUT / "execution_time.svg")
    plt.close(fig)
    print("Wrote SCALABILITY_REPORT.md and execution_time.png/.svg")


if __name__ == "__main__":
    main()
