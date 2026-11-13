"""Input helpers for local text corpora."""

from pathlib import Path
from typing import Dict, Iterable


def load_documents(directory: Path, extensions: Iterable[str] = (".txt",)) -> Dict[str, str]:
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

