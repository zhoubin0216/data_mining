"""Time existing algorithms on fixed corpora; keep exhaustive QA out of LSH time.

Run: python3 scripts/benchmark_scalability.py
Outputs raw trials, medians/ranges, exhaustive ground truth and retrieval errors.
"""

import argparse
import csv
import gc
import hashlib
import itertools
import json
import os
import platform
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from finding_similar_items import Shingling, CompareSets, MinHashing, CompareSignatures, LSH
from finding_similar_items.io_utils import load_documents
from finding_similar_items.pipeline import analyze_documents

DATA = ROOT / "data" / "election_2026"
OUT = ROOT / "results" / "scalability"
K, HASHES, SEED, THRESHOLD = 10, 120, 42, 0.8


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def validate(sizes):
    """Check manifests before timing. This also warms the OS file cache."""
    fingerprints = {}
    for size in sizes:
        if not (DATA / "corpora" / ("scale_%d" % size)).is_dir():
            raise FileNotFoundError(
                "Download and import the dataset ZIP before benchmarking: "
                "python3 scripts/dataset_archive.py import --archive /path/to/election_2026_1000.zip "
                "(see data/election_2026/DOWNLOAD.md)"
            )
        path = DATA / "manifests" / ("scale_%d.json" % size)
        manifest = json.loads(path.read_text())
        assert len(manifest["documents"]) == size
        files = list((DATA / "corpora" / ("scale_%d" % size)).glob("*.txt"))
        assert len(files) == size
        for item in manifest["documents"]:
            assert sha(ROOT / item["corpus_path"]) == item["sha256"], item["id"]
        fingerprints[str(size)] = sha(path)
    return fingerprints


def metrics(predicted, truth):
    tp = len(predicted & truth)
    return {"tp": tp, "fp": len(predicted - truth), "fn": len(truth - predicted),
            "precision": tp / len(predicted) if predicted else None,
            "recall": tp / len(truth) if truth else None}


def timed_trial(size, repeat, quiet=False):
    gc.collect()
    seconds = {}
    start = time.perf_counter()
    documents = load_documents(DATA / "corpora" / ("scale_%d" % size))
    seconds["load"] = time.perf_counter() - start
    start = time.perf_counter()
    shingler = Shingling(K)
    minhash = MinHashing(HASHES, SEED)
    lsh = LSH(HASHES, THRESHOLD)
    seconds["setup"] = time.perf_counter() - start
    start = time.perf_counter()
    sets = {key: shingler.shingle_set(text) for key, text in documents.items()}
    seconds["shingling"] = time.perf_counter() - start
    if not quiet:
        print("N=%d repeat=%d: MinHash started" % (size, repeat), flush=True)
    start = time.perf_counter()
    signatures = {key: minhash.signature(values) for key, values in sets.items()}
    seconds["minhash"] = time.perf_counter() - start
    start = time.perf_counter()
    candidates = lsh.candidate_pairs(signatures)
    seconds["lsh"] = time.perf_counter() - start
    start = time.perf_counter()
    estimates = {pair: CompareSignatures.similarity(signatures[pair[0]], signatures[pair[1]])
                 for pair in candidates}
    estimated_pairs = {pair for pair, value in estimates.items() if value >= THRESHOLD}
    seconds["candidate_signature_comparison"] = time.perf_counter() - start
    # Verify ALL LSH candidates: a noisy MinHash threshold must not be the final
    # definition of similarity and need not introduce an extra loss of recall.
    start = time.perf_counter()
    candidate_exact = {pair: CompareSets.jaccard(sets[pair[0]], sets[pair[1]]) for pair in candidates}
    verified = {pair for pair, value in candidate_exact.items() if value >= THRESHOLD}
    seconds["candidate_exact_verification"] = time.perf_counter() - start
    seconds["algorithm_total"] = sum(seconds[key] for key in (
        "setup", "shingling", "minhash", "lsh", "candidate_signature_comparison"))
    seconds["end_to_end"] = seconds["load"] + seconds["algorithm_total"] + seconds["candidate_exact_verification"]
    seconds["retrieval_with_precomputed_signatures"] = sum(seconds[key] for key in (
        "lsh", "candidate_signature_comparison", "candidate_exact_verification"))
    if not quiet:
        print("N=%d repeat=%d: algorithm-only %.3fs; %d candidates; offline exhaustive validation started"
              % (size, repeat, seconds["algorithm_total"], len(candidates)), flush=True)
    # This includes EVERY pair, including cross-family pairs; not just planted
    # source/variant relationships. It is deliberately outside algorithm_total.
    start = time.perf_counter()
    truth = {}
    for left, right in itertools.combinations(sorted(sets), 2):
        value = CompareSets.jaccard(sets[left], sets[right])
        if value >= THRESHOLD:
            truth[(left, right)] = value
    seconds["all_pairs_exact"] = time.perf_counter() - start
    seconds["exact_baseline_end_to_end"] = seconds["load"] + seconds["shingling"] + seconds["all_pairs_exact"]
    true_pairs = set(truth)
    assert verified == true_pairs & candidates
    # A direct equivalence check against the existing pipeline on the small set.
    # Evaluation and assertions do not enter timed stage measurements.
    if size == 10 and repeat == 1:
        reference = analyze_documents(documents, K, HASHES, THRESHOLD, SEED)
        assert reference.true_pairs == true_pairs
        assert reference.candidate_pairs == candidates
        assert reference.estimated_pairs == estimated_pairs
    pairs = size * (size - 1) // 2
    quality = {"all_possible_pairs": pairs, "true_similar_pairs": len(true_pairs),
               "lsh_candidates": len(candidates), "verified_similar_pairs": len(verified),
               "minhash_threshold_pairs": len(estimated_pairs),
               "candidate_reduction": 1 - len(candidates) / pairs,
               "candidates": metrics(candidates, true_pairs),
               "exact_verified": metrics(verified, true_pairs),
               "minhash_filtered": metrics(estimated_pairs, true_pairs)}
    detail = {"true_pairs": [{"left": p[0], "right": p[1], "jaccard": v,
                              "lsh_candidate": p in candidates} for p, v in sorted(truth.items())],
              "candidate_pairs": [{"left": p[0], "right": p[1], "jaccard": candidate_exact[p],
                                   "minhash_estimate": estimates[p]} for p in sorted(candidates)]}
    row = {"size": size, "repeat": repeat, "seconds": seconds, "quality": quality,
           "total_words": sum(len(text.split()) for text in documents.values()),
           "total_shingles": sum(map(len, sets.values()))}
    if not quiet:
        print("N=%d repeat=%d: offline baseline %.3fs (excluded); true=%d; recall=%.4f"
              % (size, repeat, seconds["exact_baseline_end_to_end"], len(true_pairs), quality["candidates"]["recall"] or 0), flush=True)
    return row, detail


