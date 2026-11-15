from pathlib import Path
from zipfile import ZipFile

import pytest
from pypdf import PdfReader

from carwise.catalog import Catalog
from carwise.fetch_sources import extract_pdf
from carwise.knowledge import _read_sections, load_manifest
from carwise.config import Settings


def test_manifest_matches_local_source_files():
    settings = Settings()
    records = load_manifest(settings.data_dir / "documents.json")
    assert len(records) == 11
    manuals = [record for record in records if record.path.endswith(".pdf")]
    assert len(manuals) == 10
    catalog = Catalog.from_file(settings.data_dir / "catalog.json")
    assert {vehicle.id for vehicle in catalog.list()} == {
        vehicle_id for record in manuals for vehicle_id in record.vehicle_ids
    }
    for record in records:
        assert record.page_ranges or record.content_selector
        assert (settings.data_dir / "raw" / record.path).is_file()
        assert record.source_url.host == "www.byd.com"
        if record.archive_path:
            assert (settings.data_dir / "raw" / record.archive_path).is_file()
        if record.path.endswith(".pdf"):
            assert record.page_ranges == [(1, len(PdfReader(settings.data_dir / "raw" / record.path).pages))]


def test_pdf_section_keeps_original_page_number():
    settings = Settings()
    sections = _read_sections(settings.data_dir / "raw" / "qin_l_manual_2026.pdf", [(58, 58)])
    assert len(sections) == 1
    assert sections[0][0] == "第 58 页"
    assert "指示灯" in sections[0][1]


def test_page_range_cannot_exceed_source():
    settings = Settings()
    with pytest.raises(ValueError, match="exceeds"):
        _read_sections(settings.data_dir / "raw" / "qin_l_manual_2026.pdf", [(9999, 9999)])


def test_extract_official_pdf_from_archive(tmp_path: Path):
    archive = tmp_path / "manual.zip"
    target = tmp_path / "manual.pdf"
    with ZipFile(archive, "w") as bundle:
        bundle.writestr("说明/手册.pdf", b"%PDF-sample")
    extract_pdf(archive, target)
    assert target.read_bytes() == b"%PDF-sample"

