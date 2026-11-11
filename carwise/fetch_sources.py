"""Download only manifest-listed public source files for local indexing."""

import argparse
from pathlib import Path

import httpx

from .config import Settings
from .knowledge import load_manifest


def download(url: str, target: Path) -> None:
    if target.exists():
        print(f"Already present: {target.name}")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".part")
    with httpx.stream("GET", url, follow_redirects=True, timeout=90) as response:
        response.raise_for_status()
        with temporary.open("wb") as output:
            for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                output.write(chunk)
    if target.suffix.lower() == ".pdf" and temporary.open("rb").read(5) != b"%PDF-":
        temporary.unlink(missing_ok=True)
        raise ValueError(f"Downloaded content is not a PDF: {url}")
    temporary.replace(target)
    print(f"Downloaded {target.name} ({target.stat().st_size / 1024 / 1024:.1f} MB)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download document manifest sources")
    parser.add_argument("--document", help="Download a single document ID")
    args = parser.parse_args()
    settings = Settings()
    records = load_manifest(settings.data_dir / "documents.json")
    for record in records:
        if args.document and record.id != args.document:
            continue
        target = (settings.data_dir / "raw" / record.path).resolve()
        if not target.is_relative_to((settings.data_dir / "raw").resolve()):
            raise ValueError(f"Document path escapes data/raw: {record.path}")
        download(str(record.source_url), target)


if __name__ == "__main__":
    main()

