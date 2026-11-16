"""Package or import the fixed 1,000-document snapshot without recollection.

Run from the project root:
  python3 scripts/dataset_archive.py pack
  python3 scripts/dataset_archive.py import --archive /path/to/election_2026_1000.zip
"""

import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "election_2026"
DEFAULT_ARCHIVE = ROOT / "exports" / "election_2026_1000.zip"
SIZES = {"real_20": 20, "scale_10": 10, "scale_100": 100, "scale_1000": 1000}


def manifests():
    result = {}
    for name, size in SIZES.items():
        items = json.loads((DATA / "manifests" / (name + ".json")).read_text())["documents"]
        records = {item["id"]: item for item in items}
        if len(items) != size or len(records) != size:
            raise ValueError("Invalid manifest size: " + name)
        for doc_id in records:
            if Path(doc_id).name != doc_id or "/" in doc_id or "\\" in doc_id or doc_id in (".", ".."):
                raise ValueError("Invalid document ID")
        result[name] = records
    full = result["scale_1000"]
    for records in result.values():
        for doc_id, item in records.items():
            if doc_id not in full or item["sha256"] != full[doc_id]["sha256"]:
                raise ValueError("Subset differs from full snapshot: " + doc_id)
    return result


def check_content(doc_id, content, item):
    if hashlib.sha256(content).hexdigest() != item["sha256"]:
        raise ValueError("SHA-256 mismatch: " + doc_id)
    content.decode("utf-8")


def pack(archive):
    records = manifests()["scale_1000"]
    contents = {}
    for doc_id, item in records.items():
        content = (DATA / "corpora" / "scale_1000" / (doc_id + ".txt")).read_bytes()
        check_content(doc_id, content, item)
        contents[doc_id] = content
    archive.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as bundle:
        for doc_id, content in sorted(contents.items()):
            bundle.writestr("documents/" + doc_id + ".txt", content)
        for name in SIZES:
            bundle.write(DATA / "manifests" / (name + ".json"), "manifests/" + name + ".json")
        for name in ("sources.json", "dataset_summary.json"):
            bundle.write(DATA / name, name)
        bundle.writestr("README.txt",
            "Finding Similar Items: fixed 1,000-document experiment snapshot.\n"
            "200 real texts (44 articles, 156 live updates) and 800 sentence-edit variants.\n"
            "The documents directory stores each final text once.\n"
            "From the matching project checkout, run:\n"
            "python3 scripts/dataset_archive.py import --archive /path/to/election_2026_1000.zip\n"
            "The importer checks project manifest hashes and restores real_20, scale_10,\n"
            "scale_100, and scale_1000 under data/election_2026/corpora/.\n"
            "No web collection or variant regeneration is required.\n"
            "Original publisher attribution is in sources.json and manifests/.\n")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(".zip.sha256").write_text(digest + "  " + archive.name + "\n")
    print("Packaged 1000 documents:", archive)
    print("SHA-256:", digest)


def import_archive(archive, destination=None):
    destination = DATA / "corpora" if destination is None else Path(destination)
    groups = manifests()
    contents = {}
    with ZipFile(archive) as bundle:
        names = bundle.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate archive entries")
        expected = {"documents/" + doc_id + ".txt" for doc_id in groups["scale_1000"]}
        actual = {name for name in names if name.startswith("documents/") and not name.endswith("/")}
        if actual != expected:
            raise ValueError("Archive must contain the exact 1000 expected documents")
        # Read only known entries; never extract archive-provided paths.
        for doc_id, item in groups["scale_1000"].items():
            content = bundle.read("documents/" + doc_id + ".txt")
            check_content(doc_id, content, item)
            contents[doc_id] = content
    # Validate every existing destination before writing anything.
    for name, records in groups.items():
        folder = destination / name
        extras = {p.name for p in folder.glob("*.txt")} - {key + ".txt" for key in records}
        if extras:
            raise ValueError("Unexpected existing files in " + str(folder))
        for doc_id in records:
            path = folder / (doc_id + ".txt")
            if path.exists() and path.read_bytes() != contents[doc_id]:
                raise ValueError("Existing file differs; move it aside first: " + str(path))
    for name, records in groups.items():
        folder = destination / name
        folder.mkdir(parents=True, exist_ok=True)
        for doc_id in records:
            path = folder / (doc_id + ".txt")
            if not path.exists():
                path.write_bytes(contents[doc_id])
    print("Verified snapshot; restored real_20, scale_10, scale_100, scale_1000:", destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    export = sub.add_parser("pack", help="create the ZIP for cloud-drive upload")
    export.add_argument("--output", type=Path, default=DEFAULT_ARCHIVE)
    restore = sub.add_parser("import", help="verify and restore a downloaded ZIP")
    restore.add_argument("--archive", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "pack":
            pack(args.output)
        else:
            import_archive(args.archive)
    except (OSError, ValueError, BadZipFile) as error:
        parser.exit(1, "Dataset error: %s\n" % error)


if __name__ == "__main__":
    main()
