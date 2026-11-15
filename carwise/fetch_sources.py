"""Download documents listed in the source manifest."""

import argparse
from pathlib import Path
from shutil import copyfileobj
from zipfile import ZipFile

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


def extract_pdf(archive: Path, target: Path) -> None:
    if target.exists():
        print(f"Already present: {target.name}")
        return
    with ZipFile(archive) as bundle:
        pdfs = [item for item in bundle.infolist() if not item.is_dir() and item.filename.lower().endswith(".pdf")]
        if len(pdfs) != 1:
            raise ValueError(f"Expected one PDF in {archive.name}, found {len(pdfs)}")
        temporary = target.with_suffix(".pdf.part")
        with bundle.open(pdfs[0]) as source, temporary.open("wb") as output:
            copyfileobj(source, output)
        if temporary.open("rb").read(5) != b"%PDF-":
            temporary.unlink(missing_ok=True)
            raise ValueError(f"Archive does not contain a valid PDF: {archive.name}")
        temporary.replace(target)
    print(f"Extracted {target.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download document manifest sources")
    parser.add_argument("--document", help="Download a single document ID")
    args = parser.parse_args()
    settings = Settings()
    records = load_manifest(settings.data_dir / "documents.json")
    for record in records:
        if args.document and record.id != args.document:
            continue
        raw_root = (settings.data_dir / "raw").resolve()
        target = (raw_root / record.path).resolve()
        archive = (raw_root / record.archive_path).resolve() if record.archive_path else None
        if not target.is_relative_to(raw_root) or (archive and not archive.is_relative_to(raw_root)):
            raise ValueError(f"Document path escapes data/raw: {record.path}")
        if archive:
            download(str(record.source_url), archive)
            extract_pdf(archive, target)
        else:
            download(str(record.source_url), target)


if __name__ == "__main__":
    main()

