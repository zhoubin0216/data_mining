"""Command-line interface for corpus analysis."""

import argparse
import json
from pathlib import Path
from typing import Sequence

from .io_utils import load_documents
from .pipeline import AnalysisResult, analyze_documents


def _analysis_payload(result: AnalysisResult) -> dict:
    return {
        "configuration": {
            "documents": result.document_count,
            "bands": result.bands,
            "rows_per_band": result.rows,
            "approximate_lsh_threshold": result.approximate_lsh_threshold,
        },
        "shingle_counts": dict(result.shingle_counts),
        "evaluation": {
            "true_similar_pairs": len(result.true_pairs),
            "lsh_candidate_pairs": len(result.candidate_pairs),
            "minhash_similar_candidate_pairs": len(result.estimated_pairs),
            "candidate_precision": result.candidate_precision,
            "candidate_recall": result.candidate_recall,
        },
        "pairs": [
            {
                "left": score.left,
                "right": score.right,
                "exact_jaccard": score.exact_jaccard,
                "minhash_estimate": score.minhash_estimate,
                "lsh_candidate": score.lsh_candidate,
            }
            for score in result.pair_scores
        ],
    }


def _print_analysis(result: AnalysisResult, threshold: float) -> None:
    print("Documents: %d" % result.document_count)
    print(
        "LSH: %d bands x %d rows (curve threshold %.3f)"
        % (result.bands, result.rows, result.approximate_lsh_threshold)
    )
    print(
        "Exact pairs >= %.2f: %d | LSH candidates: %d | precision: %.3f | recall: %.3f"
        % (
            threshold,
            len(result.true_pairs),
            len(result.candidate_pairs),
            result.candidate_precision,
            result.candidate_recall,
        )
    )
    print("\nPairs meeting the exact threshold:")
    print("left\tright\texact_jaccard\tminhash_estimate\tlsh_candidate")
    for score in result.pair_scores:
        if score.exact_jaccard >= threshold:
            print(
                "%s\t%s\t%.4f\t%.4f\t%s"
                % (
                    score.left,
                    score.right,
                    score.exact_jaccard,
                    score.minhash_estimate,
                    str(score.lsh_candidate).lower(),
                )
            )


def _run_analyze(args: argparse.Namespace) -> int:
    documents = load_documents(args.input)
    result = analyze_documents(
        documents,
        k=args.k,
        num_hashes=args.num_hashes,
        threshold=args.threshold,
        seed=args.seed,
        bands=args.bands,
    )
    _print_analysis(result, args.threshold)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(_analysis_payload(result), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print("\nJSON written to %s" % args.output)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Find near-duplicate documents with shingling, MinHash, and LSH."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def common(subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument("--input", type=Path, required=True)
        subparser.add_argument("--k", type=int, default=10)
        subparser.add_argument("--num-hashes", type=int, default=120)
        subparser.add_argument("--threshold", type=float, default=0.8)
        subparser.add_argument("--seed", type=int, default=42)
        subparser.add_argument("--bands", type=int, default=None)

    analyze_parser = subparsers.add_parser("analyze", help="analyze a local corpus")
    common(analyze_parser)
    analyze_parser.add_argument("--output", type=Path)
    analyze_parser.set_defaults(func=_run_analyze)

    return parser


def main(argv: Sequence[str] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

