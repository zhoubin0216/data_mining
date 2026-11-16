# Download the fixed experiment dataset

The final dataset is distributed as **election_2026_1000.zip** through a cloud
drive, separately from the Git repository.

- **Download folder:** [Google Drive dataset folder](https://drive.google.com/drive/folders/12gJchd3Gv5oO9GsbdZrfX5CRR0VNfaGZ)

Open the folder and download `election_2026_1000.zip`, then run from the
project root (replace the example path):

```bash
python3 scripts/dataset_archive.py import --archive /path/to/election_2026_1000.zip
python3 main.py
```

`--archive` is required. The importer uses only the Python standard library,
checks every document against the repository's SHA-256 manifests, and restores:

- `data/election_2026/corpora/scale_1000/`: all 1,000 texts;
- `data/election_2026/corpora/scale_100/`: the original 100-text subset;
- `data/election_2026/corpora/scale_10/`: the original 10-text subset;
- `data/election_2026/corpora/real_20/`: the 20 real-article demonstration subset.

The ZIP stores the 1,000 texts once, under `documents/`, together with provenance
and manifests. Smaller sets are restored by document ID, without recollecting,
rewriting, resampling, or rerunning similarity algorithms. Existing matching files
are reused; conflicting files cause an error before any documents are written.
Manual extraction into the project root is unnecessary.

The dataset contains 200 real texts and 800 sentence-edit variants, not 1,000
independently collected articles. See [README.md](README.md) for provenance.

## Prepare the upload (dataset maintainer)

```bash
python3 scripts/dataset_archive.py pack
```

`pack --output` defaults to `exports/election_2026_1000.zip`. Upload this ZIP
and its accompanying `.zip.sha256` checksum file to the linked cloud-drive
folder. `exports/` and corpus text folders are Git-ignored. The historical web
collector and dataset builder remain available, but are not required to use the
distributed snapshot or reproduce the benchmark inputs.
