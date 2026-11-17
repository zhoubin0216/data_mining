# Finding Similar News Items — PyCharm Project

This pure-Python project implements the document-similarity stages from
*Finding Similar Items*:

1. character **k-shingling** and stable shingle hashing;
2. exact **Jaccard similarity**;
3. deterministic **MinHash signatures**;
4. signature-similarity estimation;
5. optional **LSH banding** for candidate generation.

The default corpus now contains 20 real standalone articles about the November
2026 U.S. midterm election. A separate, nested 10/100/1,000-document dataset uses
200 real news texts (including explicitly identified live updates) and 800
mechanically edited variants. See `data/election_2026/README.md` for provenance,
limitations, and verification.

The final 1,000-document snapshot is distributed separately as a cloud-drive ZIP;
texts and distribution archives are Git-ignored. Only metadata and scripts are
intended for version control. Download from the
[Google Drive dataset folder](https://drive.google.com/drive/folders/12gJchd3Gv5oO9GsbdZrfX5CRR0VNfaGZ); see
[`data/election_2026/DOWNLOAD.md`](data/election_2026/DOWNLOAD.md).
The older `data/news_corpus` and `results/analysis.json`
remain historical synthetic demonstration material, not collected news.

## Download and import the dataset

Download `election_2026_1000.zip` from the shared cloud drive, then run from
the project root, replacing the example path:

```bash
python3 scripts/dataset_archive.py import --archive /path/to/election_2026_1000.zip
```

The importer checks SHA-256 hashes and restores `scale_10`, `scale_100`,
`scale_1000`, and `real_20` using the original manifests. No collection or
variant generation is needed. To prepare the ZIP for upload, run
`python3 scripts/dataset_archive.py pack`; the output and checksum are in
`exports/` (Git-ignored).

## Open and run in PyCharm

1. Start PyCharm and select **Open**.
2. Choose this project folder: `ID2222`.
3. If PyCharm requests an interpreter, select Python 3.9 or later. Algorithms
   and the dataset importer require no third-party packages. Import the
   downloaded ZIP first if the corpus is missing locally.
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
  --input data/election_2026/corpora/real_20 \
  --k 10 \
  --num-hashes 120 \
  --threshold 0.8 \
  --output results/real_news_analysis.json
```

## Project structure

```text
ID2222/
├── main.py                         # PyCharm entry point
├── data/
│   ├── election_2026/              # real news, variants, manifests and QA
│   ├── news_corpus/                # historical synthetic demonstration
│   └── sources.json                # historical demonstration metadata
├── scripts/                       # dataset import/export, benchmark, collection
├── exports/                       # cloud-drive upload ZIP (Git-ignored)
├── report/                        # current LaTeX report and Overleaf ZIP
├── src/finding_similar_items/
│   ├── shingling.py                # Shingling and CompareSets
│   ├── minhashing.py               # MinHashing and CompareSignatures
│   ├── lsh.py                      # LSH banding
│   ├── pipeline.py                 # end-to-end analysis
│   ├── io_utils.py                 # corpus loading
│   └── cli.py                      # optional command-line interface
├── tests/test_algorithms.py        # six unit tests
├── results/analysis.json           # saved example output
├── REPORT.md                       # historical demonstration report
└── .idea/                          # portable PyCharm configuration
```

The completed scalability experiment is documented in
[`SCALABILITY_REPORT.md`](SCALABILITY_REPORT.md), with raw measurements in
`results/scalability/`. Reproduce it with `python3 scripts/benchmark_scalability.py
--repeats 3`; render the report/figure with `python3 scripts/report_scalability.py`
(matplotlib needed only for plotting).

Reported algorithm time includes setup, shingling, MinHash, LSH and candidate
signature comparison only. File reading, all exact-Jaccard verification and
quality evaluation are excluded. The interactive `pipeline.py` still compares all pairs for evaluation;
its total runtime should not be interpreted as LSH-only runtime. `REPORT.md`
describes the older demonstration, not the new data collection.

