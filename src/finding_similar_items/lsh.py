"""Locality-sensitive hashing with MinHash banding."""

import itertools
from collections import defaultdict
from typing import Dict, Mapping, Sequence, Set, Tuple

from .minhashing import CompareSignatures

DocumentPair = Tuple[str, str]


class LSH:
    """Generate and optionally verify candidate pairs using banding.

    If ``bands`` is omitted, a factorization of the signature length is chosen
    whose theoretical S-curve threshold ``(1 / bands) ** (1 / rows)`` is closest
    to the requested similarity threshold.
    """

    def __init__(
        self,
        num_hashes: int,
        threshold: float = 0.8,
        bands: int = None,
    ) -> None:
        if num_hashes <= 0:
            raise ValueError("num_hashes must be positive")
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("threshold must be between 0 and 1")
        if bands is None:
            bands = self._choose_bands(num_hashes, threshold)
        if bands <= 0 or num_hashes % bands != 0:
            raise ValueError("bands must be a positive divisor of num_hashes")
        self.num_hashes = num_hashes
        self.threshold = threshold
        self.bands = bands
        self.rows = num_hashes // bands

    @staticmethod
    def _choose_bands(num_hashes: int, threshold: float) -> int:
        divisors = [
            value for value in range(1, num_hashes + 1) if num_hashes % value == 0
        ]

        def distance(bands: int) -> float:
            rows = num_hashes // bands
            approximate_threshold = (1.0 / bands) ** (1.0 / rows)
            return abs(approximate_threshold - threshold)

        return min(divisors, key=distance)

    @property
    def approximate_threshold(self) -> float:
        return (1.0 / self.bands) ** (1.0 / self.rows)

    def candidate_probability(self, similarity: float) -> float:
        return 1.0 - (1.0 - similarity ** self.rows) ** self.bands

    def candidate_pairs(
        self, signatures: Mapping[str, Sequence[int]]
    ) -> Set[DocumentPair]:
        buckets: Dict[Tuple[int, Tuple[int, ...]], list] = defaultdict(list)
        for document_id, signature in signatures.items():
            if len(signature) != self.num_hashes:
                raise ValueError(
                    "%s has signature length %d; expected %d"
                    % (document_id, len(signature), self.num_hashes)
                )
            for band in range(self.bands):
                start = band * self.rows
                band_values = tuple(signature[start : start + self.rows])
                buckets[(band, band_values)].append(document_id)

        pairs: Set[DocumentPair] = set()
        for document_ids in buckets.values():
            if len(document_ids) < 2:
                continue
            for left, right in itertools.combinations(sorted(document_ids), 2):
                pairs.add((left, right))
        return pairs

    def similar_pairs(
        self, signatures: Mapping[str, Sequence[int]]
    ) -> Set[DocumentPair]:
        """Filter LSH candidates by estimated MinHash similarity."""
        return {
            pair
            for pair in self.candidate_pairs(signatures)
            if CompareSignatures.similarity(
                signatures[pair[0]], signatures[pair[1]]
            )
            >= self.threshold
        }

