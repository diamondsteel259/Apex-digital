from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from apex_market_scraper.config.models import SiteConfig
from apex_market_scraper.core.models import HttpResponse, RequestSpec
from apex_market_scraper.sites.g2g import G2GScraper


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "g2g"


def load_fixture(filename: str) -> str:
    return (FIXTURES_DIR / filename).read_text(encoding="utf-8")


def load_json_fixture(filename: str) -> dict[str, Any]:
    return json.loads(load_fixture(filename))


def create_scraper(**params: Any) -> G2GScraper:
    site = SiteConfig(
        name="g2g_test",
        kind="g2g",
        enabled=True,
        api_key_env=None,
        params=params,
    )
    return G2GScraper(site=site, api_key=None, task_id="test-task")


def create_response(text: str, url: str = "https://www.g2g.com/offers?page=1") -> HttpResponse:
    return HttpResponse(
        url=url,
        status_code=200,
        headers={"Content-Type": "application/json"},
        text=text,
        content=text.encode("utf-8"),
    )


class TestG2GScraperBasics:
    def test_scraper_registration(self) -> None:
        scraper = create_scraper()
        assert scraper.site.kind == "g2g"
        assert scraper.base_url == "https://www.g2g.com"

    def test_custom_base_url(self) -> None:
        scraper = create_scraper(base_url="https://custom.g2g.com")
        assert scraper.base_url == "https://custom.g2g.com"

    def test_build_requests_default(self) -> None:
        scraper = create_scraper()
        requests = scraper.build_requests()
        
        assert len(requests) == 5
        assert all(isinstance(r, RequestSpec) for r in requests)
        assert requests[0].url == "https://www.g2g.com/offers?page=1"
        assert requests[4].url == "https://www.g2g.com/offers?page=5"

    def test_build_requests_custom_category(self) -> None:
        scraper = create_scraper(category="world-of-warcraft", max_pages=2)
        requests = scraper.build_requests()
        
        assert len(requests) == 2
        assert requests[0].url == "https://www.g2g.com/world-of-warcraft?page=1"
        assert requests[1].url == "https://www.g2g.com/world-of-warcraft?page=2"

    def test_dry_run(self) -> None:
        scraper = create_scraper()
        request = RequestSpec(url="https://www.g2g.com/offers?page=1")
        response = HttpResponse(
            url=request.url,
            status_code=0,
            headers={},
            text="",
            content=b"",
            is_dry_run=True,
        )
        
        listings = scraper.parse_listing(response, request)
        
        assert len(listings) == 1
        assert listings[0]["title"] == "G2G Gaming Currency - 1000 Gold"
        assert listings[0]["price"] == 9.99


class TestG2GJSONParsing:
    def test_parse_normal_listings(self) -> None:
        scraper = create_scraper()
        fixture_text = load_fixture("normal_listings.json")
        response = create_response(fixture_text)
        request = RequestSpec(url="https://www.g2g.com/offers?page=1")
        
        listings = scraper.parse_listing(response, request)
        
        assert len(listings) == 3
        
        first = listings[0]
        assert first["title"] == "World of Warcraft Gold - 1000g"
        assert first["price"] == 15.99
        assert first["currency"] == "USD"
        assert first["minQty"] == 1
        assert first["maxQty"] == 100
        assert first["sellerRating"] == 4.8
        assert first["soldCount"] == 523
        assert first["stock"] == 50
        assert first["deliveryEta"] == "5-10 minutes"
        assert first["warranty"] == "30 days"
        assert first["refillAvailable"] is True
        assert first["url"] == "https://www.g2g.com/offer/12345"

    def test_parse_no_stock_listing(self) -> None:
        scraper = create_scraper()
        fixture_text = load_fixture("no_stock.json")
        response = create_response(fixture_text)
        request = RequestSpec(url="https://www.g2g.com/offers?page=1")
        
        listings = scraper.parse_listing(response, request)
        
        assert len(listings) == 1
        assert listings[0]["stock"] == 0

    def test_parse_preorder_listing(self) -> None:
        scraper = create_scraper()
        fixture_text = load_fixture("preorder.json")
        response = create_response(fixture_text)
        request = RequestSpec(url="https://www.g2g.com/offers?page=1")
        
        listings = scraper.parse_listing(response, request)
        
        assert len(listings) == 1
        listing = listings[0]
        assert listing["deliveryEta"] == "Available on release day"
        assert listing["metadata"]["preorder"] is True

    def test_parse_variable_delivery_windows(self) -> None:
        scraper = create_scraper()
        fixture_text = load_fixture("variable_delivery.json")
        response = create_response(fixture_text)
        request = RequestSpec(url="https://www.g2g.com/offers?page=1")
        
        listings = scraper.parse_listing(response, request)
        
        assert len(listings) == 3
        assert listings[0]["deliveryEta"] == "1-3 hours"
        assert listings[1]["deliveryEta"] == "5-30 minutes"
        assert listings[2]["deliveryEta"] == "30 minutes - 2 hours"

    def test_parse_edge_cases(self) -> None:
        scraper = create_scraper()
        fixture_text = load_fixture("edge_cases.json")
        response = create_response(fixture_text)
        request = RequestSpec(url="https://www.g2g.com/offers?page=1")
        
        listings = scraper.parse_listing(response, request)
        
        assert len(listings) == 4
        
        minimal = listings[0]
        assert minimal["title"] == "Missing Fields Test"
        assert minimal["price"] == 9.99
        assert minimal["minQty"] is None
        
        eur_listing = listings[1]
        assert eur_listing["currency"] == "EUR"
        assert eur_listing["warranty"] is None
        
        alt_fields = listings[2]
        assert alt_fields["title"] == "Alternative Name Field"
        assert alt_fields["currency"] == "GBP"
        assert alt_fields["minQty"] == 2
        assert alt_fields["maxQty"] == 20
        
        string_numbers = listings[3]
        assert string_numbers["price"] == "12.99"
        assert string_numbers["soldCount"] == "999"


