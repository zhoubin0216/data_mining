"""Input helpers for local text corpora."""

from pathlib import Path
from typing import Dict, Iterable


def load_documents(directory: Path, extensions: Iterable[str] = (".txt",)) -> Dict[str, str]:
    if not directory.is_dir():
        raise FileNotFoundError(
            "Corpus directory not found: %s. For the assignment dataset, download "
            "election_2026_1000.zip from the shared cloud drive and run from the project root: "
            "python3 scripts/dataset_archive.py import --archive /path/to/election_2026_1000.zip. "
            "See data/election_2026/DOWNLOAD.md." % directory
        )
    allowed = {extension.lower() for extension in extensions}
    paths = sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in allowed
    )
    documents = {
        path.stem: path.read_text(encoding="utf-8")
        for path in paths
    }
    if not documents:
        raise ValueError("no input documents found in %s" % directory)
    return documents

