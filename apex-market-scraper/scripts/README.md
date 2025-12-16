# Apex Market Scraper - Operational Scripts

This directory contains utility scripts for monitoring and maintaining the Apex Market Scraper in production.

## Scripts

### monitor_exports.py

Monitors the health and integrity of exported market data files.

#### Usage

```bash
python scripts/monitor_exports.py [OPTIONS]
```

#### Options

- `--export-dir PATH`: Export output directory (default: `out/`)
- `--max-age-hours N`: Maximum age of exports before alert (default: 25 hours)
- `--expected-sites SITES`: Comma-separated list of expected sites (e.g., `g2a,g2g`)
- `--json`: Output results in JSON format (useful for monitoring systems)

#### Examples

```bash
# Check exports in default directory
python scripts/monitor_exports.py

# Check with custom directory and max age
python scripts/monitor_exports.py --export-dir /mnt/exports --max-age-hours 20

# Verify specific sites scraped
python scripts/monitor_exports.py --expected-sites g2a,g2g

# Output as JSON for automated monitoring
python scripts/monitor_exports.py --json | jq '.status'
```

#### Checks Performed

1. **Export Recency**: Verifies that recent CSV exports exist
2. **Manifest Validity**: Validates manifest.json structure and content
3. **Exports Exist**: Confirms all files referenced in manifest are present
4. **Integrity Check**: Verifies SHA-256 checksums match manifest
5. **Site Coverage**: Confirms all expected sites have scrape data

#### Exit Codes

- `0`: All checks passed
- `1`: One or more checks failed

#### Integration Examples

**Cron Job with Email Alert**

```bash
#!/bin/bash
EXPORT_DIR=/var/lib/apex/exports
ALERT_EMAIL=ops@apex-digital.local

if ! python /opt/apex-market-scraper/scripts/monitor_exports.py \
    --export-dir "$EXPORT_DIR" \
    --expected-sites g2a,g2g; then
    python /opt/apex-market-scraper/scripts/monitor_exports.py \
        --export-dir "$EXPORT_DIR" --json | \
        mail -s "ALERT: Apex Scraper Monitoring Failed" "$ALERT_EMAIL"
    exit 1
fi
```

**Prometheus Exporter Integration**

```python
from prometheus_client import Gauge
import subprocess
import json

scraper_health = Gauge('apex_scraper_health', 'Scraper export health (1=ok, 0=fail)')

result = subprocess.run(
    ['python', 'scripts/monitor_exports.py', '--json'],
    capture_output=True,
    text=True
)
data = json.loads(result.stdout)
scraper_health.set(1 if data['status'] == 'OK' else 0)
```

**Kubernetes ConfigMap**

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: apex-scraper-healthcheck
data:
  healthcheck.sh: |
    #!/bin/bash
    cd /app
    python scripts/monitor_exports.py \
      --export-dir /exports \
      --expected-sites g2a,g2g
    exit $?
```

## Future Scripts

The following scripts are planned for future releases:

- `retention.py`: Automated cleanup of old exports (retention policies)
- `import_tracker.py`: Track imports into Apex-digital bot
- `performance_metrics.py`: Collect scraping performance statistics
- `reconcile_inventory.py`: Validate scraped data against Apex inventory

## Adding New Scripts

When adding new operational scripts:

1. Use Python 3.11+ with type hints
2. Include docstrings for all functions
3. Use `argparse` for CLI arguments
4. Support JSON output for automation
5. Include comprehensive error handling
6. Document usage in this README
7. Add tests in `tests/test_scripts.py`