class TestG2GHTMLParsing:
    def test_parse_html_listings(self) -> None:
        scraper = create_scraper()
        fixture_text = load_fixture("html_listing.html")
        response = create_response(fixture_text)
        request = RequestSpec(url="https://www.g2g.com/offers?page=1")
        
        listings = scraper.parse_listing(response, request)
        
        assert len(listings) == 2
        
        first = listings[0]
        assert first["title"] == "HTML Parsed Listing - Test Item"
        assert first["price"] == 19.99
        assert first["currency"] == "USD"
        assert first["stock"] == 75
        assert first["sellerRating"] == "4.7"
        assert "offer/12357" in first["url"]


class TestG2GNormalization:
    def test_normalize_normal_record(self) -> None:
        scraper = create_scraper()
        raw = {
            "title": "Test Item",
            "category": "Test Category",
            "price": 10.00,
            "currency": "USD",
            "minQty": 1,
            "maxQty": 50,
            "sellerRating": 4.5,
            "soldCount": 100,
            "stock": 25,
            "deliveryEta": "10 minutes",
            "warranty": "30 days",
            "refillAvailable": True,
            "description": "Test description",
            "url": "https://www.g2g.com/offer/12345",
            "metadata": {"listingId": "12345"},
        }
        
        record = scraper.normalize_record(raw)
        
        assert record.product_name == "Test Item"
        assert record.category == "Test Category"
        assert record.price == 1000.0
        assert record.currency == "USD"
        assert record.min_quantity == 1.0
        assert record.max_quantity == 50.0
        assert record.seller_rating == 4.5
        assert record.sold_amount == 100
        assert record.stock == 25
        assert record.delivery_eta == "10 minutes"
        assert record.warranty == "30 days"
        assert record.refill_available is True
        assert record.product_url == "https://www.g2g.com/offer/12345"

    def test_normalize_with_missing_optional_fields(self) -> None:
        scraper = create_scraper()
        raw = {
            "title": "Minimal Item",
            "price": 5.00,
            "currency": "USD",
            "url": "https://www.g2g.com/offer/99999",
        }
        
        record = scraper.normalize_record(raw)
        
        assert record.product_name == "Minimal Item"
        assert record.price == 500.0
        assert record.category is None
        assert record.min_quantity is None
        assert record.max_quantity is None
        assert record.seller_rating is None
        assert record.sold_amount is None
        assert record.stock is None

    def test_price_normalization_to_cents(self) -> None:
        scraper = create_scraper()
        
        assert scraper._normalize_price(10.00, "USD") == 1000.0
        assert scraper._normalize_price(1.99, "USD") == 199.0
        assert scraper._normalize_price(0.50, "USD") == 50.0
        assert scraper._normalize_price(None, "USD") is None

    def test_currency_conversion_to_usd(self) -> None:
        scraper = create_scraper()
        
        eur_price = scraper._normalize_price(10.00, "EUR")
        assert eur_price is not None
        assert eur_price > 1000.0
        
        gbp_price = scraper._normalize_price(10.00, "GBP")
        assert gbp_price is not None
        assert gbp_price > 1000.0

    def test_custom_currency_overrides(self) -> None:
        scraper = create_scraper(
            currency_overrides={"EUR": "USD", "GBP": "USD"}
        )
        
        assert scraper._get_currency("EUR") == "USD"
        assert scraper._get_currency("GBP") == "USD"
        assert scraper._get_currency("JPY") == "JPY"

    def test_rating_parsing(self) -> None:
        scraper = create_scraper()
        
        assert scraper._parse_rating(4.5) == 4.5
        assert scraper._parse_rating("4.5") == 4.5
        assert scraper._parse_rating("4.5/5") == 4.5
        assert scraper._parse_rating("Rating: 4.8") == 4.8
        assert scraper._parse_rating(None) is None
        assert scraper._parse_rating("invalid") is None

    def test_int_parsing(self) -> None:
        scraper = create_scraper()
        
        assert scraper._parse_int(100) == 100
        assert scraper._parse_int("100") == 100
        assert scraper._parse_int("1,000") == 1000
        assert scraper._parse_int(None) is None
        assert scraper._parse_int("") is None

    def test_bool_parsing(self) -> None:
        scraper = create_scraper()
        
        assert scraper._parse_bool(True) is True
        assert scraper._parse_bool(False) is False
        assert scraper._parse_bool("true") is True
        assert scraper._parse_bool("yes") is True
        assert scraper._parse_bool("available") is True
        assert scraper._parse_bool("false") is False
        assert scraper._parse_bool(None) is None

    def test_delivery_eta_normalization(self) -> None:
        scraper = create_scraper()
        
        assert scraper._normalize_delivery_eta("10 minutes") == "10 minutes"
        assert scraper._normalize_delivery_eta("1-3 hours") == "1-3 hours"
        assert scraper._normalize_delivery_eta("") is None
        assert scraper._normalize_delivery_eta("unknown") is None
        assert scraper._normalize_delivery_eta(None) is None

    def test_warranty_normalization(self) -> None:
        scraper = create_scraper()
        
        assert scraper._normalize_warranty("30 days") == "30 days"
        assert scraper._normalize_warranty("90 days") == "90 days"
        assert scraper._normalize_warranty("") is None
        assert scraper._normalize_warranty("none") is None
        assert scraper._normalize_warranty("n/a") is None
        assert scraper._normalize_warranty(None) is None


