import unittest

from finding_similar_items import (
    CompareSets,
    CompareSignatures,
    LSH,
    MinHashing,
    Shingling,
    analyze_documents,
)


class ShinglingTests(unittest.TestCase):
    def test_hashes_are_unique_and_ordered(self):
        result = Shingling(k=3).hashed_shingles("Banana!")
        self.assertEqual(result, tuple(sorted(set(result))))
        self.assertEqual(len(result), 3)

    def test_jaccard_known_value(self):
        self.assertAlmostEqual(CompareSets.jaccard({1, 2, 3}, {2, 3, 4}), 0.5)
        self.assertEqual(CompareSets.jaccard(set(), set()), 1.0)


class MinHashTests(unittest.TestCase):
    def test_identical_sets_have_identical_signatures(self):
        minhash = MinHashing(num_hashes=32, seed=7)
        left = minhash.signature({1, 2, 3})
        right = minhash.signature({3, 2, 1})
        self.assertEqual(CompareSignatures.similarity(left, right), 1.0)

    def test_estimate_tracks_jaccard(self):
        minhash = MinHashing(num_hashes=256, seed=7)
        left_values = set(range(100))
        right_values = set(range(50, 150))
        exact = CompareSets.jaccard(left_values, right_values)
        estimate = CompareSignatures.similarity(
            minhash.signature(left_values), minhash.signature(right_values)
        )
        self.assertLess(abs(exact - estimate), 0.12)


class LSHTests(unittest.TestCase):
    def test_identical_signatures_are_candidates(self):
        signature = tuple(range(24))
        lsh = LSH(num_hashes=24, threshold=0.8)
        pairs = lsh.candidate_pairs({"a": signature, "b": signature})
        self.assertEqual(pairs, {("a", "b")})

    def test_pipeline_finds_a_near_duplicate(self):
        base = "The election result changed control of Congress. " * 12
        documents = {
            "a": base,
            "b": base.replace("result", "outcome", 1),
            "c": "A completely unrelated report about rainfall and forests. " * 12,
        }
        result = analyze_documents(
            documents, k=5, num_hashes=60, threshold=0.8, seed=3
        )
        self.assertIn(("a", "b"), result.true_pairs)
        self.assertIn(("a", "b"), result.candidate_pairs)


if __name__ == "__main__":
    unittest.main()
