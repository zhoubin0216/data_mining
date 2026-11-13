"""PyCharm entry point for the Finding Similar Items assignment.

Open this file in PyCharm and click Run.  Change the constants below to try
different shingle lengths, signature lengths, or similarity thresholds.
"""

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from finding_similar_items.io_utils import load_documents  # noqa: E402
from finding_similar_items.pipeline import analyze_documents  # noqa: E402


# Experiment configuration
CORPUS_DIRECTORY = PROJECT_ROOT / "data" / "news_corpus"
K_SHINGLE_LENGTH = 10
MINHASH_SIGNATURE_LENGTH = 120
SIMILARITY_THRESHOLD = 0.8
RANDOM_SEED = 42


def print_results(result) -> None:
    print("Finding Similar News Items")
    print("=" * 74)
    print("Documents: %d" % result.document_count)
    print(
        "LSH configuration: %d bands x %d rows (curve threshold %.3f)"
        % (result.bands, result.rows, result.approximate_lsh_threshold)
    )
    print("Similarity threshold: %.2f" % SIMILARITY_THRESHOLD)
    print()

    print("Shingle counts")
    print("-" * 74)
    for document_id, count in sorted(result.shingle_counts.items()):
        print("%-42s %6d" % (document_id, count))

    print()
    print("Similar pairs")
    print("-" * 74)
    print(
        "%-28s %-28s %8s %8s %5s"
        % ("Document A", "Document B", "Jaccard", "MinHash", "LSH")
    )
    found = False
    for score in result.pair_scores:
        if score.exact_jaccard < SIMILARITY_THRESHOLD:
            continue
        found = True
        print(
            "%-28s %-28s %8.4f %8.4f %5s"
            % (
                score.left,
                score.right,
                score.exact_jaccard,
                score.minhash_estimate,
                "yes" if score.lsh_candidate else "no",
            )
        )
    if not found:
        print("No pairs reached the selected threshold.")

    print()
    print("LSH evaluation")
    print("-" * 74)
    print("Exact similar pairs : %d" % len(result.true_pairs))
    print("LSH candidates      : %d" % len(result.candidate_pairs))
    print("Candidate precision : %.3f" % result.candidate_precision)
    print("Candidate recall    : %.3f" % result.candidate_recall)


def main() -> None:
    documents = load_documents(CORPUS_DIRECTORY)
    result = analyze_documents(
        documents,
        k=K_SHINGLE_LENGTH,
        num_hashes=MINHASH_SIGNATURE_LENGTH,
        threshold=SIMILARITY_THRESHOLD,
        seed=RANDOM_SEED,
    )
    print_results(result)


if __name__ == "__main__":
    main()

