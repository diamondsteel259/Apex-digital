# Export Scheduling & Automation Guide

This guide explains how to set up automated scraping and exporting for the Apex Market Scraper, including scheduling, monitoring, and integration with the Apex-digital bot.

## Table of Contents

1. [Overview](#overview)
2. [Export Formats and Schema](#export-formats-and-schema)
3. [Scheduling Setup](#scheduling-setup)
4. [Integration with Apex-digital](#integration-with-apex-digital)
5. [Monitoring and Alerting](#monitoring-and-alerting)
6. [Troubleshooting](#troubleshooting)
7. [Future Enhancements](#future-enhancements)

## Overview

The Apex Market Scraper provides automated, configurable scraping and export capabilities:

- **Export Formats**: CSV and Excel (XLSX) with matching schema
- **Column Mapping**: Exports align with Apex-digital's `products_template.xlsx`
- **Metadata**: Automatic manifest generation with checksums and scrape timestamps
- **Hidden Columns**: Back-office metadata (product URL, source site) hidden in Excel
- **Scheduling**: Flexible 12-24 hour cadence via CLI, cron, or systemd

### Quick Start

Run a single scrape+export cycle:

```bash
python -m apex_market_scraper.cli schedule --once
```

## Export Formats and Schema

### CSV Export

The CSV export includes:
- **Public Columns** (8): Main_Category, Sub_Category, Service_Name, Variant_Name, Price_USD, Start_Time, Duration, Refill_Period, Additional_Info
- **Hidden Metadata** (2): product_url, source_site

Example:
```
Main_Category,Sub_Category,Service_Name,Variant_Name,Price_USD,...,product_url,source_site
Electronics,G2A,Game Key,Steam,19.99,...,https://example.com/listing/123,g2a
```

### Excel Export (XLSX)

The Excel export matches the CSV schema but hides metadata columns (`product_url`, `source_site`) from normal view. These are still accessible programmatically for back-office use.

### Manifest File

Each export generates a `manifest.json` with:
- **version**: Export format version (e.g., "1.0")
- **timestamp**: ISO 8601 export timestamp
- **dataset_name**: Base name of the dataset
- **records_count**: Total number of exported records
- **exports**: File paths and SHA-256 checksums for each format
- **site_metadata**: First/last scrape timestamps per site

Example:
```json
{
  "version": "1.0",
  "timestamp": "20240101T120000Z",
  "dataset_name": "market_listings",
  "records_count": 1234,
  "exports": {
    "csv": {
      "path": "out/market_listings_20240101T120000Z.csv",
      "checksum": "abc123...",
      "size_bytes": 567890
    }
  },
  "site_metadata": {
    "g2a": {
      "first_record": "2024-01-01T12:00:00+00:00",
      "last_record": "2024-01-01T12:05:30+00:00"
    }
  }
}
```

## Scheduling Setup

### Option 1: Python `-m` Module with `--once`

For one-off exports (e.g., in cron jobs):

```bash
cd /path/to/apex-market-scraper
python -m apex_market_scraper.cli schedule --once
```

Environment variables:
- `AMSCRAPER_CONFIG_PATH`: Path to config file
- `AMSCRAPER_OUTPUT_DIR`: Override export output directory
- `AMSCRAPER_CADENCE_HOURS`: Override cadence (12-24 hours)

### Option 2: Cron Job

Add a crontab entry:

```bash
# Run daily at 2 AM
0 2 * * * cd /opt/apex-market-scraper && python -m apex_market_scraper.cli schedule --once >> /var/log/apex-scraper.log 2>&1
```

Recommended frequencies:
- **Daily** (0 2 * * *): Suitable for most use cases
- **Every 12 hours** (0 2,14 * * *): High-frequency markets

### Option 3: Systemd Timer (Linux)

Create `/etc/systemd/system/apex-scraper.service`:

```ini
[Unit]
Description=Apex Market Scraper
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=apex
Group=apex
WorkingDirectory=/opt/apex-market-scraper
Environment="AMSCRAPER_CONFIG_PATH=/etc/apex/config.json"
Environment="AMSCRAPER_OUTPUT_DIR=/var/lib/apex/exports"
ExecStart=/usr/bin/python3 -m apex_market_scraper.cli schedule --once
StandardOutput=journal
StandardError=journal
SyslogIdentifier=apex-scraper
```

Create `/etc/systemd/system/apex-scraper.timer`:

```ini
[Unit]
Description=Apex Market Scraper Timer
Requires=apex-scraper.service

[Timer]
# Run daily at 2 AM
OnCalendar=*-*-* 02:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable apex-scraper.timer
sudo systemctl start apex-scraper.timer
sudo systemctl status apex-scraper.timer
```

View logs:

```bash
journalctl -u apex-scraper.service -f
```

### Option 4: Docker Cron Container

Use a container scheduler (e.g., Kubernetes CronJob, Docker Swarm):

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: apex-scraper
spec:
  schedule: "0 2 * * *"
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: scraper
            image: apex-market-scraper:latest
            env:
            - name: AMSCRAPER_CONFIG_PATH
              value: /config/config.json
            - name: AMSCRAPER_OUTPUT_DIR
              value: /exports
            command:
            - python
            - -m
            - apex_market_scraper.cli
            - schedule
            - --once
            volumeMounts:
            - name: config
              mountPath: /config
            - name: exports
              mountPath: /exports
          volumes:
          - name: config
            configMap:
              name: apex-scraper-config
          - name: exports
            persistentVolumeClaim:
              claimName: apex-exports
          restartPolicy: OnFailure
```

## Integration with Apex-digital

### Import Pipeline Connection

The Apex-digital bot can import exported files via the configured `apex_bot_drop_dir`:

#### Configuration

In your `config.json`:

```json
{
  "scheduler": {
    "cadence_hours": 12
  },
  "export": {
    "output_dir": "out/",
    "formats": ["csv", "xlsx"],
    "apex_bot_drop_dir": "/path/to/apex-digital/imports/",
    "dataset_name": "market_listings"
  },
  "sites": [...]
}
```

#### How It Works

1. Scraper runs on schedule
2. Exports CSV/XLSX files to `output_dir/`
3. Files are copied to `apex_bot_drop_dir/`
4. Apex bot's import service watches `apex_bot_drop_dir/`
5. Bot loads products and updates inventory

#### File Format Expectations

The Apex-digital import service expects:
- **Column Order**: Matches Apex template (Main_Category, Sub_Category, etc.)
- **Encoding**: UTF-8
- **Line Endings**: LF (Unix-style)
- **Missing Values**: Empty strings, not NULL

### Manifest for Import Tracking

Use the manifest file to verify successful imports:

```python
import json

with open('out/market_listings_manifest_20240101T120000Z.json') as f:
    manifest = json.load(f)

# Verify checksums
csv_file = manifest['exports']['csv']
print(f"CSV checksum: {csv_file['checksum']}")
print(f"CSV size: {csv_file['size_bytes']} bytes")

# Check scrape completeness
for site, meta in manifest['site_metadata'].items():
    print(f"{site}: {meta['first_record']} to {meta['last_record']}")
```

## Monitoring and Alerting

### Log Monitoring

#### Standard Output

Check for:
- **"Scrape complete"**: Successful cycle
- **"site.failed"**: Individual site failures
- **"Wrote export"**: Files successfully written
- **"Exported X file(s)"**: Summary of exports

Example logs:
```
INFO:root:Scrape complete: sites_attempted=2 sites_succeeded=2 records_total=1234 records_deduped=1200
INFO:root:Wrote export: out/market_listings_20240101T120000Z.csv
INFO:root:Wrote export: out/market_listings_20240101T120000Z.xlsx
INFO:root:Wrote export: out/market_listings_manifest_20240101T120000Z.json
```

#### Using Systemd Journald

```bash
# Recent logs
journalctl -u apex-scraper.service --no-pager

# Follow logs
journalctl -u apex-scraper.service -f

# Filter by severity
journalctl -u apex-scraper.service -p err
```

### Health Checks

#### File Existence

Monitor output directory for recent exports:

```bash
find /var/lib/apex/exports -name "market_listings_*.csv" -mtime -1
```

#### Manifest Validation

Check manifest for site failures:

```python
import json
from datetime import datetime, timedelta

manifest = json.load(open('out/market_listings_manifest_20240101T120000Z.json'))

# Alert if any site has no data
for site, meta in manifest['site_metadata'].items():
    if not meta.get('last_record'):
        print(f"WARNING: No data from {site}")

# Alert if scrape took too long
export_time = datetime.fromisoformat(manifest['timestamp'].replace('Z', '+00:00'))
if datetime.now(datetime.timezone.utc) - export_time > timedelta(hours=2):
    print("WARNING: Export is stale")
```

### Alerting Integration

#### Email Alerts (on Failure)

```bash
#!/bin/bash
OUTPUT_DIR=/var/lib/apex/exports
ALERT_EMAIL=ops@apex-digital.local

# Check for recent exports
if ! find "$OUTPUT_DIR" -name "*.csv" -mtime -1 | grep -q .; then
    echo "No exports found in last 24 hours" | mail -s "ALERT: Apex Scraper Failed" "$ALERT_EMAIL"
    exit 1
fi

# Check manifest for errors
if grep -q '"errors"' "$OUTPUT_DIR"/*manifest*.json; then
    echo "Errors detected in scraper output" | mail -s "ALERT: Apex Scraper Errors" "$ALERT_EMAIL"
    exit 1
fi
```

Add to crontab:

```bash
0 6 * * * /opt/apex-market-scraper/scripts/check_health.sh
```

#### Prometheus Metrics (Future)

Example custom exporter:

```python
from prometheus_client import Gauge, start_http_server
import json
from pathlib import Path

scraper_records = Gauge('apex_scraper_records_total', 'Total records scraped')
scraper_sites = Gauge('apex_scraper_sites_succeeded', 'Sites succeeded')

def update_metrics():
    manifest = json.load(open('/var/lib/apex/exports/market_listings_manifest_latest.json'))
    scraper_records.set(manifest['records_count'])
    scraper_sites.set(len(manifest['site_metadata']))

if __name__ == '__main__':
    start_http_server(8000)
    # Update periodically...
```

## Troubleshooting

### Issue: "No records scraped"

**Cause**: Sites might be unreachable or disabled.

**Solution**:
```bash
# Check enabled sites
grep -A 10 '"sites"' config.json

# Test single site
python -m apex_market_scraper.cli scrape --sites g2a --dry-run

# Check logs
tail -f /var/log/apex-scraper.log
```

### Issue: "Database channel ID mismatch"

**Cause**: Old database records from previous configuration.

**Solution**:
```bash
# Backup database
cp apex.db apex.db.backup

# Reinitialize
rm apex.db
python -m apex_market_scraper.cli schedule --once
```

### Issue: Export files are empty

**Cause**: Column mapping issues or no records returned.

**Solution**:
1. Check `--raw-json` output: `python -m apex_market_scraper.cli scrape --raw-json debug.json`
2. Inspect JSON structure
3. Verify column mappings in `writers.py`

### Issue: Excel file is corrupted

**Cause**: OpenPyXL version mismatch or encoding issues.

**Solution**:
```bash
# Reinstall openpyxl
pip install --upgrade openpyxl

# Test export
python -m apex_market_scraper.cli export --sample
```

### Issue: Systemd timer doesn't run

**Cause**: Timer not enabled or systemd issues.

**Solution**:
```bash
# Check timer status
systemctl status apex-scraper.timer

# List scheduled runs
systemctl list-timers apex-scraper.timer

# Enable timer
systemctl enable apex-scraper.timer
systemctl start apex-scraper.timer

# Check logs
journalctl -u apex-scraper.service -n 50
```

## Future Enhancements

### Reserved for Webhook Automation

The system is designed to support future webhook/API enhancements:

```python
# Future: Webhook notification on export completion
POST /webhooks/scraper/export-complete
{
    "dataset_name": "market_listings",
    "timestamp": "2024-01-01T12:00:00Z",
    "records_count": 1234,
    "manifest_path": "out/market_listings_manifest_...json"
}
```

### Reserved for Push Notifications

```python
# Future: Push notifications for errors
notify_slack(channel='#alerts', message='Apex scraper failed: ...')
notify_pagerduty(incident='Apex scraper site failure')
```

### Reserved for Database Persistence

```python
# Future: Store manifests in database for historical tracking
db.insert_manifest(manifest_dict)
db.query_scrape_history(days=30)
```

### Reserved for Retention Policies

Future support for automated cleanup:

```bash
# Example: Keep exports for 30 days
find /var/lib/apex/exports -name "*.csv" -mtime +30 -delete
find /var/lib/apex/exports -name "*.xlsx" -mtime +30 -delete
find /var/lib/apex/exports -name "*manifest*.json" -mtime +30 -delete
```

## Quick Reference

### Common Commands

```bash
# One-off export
python -m apex_market_scraper.cli schedule --once

# Dry run (no network)
python -m apex_market_scraper.cli scrape --dry-run

# Export with custom config
python -m apex_market_scraper.cli schedule --once --config /etc/apex/config.json

# Override output directory
AMSCRAPER_OUTPUT_DIR=/mnt/exports python -m apex_market_scraper.cli schedule --once
```

### Environment Variables

- `AMSCRAPER_CONFIG_PATH`: Path to config file (default: `configs/example.json`)
- `AMSCRAPER_OUTPUT_DIR`: Override export output directory
- `AMSCRAPER_CADENCE_HOURS`: Override cadence (12-24)
- `AMSCRAPER_LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)
- `AMSCRAPER_PROXIES`: Comma-separated proxy URLs
- `AMSCRAPER_PROXIES_FILE`: Path to file with proxies (one per line)

### Configuration Example

See `configs/example.json` for full configuration options.
