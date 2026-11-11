from pathlib import Path

import pytest

from carwise.knowledge import _read_sections, load_manifest
from carwise.config import Settings


def test_manifest_matches_local_source_files():
    settings = Settings()
    records = load_manifest(settings.data_dir / "documents.json")
    assert len(records) == 6
    for record in records:
        assert record.page_ranges or record.content_selector
        assert (settings.data_dir / "raw" / record.path).is_file()
        assert record.source_url.host == "www.byd.com"


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

