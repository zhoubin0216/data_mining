"""Build reproducible, nested corpora and verify their lineage and similarities.

No network or timing benchmark is performed. Original text is never overwritten.
"""

import argparse
import hashlib
import itertools
import json
import random
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from finding_similar_items.shingling import Shingling, CompareSets

BASE = ROOT / "data" / "election_2026"
SEED = 20261116
K = 10
THRESHOLD = 0.8


def checksum(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_text(record):
    return (ROOT / record["path"]).read_text(encoding="utf-8").strip()


def diversified(records):
    """Deterministic round-robin across publisher/type/length strata."""
    buckets = defaultdict(list)
    for record in sorted(records, key=lambda x: x["id"]):
        length = min(record["word_count"] // 200, 4)
        buckets[(record["publisher_domain"], record["document_type"], length)].append(record)
    rng = random.Random(SEED)
    for group in buckets.values():
        rng.shuffle(group)
    result = []
    while buckets:
        for key in sorted(list(buckets)):
            result.append(buckets[key].pop())
            if not buckets[key]:
                del buckets[key]
    return result


def balanced_prefix_order(records):
    """Greedily balance nested prefixes against the selected pool's statistics."""
    pending = sorted(records, key=lambda x: x["id"])
    mean_words = statistics.mean(x["word_count"] for x in records)
    mean_shingles = statistics.mean(x["shingle_count"] for x in records)
    def category(x):
        return (x["document_type"], min(x["word_count"] // 200, 4))
    proportions = {key: count / len(records) for key, count in Counter(category(x) for x in records).items()}
    result, counts, words, shingles = [], Counter(), 0, 0
    while pending:
        n = len(result) + 1
        def loss(x):
            length_error = ((words + x["word_count"] - n * mean_words) / mean_words) ** 2
            length_error += ((shingles + x["shingle_count"] - n * mean_shingles) / mean_shingles) ** 2
            distribution_error = sum((counts[key] + (category(x) == key) - n * p) ** 2 / max(1, n * p)
                                     for key, p in proportions.items())
            return (length_error + distribution_error, x["id"])
        chosen = min(pending, key=loss)
        pending.remove(chosen)
        result.append(chosen)
        counts[category(chosen)] += 1
        words += chosen["word_count"]
        shingles += chosen["shingle_count"]
    return result


def variants(text, parent_id, used):
    """Select four distinct sentence edits; targets guide, never define labels.

    Only reorder or remove entire sentence units. Do not invent facts, rewrite
    names/numbers, or add document IDs to the actual text. Sentence segmentation
    is heuristic; these are mechanical experiments, not publishable news edits.
    """
    units = [x.strip() for x in re.split(r'(?<=[.!?])\s+|\n\s*\n', text) if x.strip()]
    if len(units) < 4:
        raise ValueError("Too few sentence units: " + parent_id)
    shingler = Shingling(K)
    original = shingler.shingle_set(text)
    rng = random.Random(SEED + int(checksum(parent_id)[:12], 16))
    options = {}

    def add(order, operation, removed):
        edited = "\n\n".join(units[i] for i in order)
        norm = checksum(shingler.normalize(edited))
        if norm in used or norm in options or len(edited.split()) < 40:
            return
        shingles = shingler.shingle_set(edited)
        value = CompareSets.jaccard(original, shingles)
        if value >= 1:
            return
        options[norm] = (edited, {"operation": operation, "sentence_order": order,
                                 "removed_sentence_indices": removed,
                                 "jaccard_to_parent": value})

    # Rearrangement supplies mild, meaning-preserving changes; deletions supply
    # stronger changes and cases around/below the decision threshold.
    for i in range(min(len(units) - 1, 12)):
        order = list(range(len(units)))
        order[i], order[i + 1] = order[i + 1], order[i]
        add(order, "swap_adjacent_sentence_units", [])
    for fraction in (0.05, 0.10, 0.20, 0.35, 0.50):
        for _ in range(7):
            count = max(1, min(len(units) - 1, round(len(units) * fraction)))
            removed = sorted(rng.sample(range(len(units)), count))
            order = [i for i in range(len(units)) if i not in removed]
            add(order, "omit_sentence_units", removed)
    if len(options) < 4:
        raise ValueError("Insufficient distinct variants: " + parent_id)
    selected = []
    for target in (0.97, 0.90, 0.81, 0.65):
        key = min(options, key=lambda x: (abs(options[x][1]["jaccard_to_parent"] - target), x))
        edited, change = options.pop(key)
        change["target_jaccard_advisory_only"] = target
        used.add(key)
        selected.append((edited, change))
    return selected


def materialize(name, records, texts):
    directory = BASE / "corpora" / name
    directory.mkdir(parents=True, exist_ok=True)
    expected = {x["id"] + ".txt" for x in records}
    stale = {p.name for p in directory.glob("*.txt")} - expected
    if stale:
        raise ValueError("Refusing to mix an old corpus with new selection: " + name)
    for record in records:
        path = directory / (record["id"] + ".txt")
        path.write_text(texts[record["id"]] + "\n", encoding="utf-8")
    save_json(BASE / "manifests" / (name + ".json"), {
        "name": name, "seed": SEED, "k": K, "threshold": THRESHOLD,
        "count": len(records), "documents": [dict(x, corpus_path=str(
            (directory / (x["id"] + ".txt")).relative_to(ROOT))) for x in records],
    })


def stats(records):
    words = [x["word_count"] for x in records]
    counts = [x["shingle_count"] for x in records]
    families = Counter(x["family_id"] for x in records)
    return {"documents": len(records), "kinds": dict(Counter(x["kind"] for x in records)),
            "families": len(families), "max_family_size": max(families.values()),
            "document_types": dict(Counter(x["document_type"] for x in records)),
            "publishers": dict(Counter(x["publisher_domain"] for x in records)),
            "words": {"min": min(words), "median": statistics.median(words),
                      "mean": statistics.mean(words), "max": max(words)},
            "shingles": {"min": min(counts), "median": statistics.median(counts),
                         "mean": statistics.mean(counts), "max": max(counts)}}


def build():
    sources = json.loads((BASE / "sources.json").read_text(encoding="utf-8"))
    shingler = Shingling(K)
    sources = [x for x in sources if len(re.split(r'(?<=[.!?])\s+|\n\s*\n', read_text(x))) >= 4]
    if len(sources) < 200:
        raise ValueError("Need 200 eligible real texts, found %d" % len(sources))
    # Select publisher/type/length strata, then balance the order of prefixes.
    ordered = diversified(sources)
    selected = ordered[:200]
    articles = diversified([x for x in sources if x["document_type"] == "article"])[:20]
    if len(articles) != 20:
        raise ValueError("Need 20 standalone real articles")
    texts = {x["id"]: read_text(x) for x in sources}
    used = {checksum(shingler.normalize(text)) for text in texts.values()}
    originals = {}
    for source in sources:
        original = dict(source, family_id=source["id"], parent_id=None,
                        shingle_count=len(shingler.shingle_set(texts[source["id"]])))
        originals[source["id"]] = original
    selected = balanced_prefix_order([originals[x["id"]] for x in selected])
    records, pair_labels = [], []
    for index, source in enumerate(selected):
        original = originals[source["id"]]
        family = [original]
        for number, (edited, change) in enumerate(variants(texts[source["id"]], source["id"], used), 1):
            doc_id = source["id"] + "_v%d" % number
            texts[doc_id] = edited
            family.append({"id": doc_id, "kind": "synthetic_variant", "document_type": "synthetic_variant",
                           "parent_id": source["id"], "family_id": source["id"],
                           "publisher_domain": source["publisher_domain"],
                           "source_url": source["source_url"], "published_at": None,
                           "source_published_at": source["published_at"],
                           "license": source["license"], "word_count": len(edited.split()),
                           "sha256": checksum(edited + "\n"),
                           "normalized_sha256": checksum(shingler.normalize(edited)),
                           "shingle_count": len(shingler.shingle_set(edited)),
                           "change": change, "synthetic": True})
        sets = {x["id"]: shingler.shingle_set(texts[x["id"]]) for x in family}
        for left, right in itertools.combinations(family, 2):
            exact = CompareSets.jaccard(sets[left["id"]], sets[right["id"]])
            pair_labels.append({"left": left["id"], "right": right["id"],
                                "family_id": original["id"], "exact_jaccard": exact,
                                "similar_at_0_8": exact >= THRESHOLD})
        records.extend(family)
        if (index + 1) % 20 == 0:
            print("Built", len(records), "documents", flush=True)
    # All text identity checks use exactly the algorithm's normalization.
    hashes = [checksum(shingler.normalize(texts[x["id"]])) for x in records]
    if len(set(hashes)) != 1000:
        raise AssertionError("Duplicate normalized text in scale_1000")
    corpora = {"real_20": [originals[x["id"]] for x in articles],
               "scale_10": records[:10], "scale_100": records[:100], "scale_1000": records}
    for name, members in corpora.items():
        materialize(name, members, texts)
    save_json(BASE / "within_family_labels.json", {
        "scope": "All pairs within each selected source family only; NOT exhaustive corpus ground truth. Cross-family pairs are unlabeled, not negative.",
        "k": K, "threshold": THRESHOLD, "pairs": pair_labels,
    })
    positive = sum(x["similar_at_0_8"] for x in pair_labels)
    save_json(BASE / "dataset_summary.json", {
        "event": "2026 US midterm election results and immediate aftermath",
        "publication_window": ["2026-11-03", "2026-11-16"], "seed": SEED,
        "collected_real_documents": len(json.loads((BASE / "sources.json").read_text())),
        "eligible_real_documents": len(sources), "selected_real_documents": 200,
        "synthetic_variants": 800, "corpora": {name: stats(members) for name, members in corpora.items()},
        "within_family_pairs": len(pair_labels), "within_family_positive_pairs": positive,
        "within_family_negative_pairs": len(pair_labels) - positive,
        "normalized_duplicates_in_scale_1000": 0,
        "limitations": ["Not 1000 independent news articles; 800 mechanical sentence-edit variants.",
                        "Live updates from the same page are separate news units, not independent publishers.",
                        "Scale sets are nested, not train/test splits; the builder performs no timing. See the separate scalability report for measurements.",
                        "Target edit similarities are advisory. Labels use measured Jaccard, never lineage alone.",
                        "Source-family size is fixed at five; real cross-family overlap can still create larger candidate buckets.",
                        "Publisher mix and length distributions vary across sizes; report provided statistics.",
                        "No redistribution license for downloaded media text is assumed; bodies are Git-ignored."]})
    verify()


def verify():
    shingler = Shingling(K)
    manifests = {}
    for name, expected in (("real_20", 20), ("scale_10", 10), ("scale_100", 100), ("scale_1000", 1000)):
        manifest = json.loads((BASE / "manifests" / (name + ".json")).read_text())
        members = manifest["documents"]
        assert len(members) == expected
        files = list((BASE / "corpora" / name).glob("*.txt"))
        assert len(files) == expected
        hashes = set()
        for doc in members:
            text = (ROOT / doc["corpus_path"]).read_text(encoding="utf-8")
            assert checksum(text) == doc["sha256"], doc["id"]
            assert len(text.split()) == doc["word_count"]
            assert len(shingler.shingle_set(text)) == doc["shingle_count"]
            hashes.add(checksum(shingler.normalize(text)))
        assert len(hashes) == expected
        ids = {x["id"] for x in members}
        for doc in members:
            if doc["kind"] == "synthetic_variant":
                assert doc["parent_id"] in ids
        manifests[name] = ids
    assert manifests["scale_10"] < manifests["scale_100"] < manifests["scale_1000"]
    labels = json.loads((BASE / "within_family_labels.json").read_text())["pairs"]
    full = json.loads((BASE / "manifests" / "scale_1000.json").read_text())["documents"]
    sets = {x["id"]: shingler.shingle_set((ROOT / x["corpus_path"]).read_text()) for x in full}
    for pair in labels:
        exact = CompareSets.jaccard(sets[pair["left"]], sets[pair["right"]])
        assert abs(exact - pair["exact_jaccard"]) < 1e-12
        assert (exact >= THRESHOLD) == pair["similar_at_0_8"]
    print("VERIFIED: sizes, hashes, unique normalized texts, nesting, lineage, and 2000 exact labels.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    if parser.parse_args().verify_only:
        verify()
    else:
        build()
