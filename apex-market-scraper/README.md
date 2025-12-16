# apex-market-scraper

Independent ingestion tool that scrapes supported marketplaces, exports normalized data (CSV/Excel), and hands it off to the Apex-digital Discord bot for import.

This folder is intended to be its own repository (`apex-market-scraper`) while being bootstrapped alongside the bot codebase.

## Goals

- Keep scraping/ingestion independent from the Discord bot runtime.
- Standardize exports (CSV/Excel) so the bot can ingest without coupling to site-specific logic.
- Support running locally (developer machine) or in a container.

## Project layout

- `apex_market_scraper/`
  - `core/` shared utilities (logging, errors)
  - `config/` pydantic models + YAML/JSON loader
  - `sites/` site-specific scrapers
  - `export/` CSV/Excel exporters
  - `scheduler/` cadence runner (12–24h)
  - `cli.py` CLI entrypoint (`python -m apex_market_scraper.cli`)
- `configs/` example YAML configs (site + export + scheduler)
- `tests/` small unit tests for config + CLI

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

## Development notes

- Lint: `ruff check .`
- Tests: `pytest`
- The current implementation provides a working scaffold with an example site scraper.
  Real site implementations should live in `apex_market_scraper/sites/` and be registered via `sites.registry`.
