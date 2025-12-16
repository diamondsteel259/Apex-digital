from __future__ import annotations

import csv
import hashlib
import json
import logging
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook

from apex_market_scraper.config.models import ExportConfig

logger = logging.getLogger(__name__)

APEX_TEMPLATE_COLUMNS = [
    "Main_Category",
    "Sub_Category",
    "Service_Name",
    "Variant_Name",
    "Price_USD",
    "Start_Time",
    "Duration",
    "Refill_Period",
    "Additional_Info",
]

HIDDEN_METADATA_COLUMNS = [
    "product_url",
    "source_site",
]


def _timestamp() -> str:
    return datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")


def _map_product_record_to_apex_template(record: dict[str, Any]) -> dict[str, Any]:
    """Map ProductRecord fields to Apex-digital template columns."""
    result: dict[str, Any] = {}

    for col in APEX_TEMPLATE_COLUMNS:
        if col == "Main_Category":
            result[col] = record.get("category", "")
        elif col == "Sub_Category":
            result[col] = record.get("site", "")
        elif col == "Service_Name":
            result[col] = record.get("name", "")
        elif col == "Variant_Name":
            result[col] = record.get("description", "")
        elif col == "Price_USD":
            result[col] = record.get("price", "")
        elif col == "Start_Time":
            result[col] = record.get("source_updated_at", "")
        elif col == "Duration":
            result[col] = record.get("warranty", "")
        elif col == "Refill_Period":
            result[col] = record.get("refill_available", "")
        elif col == "Additional_Info":
            info_parts = []
            if record.get("sold_amount") is not None:
                info_parts.append(f"Sold: {record['sold_amount']}")
            if record.get("stock") is not None:
                info_parts.append(f"Stock: {record['stock']}")
            if record.get("seller_rating") is not None:
                info_parts.append(f"Rating: {record['seller_rating']}")
            result[col] = "; ".join(info_parts) if info_parts else ""

    for col in HIDDEN_METADATA_COLUMNS:
        if col == "product_url":
            result[col] = record.get("url", "")
        elif col == "source_site":
            result[col] = record.get("site", "")

    return result


def _compute_file_checksum(path: Path) -> str:
    """Compute SHA-256 checksum of a file."""
    sha256_hash = hashlib.sha256()
    with path.open("rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def write_csv(
    records: list[dict[str, Any]],
    path: Path,
    use_apex_template: bool = True,
    include_hidden_metadata: bool = True,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    if use_apex_template:
        fieldnames = APEX_TEMPLATE_COLUMNS.copy()
        if include_hidden_metadata:
            fieldnames.extend(HIDDEN_METADATA_COLUMNS)
        mapped_records = [_map_product_record_to_apex_template(r) for r in records]
    else:
        fieldnames = sorted({k for r in records for k in r.keys()})
        mapped_records = records

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in mapped_records:
            writer.writerow(row)


def write_xlsx(
    records: list[dict[str, Any]],
    path: Path,
    use_apex_template: bool = True,
    include_hidden_metadata: bool = True,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    if use_apex_template:
        fieldnames = APEX_TEMPLATE_COLUMNS.copy()
        if include_hidden_metadata:
            fieldnames.extend(HIDDEN_METADATA_COLUMNS)
        mapped_records = [_map_product_record_to_apex_template(r) for r in records]
    else:
        fieldnames = sorted({k for r in records for k in r.keys()})
        mapped_records = records

    wb = Workbook()
    ws = wb.active
    ws.title = "data"

    ws.append(fieldnames)

    if include_hidden_metadata and use_apex_template:
        for col_idx, col_name in enumerate(fieldnames, start=1):
            if col_name in HIDDEN_METADATA_COLUMNS:
                ws.column_dimensions[chr(64 + col_idx)].hidden = True

    for row in mapped_records:
        ws.append([row.get(k, "") for k in fieldnames])

    wb.save(path)


def write_manifest(
    records: list[dict[str, Any]],
    output_dir: Path,
    dataset_name: str,
    exported_files: dict[str, str],
) -> Path:
    """Write manifest.json with metadata about the scrape and exports."""
    output_dir.mkdir(parents=True, exist_ok=True)

    ts = _timestamp()

    manifest = {
        "version": "1.0",
        "timestamp": ts,
        "dataset_name": dataset_name,
        "records_count": len(records),
        "exports": {},
        "site_metadata": {},
        "checksum_version": "sha256",
    }

    for fmt, file_path in exported_files.items():
        if Path(file_path).exists():
            checksum = _compute_file_checksum(Path(file_path))
            manifest["exports"][fmt] = {
                "path": file_path,
                "checksum": checksum,
                "size_bytes": Path(file_path).stat().st_size,
            }

    site_timestamps: dict[str, dict[str, str]] = {}
    for record in records:
        site = record.get("site", "unknown")
        if site not in site_timestamps:
            site_timestamps[site] = {
                "first_record": record.get("scraped_at", ""),
                "last_record": record.get("scraped_at", ""),
            }
        else:
            site_timestamps[site]["last_record"] = record.get("scraped_at", "")

    manifest["site_metadata"] = site_timestamps

    manifest_path = output_dir / f"{dataset_name}_manifest_{ts}.json"
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    return manifest_path


def export_records(records: list[dict[str, Any]], cfg: ExportConfig) -> list[Path]:
    """Export records to configured formats and generate manifest."""
    ts = _timestamp()

    written: list[Path] = []
    exported_files: dict[str, str] = {}

    for fmt in cfg.formats:
        out_path = cfg.output_dir / f"{cfg.dataset_name}_{ts}.{fmt}"
        if fmt == "csv":
            write_csv(records, out_path, use_apex_template=True, include_hidden_metadata=True)
        elif fmt == "xlsx":
            write_xlsx(records, out_path, use_apex_template=True, include_hidden_metadata=True)
        else:
            raise ValueError(f"Unsupported export format: {fmt}")

        written.append(out_path)
        exported_files[fmt] = str(out_path)

        if cfg.apex_bot_drop_dir is not None:
            cfg.apex_bot_drop_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(out_path, cfg.apex_bot_drop_dir / out_path.name)

    manifest_path = write_manifest(records, cfg.output_dir, cfg.dataset_name, exported_files)
    written.append(manifest_path)

    if cfg.apex_bot_drop_dir is not None and manifest_path.exists():
        shutil.copy2(manifest_path, cfg.apex_bot_drop_dir / manifest_path.name)

    return written