def normalize_timing_scope(payload):
    """Recompute derived totals from unchanged stage timings; no rerun needed."""
    payload["primary_timing_key"] = "algorithm_total"
    payload["timing_scope"] = {
        "included": ["setup", "shingling", "minhash", "lsh", "candidate_signature_comparison"],
        "excluded": ["load", "candidate_exact_verification", "all_pairs_exact", "metrics", "serialization", "reporting"],
        "note": "Algorithm-only totals recomputed per trial from separately measured stages. Other timing fields are diagnostics, not the reported scalability time.",
    }
    payload["method"] = [
        "perf_counter wall-clock seconds; one small warm-up excluded",
        "each trial recomputes all representations; sequential increasing sizes per repeat",
        "algorithm_total includes only setup, shingling, minhash, LSH and candidate signature comparison",
        "file reading, ALL exact Jaccard work, ground-truth checks, quality metrics, writing and reporting are excluded",
        "end_to_end and exact_baseline_end_to_end are retained as auxiliary diagnostics only",
        "all candidates and all possible pairs receive separately timed exact Jaccard for offline evaluation",
    ]
    for row in payload["trials"]:
        row["seconds"]["algorithm_total"] = sum(row["seconds"][key] for key in payload["timing_scope"]["included"])


def persist(payload):
    normalize_timing_scope(payload)
    groups = {}
    for row in payload["trials"]:
        groups.setdefault(row["size"], []).append(row)
    summary = {}
    for size, rows in groups.items():
        assert all(row["quality"] == rows[0]["quality"] for row in rows)
        summary[str(size)] = {
            "repeats_completed": len(rows), "quality": rows[0]["quality"],
            "total_words": rows[0]["total_words"], "total_shingles": rows[0]["total_shingles"],
            "seconds": {key: {"median": statistics.median(r["seconds"][key] for r in rows),
                              "min": min(r["seconds"][key] for r in rows),
                              "max": max(r["seconds"][key] for r in rows)} for key in rows[0]["seconds"]}}
    payload["summary"] = summary
    save_json(OUT / "benchmark.json", payload)
    if payload["trials"]:
        flat = [{"documents": x["size"], "repeat": x["repeat"], **x["seconds"],
                 "candidates": x["quality"]["lsh_candidates"], "true_pairs": x["quality"]["true_similar_pairs"]}
                for x in payload["trials"]]
        with (OUT / "trials.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(flat[0]))
            writer.writeheader()
            writer.writerows(flat)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    sizes = (10, 100, 1000)
    payload = {"status": "running", "started_utc": datetime.now(timezone.utc).isoformat(),
               "configuration": {"k": K, "signature_length": HASHES, "seed": SEED, "threshold": THRESHOLD,
                                 "bands": 12, "rows": 10, "repeats": args.repeats, "sizes": sizes},
               "environment": {"python": sys.version, "system": platform.system(), "release": platform.release(),
                               "machine": platform.machine(), "logical_cpus": os.cpu_count(),
                               "execution": "single process, sequential; no explicit parallelism"},
               "manifest_sha256": validate(sizes),
               "code_sha256": {str(p.relative_to(ROOT)): sha(p) for p in sorted(
                   (ROOT / "src" / "finding_similar_items").glob("*.py"))},
               "method": ["perf_counter wall-clock seconds; one small warm-up excluded",
                          "OS file cache warmed by validation; each trial recomputes all representations",
                          "sequential increasing sizes per repeat; other host activity is uncontrolled",
                          "end_to_end includes load, setup, shingling, minhash, LSH, candidate signature comparison and exact verification",
                          "all-pairs exact baseline measured separately using same shingle sets; baseline end-to-end reuses measured load and shingling costs",
                          "all candidates receive exact verification; MinHash threshold pairs reported separately, not used to prune verification",
                          "no download, generation, quality metrics, serialization or reporting in timed totals"],
               "trials": []}
    print("Validation complete; warming up on 10 documents", flush=True)
    timed_trial(10, 0, quiet=True)
    for repeat in range(1, args.repeats + 1):
        for size in sizes:
            row, detail = timed_trial(size, repeat)
            payload["trials"].append(row)
            if repeat == 1:
                save_json(OUT / ("pairs_%d.json" % size), detail)
            persist(payload)
    payload["status"] = "complete"
    payload["finished_utc"] = datetime.now(timezone.utc).isoformat()
    persist(payload)
    print("COMPLETE:", OUT / "benchmark.json", flush=True)


if __name__ == "__main__":
    main()
