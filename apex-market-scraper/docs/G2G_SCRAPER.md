# G2G Scraper Documentation

## Overview

The G2G scraper is designed to extract product listings from G2G marketplace (https://www.g2g.com), a popular platform for gaming currency, accounts, and items.

## Features

- **JSON and HTML parsing**: Supports both JSON API responses and HTML page scraping
- **Comprehensive field mapping**: Extracts all required fields including seller stats, stock, warranty, and refill info
- **Currency conversion**: Automatic conversion to USD with configurable rates
- **Price normalization**: Prices converted to cents for Apex ingestion
- **Throttling & rate limiting**: Built-in request throttling to comply with site policies
- **Pagination support**: Configurable page limits for bulk scraping
- **Error handling**: Gracefully skips listings with missing critical fields
- **Edge case handling**: Robust parsing for various data formats and edge cases

## Configuration

### Basic Configuration

Create a configuration file (e.g., `configs/sites/g2g.yaml`):

```yaml
scheduler:
  cadence_hours: 12

export:
  output_dir: out
  formats:
    - csv
    - xlsx
  apex_bot_drop_dir: out/apex_bot_drop
  dataset_name: g2g_market_listings

sites:
  - name: g2g_main
    kind: g2g
    enabled: true
    api_key_env: G2G_API_KEY  # Optional
    params:
      base_url: https://www.g2g.com
      category: ""  # Empty for all, or specific like "world-of-warcraft"
      max_pages: 5
      default_currency: USD
      currency_overrides: {}
      
      # Rate limiting
      throttle_seconds: 1.0
      max_attempts: 3
      backoff_initial_seconds: 0.5
      backoff_max_seconds: 8.0
      jitter_seconds: 0.25
      respect_robots: true
```

### Configuration Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `base_url` | string | `https://www.g2g.com` | Base URL of the G2G site |
| `category` | string | `""` | Category path (empty for all offers) |
| `max_pages` | int | `5` | Maximum number of pages to scrape |
| `default_currency` | string | `USD` | Default currency for listings |
| `currency_overrides` | dict | `{}` | Force specific currencies to another (e.g., `{"EUR": "USD"}`) |
| `throttle_seconds` | float | `1.0` | Delay between requests (seconds) |
| `max_attempts` | int | `3` | Maximum retry attempts for failed requests |
| `respect_robots` | bool | `true` | Respect robots.txt directives |

## Field Mapping

### G2G → Apex Schema

| G2G Field | Apex Field | Notes |
|-----------|------------|-------|
| `title`, `name` | `product_name` | Product title |
| `category` | `category` | Product category |
| `price` | `price` | Normalized to cents (USD) |
| `currency` | `currency` | Currency code |
| `minQuantity`, `min_qty` | `min_quantity` | Minimum order quantity |
| `maxQuantity`, `max_qty` | `max_quantity` | Maximum order quantity |
| `seller.rating`, `sellerRating` | `seller_rating` | Seller rating (0-5) |
| `soldCount`, `sold_count` | `sold_amount` | Total items sold |
| `stock`, `stockQuantity` | `stock` | Available stock |
| `deliveryTime`, `delivery_eta` | `delivery_eta` | Estimated delivery time |
| `refillAvailable`, `refill` | `refill_available` | Whether refills are offered |
| `warranty` | `warranty` | Warranty period |
| `url`, `link` | `product_url` | Product listing URL |

### Hidden Metadata

Additional fields stored in `hidden_link_metadata`:
- `listingId`: Listing identifier
- `sellerId`: Seller identifier
- `preorder`: Whether item is preorder

## Usage

### Scrape with CLI

```bash
# Dry run (no network requests)
python -m apex_market_scraper.cli \
  --config configs/sites/g2g.yaml \
  scrape \
  --sites g2g_main \
  --dry-run \
  --raw-json tmp/g2g.json

# Live scrape
python -m apex_market_scraper.cli \
  --config configs/sites/g2g.yaml \
  scrape \
  --sites g2g_main \
  --raw-json tmp/g2g.json
```

### Programmatic Usage

```python
from apex_market_scraper.config.models import SiteConfig
from apex_market_scraper.sites.g2g import G2GScraper

site = SiteConfig(
    name="g2g",
    kind="g2g",
    enabled=True,
    params={
        "base_url": "https://www.g2g.com",
        "category": "world-of-warcraft",
        "max_pages": 3,
    }
)

scraper = G2GScraper(site=site, api_key=None, task_id="manual-scrape")
records = scraper.scrape()

print(f"Scraped {len(records)} records")
```

## Currency Conversion

The scraper includes built-in conversion rates for common currencies:

| Currency | Rate to USD |
|----------|-------------|
| EUR | 1.08 |
| GBP | 1.27 |
| JPY | 0.0067 |
| CNY | 0.14 |
| KRW | 0.00075 |
| AUD | 0.65 |
| CAD | 0.72 |

Prices are automatically converted to USD and then normalized to cents (multiplied by 100).

Example: EUR 10.00 → USD 10.80 → 1080 cents

## Error Handling

### Critical Fields Validation

Listings must have these fields to be processed:
- `title` or `name`
- `price`
- `url` or `link`

Listings missing any of these are logged and skipped.

### Edge Cases Handled

- **No stock**: Stock can be 0 or null
- **Preorder**: Flagged in metadata, special delivery ETA
- **Variable delivery**: Parsed as-is (e.g., "5-30 minutes", "1-3 hours")
- **String numbers**: Automatically converted (e.g., "100" → 100)
- **Rating formats**: Handles "4.5", "4.5/5", "Rating: 4.8"
- **Alternative field names**: Supports both camelCase and snake_case

## Testing

### Run Tests

```bash
# All G2G tests
pytest tests/test_g2g_parser.py -v

# Specific test
pytest tests/test_g2g_parser.py::TestG2GNormalization::test_price_normalization_to_cents -v
```

### Test Fixtures

Fixtures are located in `tests/fixtures/g2g/`:

- `normal_listings.json`: Standard product listings
- `no_stock.json`: Out of stock scenario
- `preorder.json`: Preorder listing
- `variable_delivery.json`: Various delivery time formats
- `edge_cases.json`: Edge cases and alternative field names
- `html_listing.html`: HTML parsing test

## Throttling & Rate Limiting

The scraper respects site policies:

1. **Throttling**: Configurable delay between requests (default: 1 second)
2. **Robots.txt**: Checks and respects robots.txt directives
3. **Retry logic**: Exponential backoff for failed requests
4. **User agent rotation**: Randomly selects from a pool of user agents
5. **Connection pooling**: Reuses HTTP connections for efficiency

## Output Format

### JSON Output

```json
{
  "site": "g2g_main",
  "site_kind": "g2g",
  "name": "World of Warcraft Gold - 1000g",
  "category": "WoW",
  "price": 1599.0,
  "currency": "USD",
  "description": "Fast delivery, 24/7 support",
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
    "sellerId": "seller123",
    "preorder": false
  },
  "scraped_at": "2025-12-16T10:14:12.569516+00:00",
  "source_updated_at": null
}
```

## Troubleshooting

### No records returned

- Check if site structure has changed
- Verify category path is correct
- Ensure throttle_seconds isn't too aggressive
- Check logs for parsing errors

### Currency conversion issues

- Update conversion rates in `_convert_to_usd` method
- Use `currency_overrides` to force specific currencies

### Rate limiting errors

- Increase `throttle_seconds`
- Reduce `max_pages`
- Check if IP is blocked

## Future Enhancements

Potential improvements for production use:

1. **Dynamic currency rates**: Fetch live exchange rates from an API
2. **Category discovery**: Auto-detect available categories
3. **Search support**: Scrape specific search queries
4. **Seller filtering**: Filter by minimum seller rating
5. **Price range filtering**: Only scrape within price bounds
6. **Incremental updates**: Track changes since last scrape
7. **Anti-bot detection**: Handle CAPTCHAs and bot challenges
8. **Proxy rotation**: Support proxy pools for distributed scraping
