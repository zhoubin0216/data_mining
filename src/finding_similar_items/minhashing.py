"""MinHash signatures and signature comparison."""

import random
from typing import Iterable, Sequence, Tuple


class MinHashing:
    """Build deterministic MinHash signatures using universal hash functions."""

    # A Mersenne prime large enough for the 64-bit shingle hashes after reduction.
    PRIME = (1 << 61) - 1

    def __init__(self, num_hashes: int = 120, seed: int = 42) -> None:
        if num_hashes <= 0:
            raise ValueError("num_hashes must be positive")
        self.num_hashes = num_hashes
        self.seed = seed
        rng = random.Random(seed)
        self._coefficients = tuple(
            (rng.randrange(1, self.PRIME), rng.randrange(0, self.PRIME))
            for _ in range(num_hashes)
        )

    def signature(self, values: Iterable[int]) -> Tuple[int, ...]:
        reduced = tuple({value % self.PRIME for value in values})
        if not reduced:
            return tuple([self.PRIME] * self.num_hashes)

        minima = [self.PRIME] * self.num_hashes
        prime = self.PRIME
        for value in reduced:
            for index, (coefficient_a, coefficient_b) in enumerate(
                self._coefficients
            ):
                candidate = (coefficient_a * value + coefficient_b) % prime
                if candidate < minima[index]:
                    minima[index] = candidate
        return tuple(minima)


class CompareSignatures:
    """Estimate Jaccard similarity from equal-length MinHash signatures."""

    @staticmethod
    def similarity(left: Sequence[int], right: Sequence[int]) -> float:
        if len(left) != len(right):
            raise ValueError("signatures must have equal length")
        if not left:
            raise ValueError("signatures must not be empty")
        agreements = sum(a == b for a, b in zip(left, right))
        return agreements / len(left)

