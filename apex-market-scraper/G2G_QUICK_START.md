# G2G Scraper Quick Start Guide

## Installation

```bash
cd apex-market-scraper
pip install -r requirements.txt -r requirements-dev.txt
```

## Basic Usage

### 1. Dry Run (No Network Calls)

```bash
python -m apex_market_scraper.cli \
  --config configs/sites/g2g.yaml \
  scrape \
  --sites g2g_main \
  --dry-run \
  --raw-json tmp/g2g.json
```

**Output:** Creates `tmp/g2g.json` with sample records

### 2. Live Scrape

```bash
python -m apex_market_scraper.cli \
  --config configs/sites/g2g.yaml \
  scrape \
  --sites g2g_main \
  --raw-json tmp/g2g_live.json
```

**Note:** Adjust `throttle_seconds` in config for production use

### 3. Run Tests

```bash
# All G2G tests
pytest tests/test_g2g_parser.py -v

# Specific test class
pytest tests/test_g2g_parser.py::TestG2GNormalization -v

# All tests
pytest tests/ -v
```

## Configuration

Edit `configs/sites/g2g.yaml`:

```yaml
sites:
  - name: g2g_main
    kind: g2g
    enabled: true
    params:
      base_url: https://www.g2g.com
      category: ""  # or "world-of-warcraft", "final-fantasy-xiv", etc.
      max_pages: 5
      throttle_seconds: 1.0  # Increase for production
```

## Common Tasks

### Change Scraping Category

```yaml
params:
  category: "world-of-warcraft"  # Specific game/category
```

### Scrape More Pages

```yaml
params:
  max_pages: 10  # Increase page limit
```

### Adjust Rate Limiting

```yaml
params:
  throttle_seconds: 2.0  # 2 seconds between requests
  max_attempts: 5        # More retry attempts
```

## Output Schema

Each product record includes:

```json
{
  "site": "g2g_main",
  "site_kind": "g2g",
  "name": "Product Name",
  "category": "Category",
  "price": 1599.0,              // In cents (15.99 USD)
  "currency": "USD",
  "min_quantity": 1.0,
  "max_quantity": 100.0,
  "seller_rating": 4.8,
  "sold_amount": 523,
  "stock": 50,
  "delivery_eta": "5-10 minutes",
  "refill_available": true,
  "warranty": "30 days",
  "url": "https://www.g2g.com/offer/12345",
  "hidden_link_metadata": {
    "listingId": "12345",
    "sellerId": "seller123"
  }
}
```

## Troubleshooting

### No records returned
- Check if `max_pages` is sufficient
- Verify category path is correct
- Check logs for parsing errors

### Rate limiting errors
- Increase `throttle_seconds`
- Reduce `max_pages`
- Add delays between runs

### Price conversion issues
- Check `default_currency` setting
- Verify conversion rates in `_convert_to_usd` method

## Next Steps

1. Test with real G2G endpoints
2. Adjust selectors if site structure differs
3. Configure scheduler for automated runs
4. Set up export to CSV/Excel for bot import

## Documentation

- Full docs: [docs/G2G_SCRAPER.md](docs/G2G_SCRAPER.md)
- Implementation: [G2G_IMPLEMENTATION_SUMMARY.md](G2G_IMPLEMENTATION_SUMMARY.md)