class TestG2GCriticalFieldValidation:
    def test_has_critical_fields_valid(self) -> None:
        scraper = create_scraper()
        
        valid_item = {
            "title": "Test",
            "price": 10.00,
            "url": "https://www.g2g.com/offer/123",
        }
        assert scraper._has_critical_fields(valid_item) is True

    def test_has_critical_fields_missing_title(self) -> None:
        scraper = create_scraper()
        
        invalid_item = {
            "price": 10.00,
            "url": "https://www.g2g.com/offer/123",
        }
        assert scraper._has_critical_fields(invalid_item) is False

    def test_has_critical_fields_missing_price(self) -> None:
        scraper = create_scraper()
        
        invalid_item = {
            "title": "Test",
            "url": "https://www.g2g.com/offer/123",
        }
        assert scraper._has_critical_fields(invalid_item) is False

    def test_has_critical_fields_missing_url(self) -> None:
        scraper = create_scraper()
        
        invalid_item = {
            "title": "Test",
            "price": 10.00,
        }
        assert scraper._has_critical_fields(invalid_item) is False

    def test_has_critical_fields_alternative_name(self) -> None:
        scraper = create_scraper()
        
        valid_item = {
            "name": "Test",
            "price": 10.00,
            "link": "https://www.g2g.com/offer/123",
        }
        assert scraper._has_critical_fields(valid_item) is True


class TestG2GIntegration:
    def test_full_scrape_workflow(self) -> None:
        scraper = create_scraper(max_pages=1)
        fixture_text = load_fixture("normal_listings.json")
        response = create_response(fixture_text)
        request = RequestSpec(url="https://www.g2g.com/offers?page=1")
        
        raw_listings = scraper.parse_listing(response, request)
        records = [scraper.normalize_record(raw) for raw in raw_listings]
        
        assert len(records) == 3
        
        for record in records:
            assert record.site_name == "g2g_test"
            assert record.site_kind == "g2g"
            assert record.product_name != ""
            assert record.price is not None
            assert record.product_url != ""

    def test_scrape_deduplication(self) -> None:
        scraper = create_scraper()
        fixture_text = load_fixture("normal_listings.json")
        response = create_response(fixture_text)
        request = RequestSpec(url="https://www.g2g.com/offers?page=1")
        
        raw_listings = scraper.parse_listing(response, request)
        records = [scraper.normalize_record(raw) for raw in raw_listings]
        
        dedupe_keys = [r.dedupe_key() for r in records]
        assert len(dedupe_keys) == len(set(dedupe_keys))

    def test_to_dict_format(self) -> None:
        scraper = create_scraper()
        raw = {
            "title": "Test Item",
            "price": 10.00,
            "currency": "USD",
            "url": "https://www.g2g.com/offer/12345",
        }
        
        record = scraper.normalize_record(raw)
        data = record.to_dict()
        
        assert data["site"] == "g2g_test"
        assert data["site_kind"] == "g2g"
        assert data["name"] == "Test Item"
        assert data["price"] == 1000.0
        assert data["currency"] == "USD"
        assert data["url"] == "https://www.g2g.com/offer/12345"
        assert "scraped_at" in data
