"""Smoke test for end-to-end export and manifest generation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from apex_market_scraper.config.models import ExportConfig
from apex_market_scraper.core.models import ProductRecord
from apex_market_scraper.export.writers import export_records


@pytest.fixture
def sample_records() -> list[ProductRecord]:
    """Create sample product records for testing."""
    return [
        ProductRecord(
            site_name="g2a",
            site_kind="marketplace",
            product_name="Game Key - Steam",
            category="Games",
            price=19.99,
            currency="USD",
            description="AAA Game Bundle",
            min_quantity=1.0,
            max_quantity=10.0,
            seller_rating=4.8,
            sold_amount=150,
            stock=50,
            delivery_eta="Instant",
            refill_available=False,
            warranty="30-day",
            product_url="https://g2a.example.com/listing/steam-game-123",
            hidden_link_metadata={"platform": "steam"},
        ),
        ProductRecord(
            site_name="g2g",
            site_kind="marketplace",
            product_name="Currency Code - WoW Gold",
            category="Virtual Currency",
            price=49.99,
            currency="USD",
            description="WoW Gold x1000",
            min_quantity=100.0,
            max_quantity=10000.0,
            seller_rating=4.5,
            sold_amount=320,
            stock=200,
            delivery_eta="5-10 minutes",
            refill_available=True,
            warranty="Refund available",
            product_url="https://g2g.example.com/listing/wow-gold-456",
            hidden_link_metadata={"game": "wow", "region": "us"},
        ),
    ]


@pytest.fixture
def export_config(tmp_path: Path) -> ExportConfig:
    """Create a temporary export config."""
    return ExportConfig(
        output_dir=tmp_path / "exports",
        formats=["csv", "xlsx"],
        apex_bot_drop_dir=tmp_path / "bot_imports",
        dataset_name="test_market_listings",
    )


def test_export_creates_csv_and_xlsx(
    sample_records: list[ProductRecord], export_config: ExportConfig
) -> None:
    """Test that export creates both CSV and XLSX files."""
    records_dicts = [r.to_dict() for r in sample_records]

    written_files = export_records(records_dicts, export_config)

    assert (
        len(written_files) >= 3
    ), f"Expected at least 3 files (csv, xlsx, manifest), got {len(written_files)}"

    csv_files = [f for f in written_files if f.suffix == ".csv"]
    xlsx_files = [f for f in written_files if f.suffix == ".xlsx"]
    json_files = [f for f in written_files if f.suffix == ".json"]

    assert len(csv_files) == 1
    assert len(xlsx_files) == 1
    assert len(json_files) == 1

    csv_path = csv_files[0]
    xlsx_path = xlsx_files[0]
    manifest_path = json_files[0]

    assert csv_path.exists(), f"CSV file not found: {csv_path}"
    assert xlsx_path.exists(), f"XLSX file not found: {xlsx_path}"
    assert manifest_path.exists(), f"Manifest file not found: {manifest_path}"


def test_csv_contains_apex_template_columns(
    sample_records: list[ProductRecord], export_config: ExportConfig
) -> None:
    """Test that CSV has correct Apex-digital template columns."""
    from apex_market_scraper.export.writers import APEX_TEMPLATE_COLUMNS, HIDDEN_METADATA_COLUMNS

    records_dicts = [r.to_dict() for r in sample_records]
    written_files = export_records(records_dicts, export_config)

    csv_path = [f for f in written_files if f.suffix == ".csv"][0]

    with csv_path.open("r", encoding="utf-8") as f:
        header = f.readline().strip().split(",")

    expected_columns = APEX_TEMPLATE_COLUMNS + HIDDEN_METADATA_COLUMNS
    assert (
        header == expected_columns
    ), f"CSV columns mismatch.\nExpected: {expected_columns}\nGot: {header}"


def test_manifest_contains_required_fields(
    sample_records: list[ProductRecord], export_config: ExportConfig
) -> None:
    """Test that manifest.json contains all required metadata."""
    records_dicts = [r.to_dict() for r in sample_records]
    written_files = export_records(records_dicts, export_config)

    manifest_path = [f for f in written_files if f.suffix == ".json"][0]

    with manifest_path.open("r", encoding="utf-8") as f:
        manifest = json.load(f)

    required_fields = [
        "version",
        "timestamp",
        "dataset_name",
        "records_count",
        "exports",
        "site_metadata",
    ]
    for field in required_fields:
        assert field in manifest

    assert manifest["version"] == "1.0"
    assert manifest["records_count"] == len(sample_records)
    assert "csv" in manifest["exports"]
    assert "xlsx" in manifest["exports"]


def test_manifest_has_site_timestamps(
    sample_records: list[ProductRecord], export_config: ExportConfig
) -> None:
    """Test that manifest includes scrape timestamps per site."""
    records_dicts = [r.to_dict() for r in sample_records]
    written_files = export_records(records_dicts, export_config)

    manifest_path = [f for f in written_files if f.suffix == ".json"][0]

    with manifest_path.open("r", encoding="utf-8") as f:
        manifest = json.load(f)

    site_metadata = manifest["site_metadata"]

    assert "g2a" in site_metadata, "g2a site not in manifest"
    assert "g2g" in site_metadata, "g2g site not in manifest"

    for site, meta in site_metadata.items():
        assert "first_record" in meta, f"Missing first_record for {site}"
        assert "last_record" in meta, f"Missing last_record for {site}"


def test_manifest_has_checksums(
    sample_records: list[ProductRecord], export_config: ExportConfig
) -> None:
    """Test that manifest includes SHA-256 checksums for exports."""
    records_dicts = [r.to_dict() for r in sample_records]
    written_files = export_records(records_dicts, export_config)

    manifest_path = [f for f in written_files if f.suffix == ".json"][0]

    with manifest_path.open("r", encoding="utf-8") as f:
        manifest = json.load(f)

    for fmt, export_info in manifest["exports"].items():
        assert "checksum" in export_info, f"Missing checksum for {fmt}"
        assert "size_bytes" in export_info, f"Missing size_bytes for {fmt}"
        assert len(export_info["checksum"]) == 64, f"Invalid SHA-256 checksum length for {fmt}"


def test_xlsx_has_hidden_metadata_columns(
    sample_records: list[ProductRecord], export_config: ExportConfig
) -> None:
    """Test that XLSX file has hidden metadata columns."""
    from openpyxl import load_workbook

    records_dicts = [r.to_dict() for r in sample_records]
    written_files = export_records(records_dicts, export_config)

    xlsx_path = [f for f in written_files if f.suffix == ".xlsx"][0]

    wb = load_workbook(xlsx_path)
    ws = wb.active

    hidden_columns = []
    for col_idx, dimension in ws.column_dimensions.items():
        if dimension.hidden:
            hidden_columns.append(col_idx)

    assert len(hidden_columns) > 0, "No hidden columns found in XLSX"


def test_files_copied_to_apex_bot_drop_dir(
    sample_records: list[ProductRecord], export_config: ExportConfig
) -> None:
    """Test that exported files are copied to apex_bot_drop_dir."""
    records_dicts = [r.to_dict() for r in sample_records]
    export_records(records_dicts, export_config)

    drop_dir = export_config.apex_bot_drop_dir
    assert drop_dir is not None

    drop_dir_files = list(drop_dir.glob("*"))

    assert len(drop_dir_files) >= 3


def test_export_handles_empty_records(export_config: ExportConfig) -> None:
    """Test that export handles empty record list gracefully."""
    empty_records: list[dict[str, Any]] = []

    written_files = export_records(empty_records, export_config)

    csv_path = [f for f in written_files if f.suffix == ".csv"][0]
    manifest_path = [f for f in written_files if f.suffix == ".json"][0]

    assert csv_path.exists()
    assert manifest_path.exists()

    with manifest_path.open("r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert manifest["records_count"] == 0


def test_csv_data_integrity(
    sample_records: list[ProductRecord], export_config: ExportConfig
) -> None:
    """Test that CSV data is correctly mapped from product records."""
    records_dicts = [r.to_dict() for r in sample_records]
    written_files = export_records(records_dicts, export_config)

    csv_path = [f for f in written_files if f.suffix == ".csv"][0]

    with csv_path.open("r", encoding="utf-8") as f:
        lines = f.readlines()

    assert len(lines) >= 2, f"CSV should have header + at least 1 data row, got {len(lines)}"

    data_row = lines[1].strip()
    assert "Game Key - Steam" in data_row or "Steam" in data_row


def test_schema_validation_smoke_test(
    sample_records: list[ProductRecord], export_config: ExportConfig
) -> None:
    """Smoke test for schema validation of exports."""
    records_dicts = [r.to_dict() for r in sample_records]
    written_files = export_records(records_dicts, export_config)

    assert len(written_files) >= 3

    for file_path in written_files:
        assert file_path.exists(), f"File does not exist: {file_path}"
        assert file_path.stat().st_size > 0, f"File is empty: {file_path}"

    manifest_path = [f for f in written_files if f.suffix == ".json"][0]

    with manifest_path.open("r", encoding="utf-8") as f:
        manifest = json.load(f)

    for export_info in manifest["exports"].values():
        exported_path = Path(export_info["path"])
        assert exported_path.exists()
