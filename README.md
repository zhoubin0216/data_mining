# Finding Similar News Items — PyCharm Project

This pure-Python project implements the document-similarity stages from
*Finding Similar Items*:

1. character **k-shingling** and stable shingle hashing;
2. exact **Jaccard similarity**;
3. deterministic **MinHash signatures**;
4. signature-similarity estimation;
5. optional **LSH banding** for candidate generation.

The included corpus contains ten short reports about the 2026 U.S. midterm
election. The texts are original paraphrases of the sources recorded in
`data/sources.json`. Documents 01/02 and 03/04 are controlled editorial
revisions used to verify near-duplicate detection at threshold 0.8.

## Open and run in PyCharm

1. Start PyCharm and select **Open**.
2. Choose this project folder: `ID2222`.
3. If PyCharm requests an interpreter, select any local Python 3.9 or later
   interpreter. No third-party packages are required.
4. Open `main.py` and click the green **Run** button, or select the included
   **Run Analysis** configuration.
5. To run the tests, select the included **Run Tests** configuration.

Experiment settings are grouped near the top of `main.py`:

```python
K_SHINGLE_LENGTH = 10
MINHASH_SIGNATURE_LENGTH = 120
SIMILARITY_THRESHOLD = 0.8
RANDOM_SEED = 42
```

The program prints each document's shingle count, all pairs meeting the exact
threshold, their MinHash estimates, whether LSH retrieved them, and candidate
precision and recall.

## Command-line alternatives

The same project can be run without PyCharm:

```bash
python3 main.py

PYTHONPATH=src python3 -m unittest discover -s tests -v

PYTHONPATH=src python3 -m finding_similar_items analyze \
  --input data/news_corpus \
  --k 10 \
  --num-hashes 120 \
  --threshold 0.8 \
  --output results/analysis.json
```

## Project structure

```text
ID2222/
├── main.py                         # PyCharm entry point
├── data/
│   ├── news_corpus/                # ten input documents
│   └── sources.json                # source provenance
├── src/finding_similar_items/
│   ├── shingling.py                # Shingling and CompareSets
│   ├── minhashing.py               # MinHashing and CompareSignatures
│   ├── lsh.py                      # LSH banding
│   ├── pipeline.py                 # end-to-end analysis
│   ├── io_utils.py                 # corpus loading
│   └── cli.py                      # optional command-line interface
├── tests/test_algorithms.py        # six unit tests
├── results/analysis.json           # saved example output
├── REPORT.md                       # submission-style report
└── .idea/                          # portable PyCharm configuration
```

The 10/100/1,000-document scalability experiment is intentionally excluded from
this version and can be added later without changing the core classes.

