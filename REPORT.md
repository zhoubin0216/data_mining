# Finding Similar News Reports with Shingling, MinHash, and LSH

## 1. Objective

This project implements the document-similarity pipeline described in *Finding
Similar Items*. It asks whether reports about the same news event are textual
near-duplicates. The case study is the 2026 U.S. midterm election, in which
Democrats won control of Congress and Republicans suffered broad losses.

The experiment uses a similarity threshold of **s = 0.8**. Two documents are
therefore labelled similar when the exact Jaccard similarity between their
hashed shingle sets is at least 0.8.

## 2. Dataset and experimental design

The local corpus contains ten short English news briefs. Each is an original
paraphrase based on a linked report; no media article is reproduced. The main
sources are CBS News and the Associated Press. Full provenance and access dates
are recorded in `data/sources.json`.

The dataset deliberately contains two types of relationship:

- **Controlled near-duplicates:** documents 01/02 and 03/04 are two editorial
  revisions of the same brief.
- **Topically related but independently written texts:** documents 05-10 cover
  redistricting, Senate losses, voter issues, unexpected House seats, Georgia,
  and the Republican post-election review.

This distinction is important. A 0.8 character-shingle threshold is designed to
find copied or lightly edited text, not merely documents about the same subject.
It would be a weak evaluation if every document were unrelated, because no true
positive would be available to test recall.

## 3. Implementation

### 3.1 Shingling and exact comparison

`Shingling(k=10)` first applies Unicode NFKC normalization, lower-casing,
punctuation removal, and whitespace collapsing. It then creates every
overlapping ten-character substring. Each unique shingle is converted to a
stable unsigned 64-bit integer with BLAKE2b and the final representation is a
set (or, when requested, a sorted tuple).

For shingle sets A and B, `CompareSets` computes:

```text
J(A, B) = |A intersection B| / |A union B|
```

Two empty sets are defined to have similarity 1.0.

### 3.2 MinHash signatures

`MinHashing` creates a 120-component signature. For each component i it uses a
universal hash function

```text
h_i(x) = (a_i x + b_i) mod p
```

where `p = 2^61 - 1`, `a_i` is nonzero, and the coefficient pairs are generated
once from random seed 42. A component is the minimum value of its hash function
over all shingles in a document. Using a fixed seed makes the entire experiment
reproducible.

`CompareSignatures` estimates Jaccard similarity as the fraction of positions
in which two signatures agree. MinHash theory gives an unbiased estimate because
the probability of agreement in a component equals the sets' Jaccard similarity.

### 3.3 Locality-sensitive hashing

`LSH` divides each signature into **12 bands of 10 rows**. Documents that have an
identical tuple in at least one band become candidate pairs. The implementation
then optionally filters candidates by their MinHash estimate or verifies them
with exact Jaccard similarity.

The approximate S-curve threshold is:

```text
(1 / b)^(1 / r) = (1 / 12)^(1 / 10) = 0.780
```

For two documents with similarity 0.8, the theoretical chance of becoming a
candidate is:

```text
1 - (1 - 0.8^10)^12 = 0.744
```

This probability is not a guarantee. LSH is a probabilistic screening stage;
exact Jaccard verification is still the final decision rule.

## 4. Results on the ten-document corpus

The implementation produced the following pairs at or above the exact threshold:

| Pair | Exact Jaccard | MinHash estimate | LSH candidate |
|---|---:|---:|---|
| 01 national result / 02 revision | 0.9041 | 0.9083 | yes |
| 03 House leadership / 04 revision | 0.9094 | 0.9083 | yes |

At threshold 0.8, LSH returned two candidates. Both were true similar pairs, and
both true pairs were retrieved:

| Metric | Value |
|---|---:|
| True pairs by exact Jaccard | 2 |
| LSH candidate pairs | 2 |
| Candidate precision | 1.000 |
| Candidate recall | 1.000 |

The largest exact similarity outside the controlled revisions was only 0.0483
(national result versus voter issues). This does not mean that the documents are
unrelated in meaning. It shows that character-shingle Jaccard at a high threshold
measures textual reuse, whereas semantic similarity would require a different
representation such as TF-IDF or embeddings.

The MinHash errors for the two positive pairs were +0.0042 and -0.0011,
respectively. These small differences are consistent with a 120-sample
probabilistic estimate.

## 5. Complexity and limitations

Let N be the number of documents, M the average number of unique shingles, H the
signature length, and C the number of LSH candidate pairs.

| Stage | Approximate time | Main storage |
|---|---|---|
| Shingling | O(total text length) | O(NM) |
| All-pairs exact Jaccard | O(N^2 M) | O(NM) |
| MinHash | O(NMH) | O(NH) signatures |
| LSH banding | O(NH + C) | O(NH + C) |
| Exact candidate verification | O(CM) | O(C) |

The experiment has four important limitations. First, the corpus is small and
contains controlled revisions, so its precision and recall are demonstrations,
not general estimates. Second, character normalization discards punctuation and
formatting. Third, the 120 hash functions trade some estimation error for speed.
Fourth, news sites may update stories after publication; the bundled paraphrases
and source metadata make this submission reproducible despite such changes.

The requested 10/100/1,000-document timing comparison is deferred and is not
part of the current version of the experiment.

## 6. Reproduction

Open the project folder in PyCharm, choose a Python 3.9 or later interpreter,
and run `main.py`. The project has no third-party dependencies. It can also be
run from a terminal:

```bash
python3 main.py
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m finding_similar_items analyze \
  --input data/news_corpus --output results/analysis.json
```

The first command shows the results directly, the second runs six unit tests,
and the third recreates the saved pairwise JSON results.

## 7. Conclusion

The implementation completes all required stages and the optional LSH stage.
On the case-study corpus it correctly separates light editorial revision from
independent reporting on the same event. MinHash closely approximates the two
exact positive similarities, and LSH reduces 45 possible document pairs to two
candidates without missing a true pair in this run.

