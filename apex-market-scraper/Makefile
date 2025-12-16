.PHONY: help install install-dev lint test cli-help scrape export schedule docker-build docker-run

help:
	@echo "Targets:"
	@echo "  install       Install runtime deps (pip)"
	@echo "  install-dev   Install runtime + dev deps (pip)"
	@echo "  lint          Run ruff"
	@echo "  test          Run pytest"
	@echo "  cli-help      Show CLI usage"
	@echo "  scrape        Run a single scrape cycle (example config)"
	@echo "  export        Export a sample dataset (example config)"
	@echo "  schedule      Run scheduler once (example config)"
	@echo "  docker-build  Build container image"
	@echo "  docker-run    Run container with help"

install:
	python -m pip install -r requirements.txt

install-dev:
	python -m pip install -r requirements-dev.txt

lint:
	ruff check .

test:
	pytest

cli-help:
	python -m apex_market_scraper.cli --help

scrape:
	python -m apex_market_scraper.cli scrape --config configs/example.yaml

export:
	python -m apex_market_scraper.cli export --config configs/example.yaml --sample

schedule:
	python -m apex_market_scraper.cli schedule --config configs/example.yaml --once

docker-build:
	docker build -t apex-market-scraper:local .

docker-run:
	docker run --rm apex-market-scraper:local
