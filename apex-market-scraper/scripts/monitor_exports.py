#!/usr/bin/env python3
"""Monitor apex-market-scraper exports and alert on issues."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


def check_export_recency(export_dir: Path, max_age_hours: int = 25) -> tuple[bool, str]:
    """Check if recent exports exist."""
    cutoff = datetime.now(tz=UTC) - timedelta(hours=max_age_hours)

    csv_files = list(export_dir.glob("*.csv"))
    if not csv_files:
        return False, "No CSV exports found"

    latest_csv = max(csv_files, key=lambda p: p.stat().st_mtime)
    latest_mtime = datetime.fromtimestamp(latest_csv.stat().st_mtime, tz=UTC)

    if latest_mtime < cutoff:
        age_hours = (datetime.now(tz=UTC) - latest_mtime).total_seconds() / 3600
        return False, f"Latest CSV is {age_hours:.1f} hours old (max: {max_age_hours})"

    return True, f"Latest CSV is recent: {latest_csv.name}"


def check_manifest_validity(manifest_path: Path) -> tuple[bool, str]:
    """Validate manifest.json structure and content."""
    if not manifest_path.exists():
        return False, f"Manifest not found: {manifest_path}"

    try:
        with manifest_path.open("r", encoding="utf-8") as f:
            manifest = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return False, f"Failed to parse manifest: {e}"

    required_fields = [
        "version",
        "timestamp",
        "dataset_name",
        "records_count",
        "exports",
        "site_metadata",
    ]
    for field in required_fields:
        if field not in manifest:
            return False, f"Missing required field in manifest: {field}"

    if manifest["records_count"] == 0:
        return False, "Manifest shows zero records (possible scrape failure)"

    records_count = manifest["records_count"]
    sites_count = len(manifest["site_metadata"])
    return True, f"Manifest valid: {records_count} records from {sites_count} sites"


def check_exports_exist(manifest: dict[str, Any]) -> tuple[bool, str]:
    """Check that files referenced in manifest exist."""
    missing = []

    for fmt, export_info in manifest.get("exports", {}).items():
        file_path = export_info.get("path")
        if not file_path or not Path(file_path).exists():
            missing.append(f"{fmt}: {file_path}")

    if missing:
        return False, f"Missing exported files: {'; '.join(missing)}"

    return True, "All exported files exist and are accessible"


def check_exports_integrity(manifest: dict[str, Any]) -> tuple[bool, str]:
    """Verify checksums of exported files."""
    import hashlib

    mismatches = []

    for fmt, export_info in manifest.get("exports", {}).items():
        file_path = Path(export_info.get("path", ""))
        expected_checksum = export_info.get("checksum")

        if not file_path.exists():
            continue

        sha256_hash = hashlib.sha256()
        with file_path.open("rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)

        actual_checksum = sha256_hash.hexdigest()
        if actual_checksum != expected_checksum:
            mismatches.append(f"{fmt}: {actual_checksum} != {expected_checksum}")

    if mismatches:
        return False, f"Checksum mismatches: {'; '.join(mismatches)}"

    return True, "All file checksums verified"


def check_site_coverage(
    manifest: dict[str, Any], expected_sites: list[str] | None = None
) -> tuple[bool, str]:
    """Check that all expected sites have data."""
    site_metadata = manifest.get("site_metadata", {})

    if not site_metadata:
        return False, "No site metadata in manifest"

    if expected_sites:
        missing_sites = set(expected_sites) - set(site_metadata.keys())
        if missing_sites:
            return False, f"Missing data from sites: {', '.join(missing_sites)}"

    errors = []
    for site, meta in site_metadata.items():
        if not meta.get("first_record") or not meta.get("last_record"):
            errors.append(f"{site}: incomplete timestamp data")

    if errors:
        return False, "; ".join(errors)

    return True, f"Coverage verified: {len(site_metadata)} sites with data"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Monitor apex-market-scraper exports and alert on issues"
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        default=Path("out"),
        help="Export output directory (default: out/)",
    )
    parser.add_argument(
        "--max-age-hours",
        type=int,
        default=25,
        help="Maximum age of exports in hours before alert (default: 25)",
    )
    parser.add_argument(
        "--expected-sites",
        type=str,
        help="Comma-separated list of expected sites (e.g., 'g2a,g2g')",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format",
    )

    args = parser.parse_args()

    export_dir = Path(args.export_dir)
    if not export_dir.exists():
        result = {"status": "FAIL", "message": f"Export directory not found: {export_dir}"}
        if args.json:
            print(json.dumps(result))
        else:
            print(f"FAIL: {result['message']}")
        return 1

    checks = []

    check_ok, msg = check_export_recency(export_dir, args.max_age_hours)
    checks.append({"name": "Export Recency", "ok": check_ok, "message": msg})

    latest_manifest = max(
        export_dir.glob("*manifest*.json"),
        default=None,
        key=lambda p: p.stat().st_mtime,
    )
    if latest_manifest:
        check_ok, msg = check_manifest_validity(latest_manifest)
        checks.append({"name": "Manifest Validity", "ok": check_ok, "message": msg})

        with latest_manifest.open("r", encoding="utf-8") as f:
            manifest = json.load(f)

        check_ok, msg = check_exports_exist(manifest)
        checks.append({"name": "Exports Exist", "ok": check_ok, "message": msg})

        check_ok, msg = check_exports_integrity(manifest)
        checks.append({"name": "Integrity Check", "ok": check_ok, "message": msg})

        expected_sites = args.expected_sites.split(",") if args.expected_sites else None
        check_ok, msg = check_site_coverage(manifest, expected_sites)
        checks.append({"name": "Site Coverage", "ok": check_ok, "message": msg})
    else:
        checks.append({"name": "Manifest Validity", "ok": False, "message": "No manifest found"})

    all_ok = all(c["ok"] for c in checks)

    if args.json:
        result = {
            "status": "OK" if all_ok else "FAIL",
            "checks": checks,
            "timestamp": datetime.now(tz=UTC).isoformat(),
        }
        print(json.dumps(result, indent=2))
    else:
        status_symbol = "✓" if all_ok else "✗"
        print(f"\n{status_symbol} Export Monitoring Results\n")
        for check in checks:
            symbol = "✓" if check["ok"] else "✗"
            print(f"{symbol} {check['name']}: {check['message']}")
        print()

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
