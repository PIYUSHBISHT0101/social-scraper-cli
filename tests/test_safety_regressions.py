"""Regression tests for data integrity and safe exports."""
from unittest.mock import patch

import openpyxl

from src.core.deduplicator import Deduplicator
from src.core.exporter import DatasetExporter, spreadsheet_safe
from src.scrapers.youtube import parse_like_count


def test_rejected_item_does_not_poison_seen_ids():
    rows = [
        {"comment_id": "1", "comment": "same"},
        {"comment_id": "2", "comment": "same"},
        {"comment_id": "2", "comment": "different"},
    ]
    kept, stats = Deduplicator(by_exact_text=True).deduplicate(rows)
    assert [r["comment_id"] for r in kept] == ["1", "2"]
    assert stats["text_duplicates"] == 1


def test_ids_are_scoped_to_platform_and_identical_text_can_be_preserved():
    rows = [{"platform": p, "comment_id": "1", "comment": "same"} for p in ("Reddit", "YouTube")]
    assert len(Deduplicator(by_exact_text=False).deduplicate(rows)[0]) == 2


def test_spreadsheet_escaping_and_excel_output(tmp_path):
    assert spreadsheet_safe("  =1+1") == "'  =1+1"
    assert spreadsheet_safe("\ttext") == "'\ttext"
    assert spreadsheet_safe(-5) == -5
    path = tmp_path / "comments.xlsx"
    DatasetExporter(str(tmp_path)).export_excel([{"comment": "=1+1", "author": "+test"}], output_path=str(path))
    sheet = openpyxl.load_workbook(path)["Comments"]
    assert sheet["D2"].value == "'=1+1"
    assert sheet["M2"].value == "'+test"
    assert sheet["D2"].data_type == "s"


def test_failed_parquet_is_not_reported(tmp_path):
    exporter = DatasetExporter(str(tmp_path))
    with patch.object(exporter, "export_parquet", return_value=""):
        assert exporter.export_all([{"comment": "test"}], formats=["parquet"]) == {}


def test_abbreviated_likes():
    assert parse_like_count("1.2K") == 1200
    assert parse_like_count("2M") == 2000000
    assert parse_like_count("1,234") == 1234
    assert parse_like_count("invalid") == 0
