from __future__ import annotations

import csv
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook

from apex_market_scraper.config.models import ExportConfig


def _timestamp() -> str:
    return datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")


def write_csv(records: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames: list[str] = sorted({k for r in records for k in r.keys()})

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in records:
            writer.writerow(row)


def write_xlsx(records: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames: list[str] = sorted({k for r in records for k in r.keys()})

    wb = Workbook()
    ws = wb.active
    ws.title = "data"

    ws.append(fieldnames)
    for row in records:
        ws.append([row.get(k) for k in fieldnames])

    wb.save(path)


def export_records(records: list[dict[str, Any]], cfg: ExportConfig) -> list[Path]:
    ts = _timestamp()

    written: list[Path] = []
    for fmt in cfg.formats:
        out_path = cfg.output_dir / f"{cfg.dataset_name}_{ts}.{fmt}"
        if fmt == "csv":
            write_csv(records, out_path)
        elif fmt == "xlsx":
            write_xlsx(records, out_path)
        else:
            raise ValueError(f"Unsupported export format: {fmt}")

        written.append(out_path)

        if cfg.apex_bot_drop_dir is not None:
            cfg.apex_bot_drop_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(out_path, cfg.apex_bot_drop_dir / out_path.name)

    return written
