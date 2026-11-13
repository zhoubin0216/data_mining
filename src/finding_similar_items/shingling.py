"""Character shingling and exact Jaccard similarity."""

import hashlib
import re
import unicodedata
from typing import FrozenSet, Iterable, Tuple


class Shingling:
    """Convert a document into deterministic hashes of unique k-shingles.

    Text is Unicode-normalized, lower-cased, and stripped of punctuation before
    overlapping character shingles are formed.  BLAKE2b is used instead of
    Python's built-in ``hash`` because the latter changes between processes.
    """

    def __init__(self, k: int = 10) -> None:
        if k <= 0:
            raise ValueError("k must be positive")
        self.k = k

    @staticmethod
    def normalize(text: str) -> str:
        normalized = unicodedata.normalize("NFKC", text).lower()
        normalized = re.sub(r"[^\w]+", " ", normalized, flags=re.UNICODE)
        return re.sub(r"\s+", " ", normalized).strip()

    def shingles(self, text: str) -> FrozenSet[str]:
        normalized = self.normalize(text)
        if not normalized:
            return frozenset()
        if len(normalized) <= self.k:
            return frozenset((normalized,))
        return frozenset(
            normalized[index : index + self.k]
            for index in range(len(normalized) - self.k + 1)
        )

    @staticmethod
    def hash_shingle(shingle: str) -> int:
        digest = hashlib.blake2b(
            shingle.encode("utf-8"), digest_size=8, person=b"shingle1"
        ).digest()
        return int.from_bytes(digest, byteorder="big", signed=False)

    def shingle_set(self, text: str) -> FrozenSet[int]:
        return frozenset(self.hash_shingle(item) for item in self.shingles(text))

    def hashed_shingles(self, text: str) -> Tuple[int, ...]:
        """Return the requested ordered set representation as a sorted tuple."""
        return tuple(sorted(self.shingle_set(text)))


class CompareSets:
    """Compute exact Jaccard similarity between two integer sets."""

    @staticmethod
    def jaccard(left: Iterable[int], right: Iterable[int]) -> float:
        left_set = set(left)
        right_set = set(right)
        union_size = len(left_set | right_set)
        if union_size == 0:
            return 1.0
        return len(left_set & right_set) / union_size

