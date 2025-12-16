# apex-market-scraper

Independent ingestion tool that scrapes supported marketplaces, exports normalized data (CSV/Excel), and hands it off to the Apex-digital Discord bot for import.

This folder is intended to be its own repository (`apex-market-scraper`) while being bootstrapped alongside the bot codebase.

## Goals

- Keep scraping/ingestion independent from the Discord bot runtime.
- Standardize exports (CSV/Excel) matching Apex-digital's template schema.
- Support automated scheduling (12–24h cadence) via cron, systemd, or Docker.
- Generate manifests with checksums and site metadata for audit trails.
- Support running locally (developer machine), in containers, or via CI/CD.

## Key Features

- **CSV & Excel Export**: Converts product records to Apex-digital's template format
- **Manifest Generation**: Auto-generated checksums and scrape timestamps per site
- **Hidden Metadata**: Back-office columns (product URL, source site) hidden in Excel
- **Flexible Scheduling**: CLI support for one-off runs and background cadence
- **Monitoring Tools**: Health checks, integrity verification, alerting
- **Comprehensive Docs**: Setup guides, scheduling options, integration patterns

## Project layout

- `apex_market_scraper/`
  - `core/` shared utilities (logging, HTTP client, models, pipeline)
  - `config/` pydantic models + YAML/JSON loader
  - `sites/` site-specific scrapers (G2A, G2G)
  - `export/` CSV/Excel exporters + manifest generation
  - `scheduler/` configurable cadence runner (12–24h)
  - `cli.py` CLI entrypoint (`python -m apex_market_scraper.cli`)
- `configs/` example YAML/JSON configs (site + export + scheduler)
- `docs/` documentation (scheduling, integration, monitoring)
- `scripts/` operational utilities (export monitoring, health checks)
- `tests/` unit and integration tests (71+ tests, smoke test suite)

## Quick start (local)

### 1) Create a virtualenv

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

### 2) Install dependencies

Poetry:

```bash
poetry install
```

Pip:

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt  # optional
```

### 3) Configure environment variables

```bash
cp .env.example .env
# edit .env
```

### 4) Run the CLI

```bash
python -m apex_market_scraper.cli --help
python -m apex_market_scraper.cli scrape --config configs/example.yaml
python -m apex_market_scraper.cli export --config configs/example.yaml --sample
python -m apex_market_scraper.cli schedule --config configs/example.yaml --once
```

## Quick start (Docker)

```bash
docker build -t apex-market-scraper:local .
docker run --rm --env-file .env apex-market-scraper:local python -m apex_market_scraper.cli --help
```

## Configuration

Configuration is loaded from YAML/JSON into pydantic models.

- Main config path is passed with `--config`, or via `AMSCRAPER_CONFIG_PATH`.
- Site credentials are referenced by env var name (not stored in YAML).
- Scheduler cadence must be **12–24 hours** (inclusive).

Example config: `configs/example.yaml`

### Site configs

Each entry under `sites:` defines a site and its type (`kind`). Site-specific settings are nested under `params`.

### Scheduler

`scheduler.cadence_hours` controls how often `schedule` runs a scrape+export cycle.

### Export / Apex import preferences

`export.output_dir` and `export.formats` define how files are created.

**Handoff to the Apex bot:** configure `export.apex_bot_drop_dir` (or bind-mount a shared volume in Docker) so the bot can watch/import from a stable location.

A simple convention:

- scraper writes exports to: `<apex_bot_drop_dir>/market/`
- bot imports from the same directory on a cadence or on-demand

## Export & Scheduling

### One-off Export (Sample Data)

```bash
python -m apex_market_scraper.cli export --sample
# Outputs: out/market_listings_*.csv, out/market_listings_*.xlsx, out/market_listings_manifest_*.json
```

### Automated Scheduling

Run a complete scrape+export cycle once (e.g., from cron):

```bash
python -m apex_market_scraper.cli schedule --once
```

Or run in background with configurable cadence (12–24 hours):

```bash
python -m apex_market_scraper.cli schedule
# Sleeps and runs again based on config.scheduler.cadence_hours
```

### Export Format & Schema

Exports match Apex-digital's `products_template.xlsx` with columns:
- Main_Category, Sub_Category, Service_Name, Variant_Name
- Price_USD, Start_Time, Duration, Refill_Period, Additional_Info
- **Hidden (back-office only)**: product_url, source_site

### Manifest File

Each export generates `market_listings_manifest_*.json` containing:
- Export version and timestamps
- SHA-256 checksums for all files
- First/last scrape time per site
- Record counts

Example:
```json
{
  "version": "1.0",
  "timestamp": "20240101T120000Z",
  "records_count": 1234,
  "exports": {
    "csv": {"checksum": "abc123...", "size_bytes": 567890},
    "xlsx": {"checksum": "def456...", "size_bytes": 123456}
  },
  "site_metadata": {
    "g2a": {"first_record": "2024-01-01T12:00:00Z", "last_record": "..."},
    "g2g": {"first_record": "...", "last_record": "..."}
  }
}
```

### Integration with Apex-digital Bot

Configure the handoff location in config:

```yaml
export:
  output_dir: "out/"
  formats: ["csv", "xlsx"]
  apex_bot_drop_dir: "/path/to/apex-digital/imports/"
  dataset_name: "market_listings"
