import argparse

from .config import Settings
from .knowledge import KnowledgeBase, load_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Import source documents into the local vector index")
    parser.add_argument("--show-only", action="store_true", help="Validate the manifest without embedding")
    args = parser.parse_args()
    settings = Settings()
    records = load_manifest(settings.data_dir / "documents.json")
    if args.show_only:
        for record in records:
            print(f"{record.id}: {record.title} ({record.path})")
        print(f"{len(records)} documents in manifest")
        return
    counts = KnowledgeBase(settings).ingest(records)
    for document_id, count in counts.items():
        print(f"{document_id}: {count} chunks")
    print(f"Imported {sum(counts.values())} chunks")


if __name__ == "__main__":
    main()

