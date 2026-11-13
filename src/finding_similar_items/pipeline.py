"""End-to-end analysis pipeline."""

import itertools
from dataclasses import dataclass
from typing import Mapping, Sequence, Set

from .lsh import DocumentPair, LSH
from .minhashing import CompareSignatures, MinHashing
from .shingling import CompareSets, Shingling


@dataclass(frozen=True)
class PairScore:
    left: str
    right: str
    exact_jaccard: float
    minhash_estimate: float
    lsh_candidate: bool


@dataclass(frozen=True)
class AnalysisResult:
    document_count: int
    shingle_counts: Mapping[str, int]
    pair_scores: Sequence[PairScore]
    true_pairs: Set[DocumentPair]
    candidate_pairs: Set[DocumentPair]
    estimated_pairs: Set[DocumentPair]
    bands: int
    rows: int
    approximate_lsh_threshold: float

    @property
    def candidate_precision(self) -> float:
        if not self.candidate_pairs:
            return 1.0 if not self.true_pairs else 0.0
        return len(self.true_pairs & self.candidate_pairs) / len(self.candidate_pairs)

    @property
    def candidate_recall(self) -> float:
        if not self.true_pairs:
            return 1.0
        return len(self.true_pairs & self.candidate_pairs) / len(self.true_pairs)


def analyze_documents(
    documents: Mapping[str, str],
    k: int = 10,
    num_hashes: int = 120,
    threshold: float = 0.8,
    seed: int = 42,
    bands: int = None,
) -> AnalysisResult:
    if len(documents) < 2:
        raise ValueError("at least two documents are required")

    shingler = Shingling(k=k)
    minhash = MinHashing(num_hashes=num_hashes, seed=seed)
    shingle_sets = {
        document_id: shingler.shingle_set(text)
        for document_id, text in documents.items()
    }
    signatures = {
        document_id: minhash.signature(values)
        for document_id, values in shingle_sets.items()
    }
    lsh = LSH(num_hashes=num_hashes, threshold=threshold, bands=bands)
    candidates = lsh.candidate_pairs(signatures)
    estimated_pairs = {
        pair
        for pair in candidates
        if CompareSignatures.similarity(signatures[pair[0]], signatures[pair[1]])
        >= threshold
    }

    scores = []
    true_pairs: Set[DocumentPair] = set()
    for left, right in itertools.combinations(sorted(documents), 2):
        pair = (left, right)
        exact = CompareSets.jaccard(shingle_sets[left], shingle_sets[right])
        estimate = CompareSignatures.similarity(signatures[left], signatures[right])
        if exact >= threshold:
            true_pairs.add(pair)
        scores.append(
            PairScore(
                left=left,
                right=right,
                exact_jaccard=exact,
                minhash_estimate=estimate,
                lsh_candidate=pair in candidates,
            )
        )

    return AnalysisResult(
        document_count=len(documents),
        shingle_counts={key: len(value) for key, value in shingle_sets.items()},
        pair_scores=tuple(scores),
        true_pairs=true_pairs,
        candidate_pairs=candidates,
        estimated_pairs=estimated_pairs,
        bands=lsh.bands,
        rows=lsh.rows,
        approximate_lsh_threshold=lsh.approximate_threshold,
    )