```

The bot watches `apex_bot_drop_dir` for new exports and imports them automatically.

## Scheduling Setup

### Via Cron (Recommended for Most Users)

Add to crontab:

```bash
0 2 * * * cd /opt/apex-market-scraper && python -m apex_market_scraper.cli schedule --once >> /var/log/apex-scraper.log 2>&1
```

### Via Systemd Timer (Linux)

See [docs/SCHEDULING_AND_EXPORT_GUIDE.md](docs/SCHEDULING_AND_EXPORT_GUIDE.md) for full setup.

### Via Docker (CI/CD, Kubernetes)

See [docs/SCHEDULING_AND_EXPORT_GUIDE.md](docs/SCHEDULING_AND_EXPORT_GUIDE.md) for Docker and Kubernetes examples.

## Monitoring Exports

Check export health and integrity:

```bash
python scripts/monitor_exports.py --export-dir out/ --expected-sites g2a,g2g

# Output as JSON for automation
python scripts/monitor_exports.py --export-dir out/ --json
```

## Supported Sites

### G2G (Gaming Marketplace)

The G2G scraper extracts product listings from https://www.g2g.com including:
- Product details (name, category, price)
- Seller information (rating, sold count)
- Stock and availability
- Delivery ETA and warranty information
- Refill availability

See [docs/G2G_SCRAPER.md](docs/G2G_SCRAPER.md) for detailed documentation.

### G2A (Gaming Marketplace)

Similar to G2G, scrapes https://www.g2a.com for product listings and seller data.

## Documentation

- **[SCHEDULING_AND_EXPORT_GUIDE.md](docs/SCHEDULING_AND_EXPORT_GUIDE.md)**: Complete scheduling, integration, and monitoring setup
- **[scripts/README.md](scripts/README.md)**: Operational scripts and utilities
- **[docs/G2G_SCRAPER.md](docs/G2G_SCRAPER.md)**: G2G site-specific details

## Environment Variables

- `AMSCRAPER_CONFIG_PATH`: Path to config file (default: `configs/example.json`)
- `AMSCRAPER_OUTPUT_DIR`: Override export output directory
- `AMSCRAPER_CADENCE_HOURS`: Override cadence (12–24)
- `AMSCRAPER_LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)
- `AMSCRAPER_PROXIES`: Comma-separated proxy URLs
- `AMSCRAPER_PROXIES_FILE`: File with proxies (one per line)

## Development notes

- **Lint**: `ruff check .`
- **Type check**: `mypy apex_market_scraper/`
- **Tests**: `pytest tests/`
- **Smoke tests**: `pytest tests/test_export_smoke.py -v` (end-to-end export validation)

The current implementation provides a working scaffold with site scrapers registered via `sites.registry`. New site implementations should follow the `BaseSiteScraper` pattern in `apex_market_scraper/sites/base.py`.
