from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from apex_market_scraper.config.models import SiteConfig
from apex_market_scraper.core.models import HttpResponse, RequestSpec
from apex_market_scraper.sites.g2a import G2AScraper


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "g2a"


def load_fixture(filename: str) -> str:
    return (FIXTURES_DIR / filename).read_text(encoding="utf-8")


def load_json_fixture(filename: str) -> dict[str, Any]:
    return json.loads(load_fixture(filename))


def create_scraper(**params: Any) -> G2AScraper:
    site = SiteConfig(
        name="g2a_test",
        kind="g2a",
        enabled=True,
        api_key_env=None,
        params=params,
    )
    return G2AScraper(site=site, api_key=None, task_id="test-task")


def create_response(text: str, url: str = "https://www.g2a.com/marketplace/search?page=1") -> HttpResponse:
    return HttpResponse(
        url=url,
        status_code=200,
        headers={"Content-Type": "application/json"},
        text=text,
        content=text.encode("utf-8"),
    )


class TestG2AScraperBasics:
    def test_scraper_registration(self) -> None:
        scraper = create_scraper()
        assert scraper.site.kind == "g2a"
        assert scraper.base_url == "https://www.g2a.com"

    def test_custom_base_url(self) -> None:
        scraper = create_scraper(base_url="https://custom.g2a.com")
        assert scraper.base_url == "https://custom.g2a.com"

    def test_build_requests_default(self) -> None:
        scraper = create_scraper()
        requests = scraper.build_requests()
        
        assert len(requests) == 5
        assert all(isinstance(r, RequestSpec) for r in requests)
        assert requests[0].url == "https://www.g2a.com/marketplace/search?page=1"
        assert requests[4].url == "https://www.g2a.com/marketplace/search?page=5"

    def test_build_requests_custom_category(self) -> None:
        scraper = create_scraper(category="steam-keys", max_pages=2)
        requests = scraper.build_requests()
        
        assert len(requests) == 2
        assert requests[0].url == "https://www.g2a.com/marketplace/search/steam-keys?page=1"
        assert requests[1].url == "https://www.g2a.com/marketplace/search/steam-keys?page=2"

    def test_dry_run(self) -> None:
        scraper = create_scraper()
        request = RequestSpec(url="https://www.g2a.com/marketplace/search?page=1")
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
        assert listings[0]["title"] == "G2A Steam Key - Popular Game"
        assert listings[0]["price"] == 19.99


class TestG2AJSONParsing:
    def test_parse_normal_listings(self) -> None:
        scraper = create_scraper()
        fixture_text = load_fixture("normal_listings.json")
        response = create_response(fixture_text)
        request = RequestSpec(url="https://www.g2a.com/marketplace/search?page=1")
        
        listings = scraper.parse_listing(response, request)
        
        assert len(listings) > 0
        
        # Check first listing structure
        first_listing = listings[0]
        assert "title" in first_listing
        assert "price" in first_listing
        assert "url" in first_listing
        
    def test_parse_json_with_products_key(self) -> None:
        scraper = create_scraper()
        data = {
            "products": [
                {
                    "id": "12345",
                    "title": "Test Game Steam Key",
                    "price": 15.99,
                    "currency": "USD",
                    "minPieces": 1,
                    "maxPieces": 10,
                    "sellerReputation": "4.5",
                    "soldNumber": 456,
                    "stock": 8,
                    "deliveryEstimates": "1-3 minutes",
                    "guaranteeTiers": "7-day guarantee",
                    "category": "Steam Keys",
                    "description": "Digital delivery",
                    "url": "/product/12345"
                }
            ]
        }
        
        response = create_response(json.dumps(data))
        request = RequestSpec(url="https://www.g2a.com/marketplace/search?page=1")
        
        listings = scraper.parse_listing(response, request)
        
        assert len(listings) == 1
        listing = listings[0]
        assert listing["title"] == "Test Game Steam Key"
        assert listing["price"] == 15.99
        assert listing["minPieces"] == 1
        assert listing["maxPieces"] == 10

    def test_parse_json_with_items_key(self) -> None:
        scraper = create_scraper()
        data = {
            "items": [
                {
                    "productId": "67890",
                    "productName": "Epic Games Key",
                    "priceUsd": 25.50,
                    "currencyCode": "USD",
                    "minQuantity": 1,
                    "maxQuantity": 25,
                    "sellerRating": "4.8",
                    "soldCount": 789,
                    "stockQuantity": 15,
                    "deliveryTime": "Instant",
                    "platform": "Epic Games Store",
                    "category": "PC Games",
                    "url": "/product/67890"
                }
            ]
        }
        
        response = create_response(json.dumps(data))
        request = RequestSpec(url="https://www.g2a.com/marketplace/search?page=1")
        
        listings = scraper.parse_listing(response, request)
        
        assert len(listings) == 1
        listing = listings[0]
        assert listing["title"] == "Epic Games Key"
        assert listing["price"] == 25.50
        assert listing["sellerReputation"] == "4.8"

    def test_category_whitelist_filtering(self) -> None:
        scraper = create_scraper(
            category_whitelist=["Steam", "Epic", "Gaming"]
        )
        
        data = {
            "products": [
                {
                    "id": "1",
                    "title": "Steam Game Key",
                    "price": 19.99,
                    "currency": "USD",
                    "category": "Steam Keys - Action Games",
                    "url": "/product/1"
                },
                {
                    "id": "2", 
                    "title": "Console Game",
                    "price": 29.99,
                    "currency": "USD",
                    "category": "PlayStation - RPG",
                    "url": "/product/2"
                },
                {
                    "id": "3",
                    "title": "Epic Store Game", 
                    "price": 39.99,
                    "currency": "USD",
                    "category": "Epic Games Store - Strategy",
                    "url": "/product/3"
                }
            ]
        }
        
        response = create_response(json.dumps(data))
        request = RequestSpec(url="https://www.g2a.com/marketplace/search?page=1")
        
        listings = scraper.parse_listing(response, request)
        
        # Should only include products 1 and 3 (contain whitelist terms)
        assert len(listings) == 2
        titles = [l["title"] for l in listings]
        assert "Steam Game Key" in titles
        assert "Epic Store Game" in titles
        assert "Console Game" not in titles

    def test_missing_critical_fields_filtering(self) -> None:
        scraper = create_scraper()
        
        data = {
            "products": [
                {
                    "id": "1",
                    "title": "Valid Product",
                    "price": 19.99,
                    "url": "/product/1"
                },
                {
                    "id": "2",
                    "title": "",  # Empty title
                    "price": 29.99,
                    "url": "/product/2"
                },
                {
                    "id": "3",
                    "title": "No Price Product",
                    # Missing price
                    "url": "/product/3"
                },
                {
                    "id": "4",
                    "title": "No URL Product",
                    "price": 39.99,
                    # Missing URL
                }
            ]
        }
        
        response = create_response(json.dumps(data))
        request = RequestSpec(url="https://www.g2a.com/marketplace/search?page=1")
        
        listings = scraper.parse_listing(response, request)
        
        # Should only include the first valid product
        assert len(listings) == 1
        assert listings[0]["title"] == "Valid Product"


class TestG2AHTMLParsing:
    def test_parse_html_listings(self) -> None:
        scraper = create_scraper()
        html = load_fixture("normal_listings.html")
        response = create_response(html, "https://www.g2a.com/marketplace/search")
        request = RequestSpec(url="https://www.g2a.com/marketplace/search?page=1")
        
        listings = scraper.parse_listing(response, request)
        
        assert len(listings) > 0
        
        # Check structure of extracted listings
        for listing in listings:
            assert "title" in listing
            assert "price" in listing
            assert "url" in listing

    def test_extract_from_html_minimal_data(self) -> None:
        scraper = create_scraper()
        html = '''
        <div class="product-card">
            <h2 class="title">Test Product</h2>
            <span class="price">$24.99</span>
            <a href="/product/123" class="link">View Details</a>
            <div data-stock="5" data-rating="4.5" data-min-pieces="1" data-max-pieces="10"></div>
        </div>
        '''
        
        result = scraper._extract_from_html(html, "https://www.g2a.com")
        
        assert result is not None
        assert result["title"] == "Test Product"
        assert result["price"] == 24.99
        assert result["stock"] == 5
        assert result["sellerReputation"] == "4.5"
        assert result["minPieces"] == 1
        assert result["maxPieces"] == 10
        assert "/product/123" in result["url"]


class TestG2ANormalization:
    def test_normalize_price_to_cents(self) -> None:
        scraper = create_scraper()
        
        # Test basic price normalization
        assert scraper._normalize_price(19.99, "USD") == 1999
        assert scraper._normalize_price(10.0, "USD") == 1000
        
        # Test currency conversion
        assert scraper._normalize_price(20.0, "EUR") == 2160  # 20 * 1.08 * 100
        
        # Test invalid price
        assert scraper._normalize_price(None, "USD") is None
        assert scraper._normalize_price("invalid", "USD") is None

    def test_parse_seller_rating_percentage(self) -> None:
        scraper = create_scraper()
        
        # Test percentage format
        assert scraper._parse_rating("95%") == 0.95
        assert scraper._parse_rating("87.5%") == 0.875
        
        # Test /5 format
        assert scraper._parse_rating("4.5/5") == 0.9
        assert scraper._parse_rating("3.2/5") == 0.64
        
        # Test decimal format
        assert scraper._parse_rating("0.95") == 0.95
        assert scraper._parse_rating("4.5") == 0.9
        
        # Test invalid
        assert scraper._parse_rating(None) is None
        assert scraper._parse_rating("invalid") is None

    def test_currency_handling(self) -> None:
        scraper = create_scraper()
        
        # Test default currency
        assert scraper._get_currency(None) == "USD"
        assert scraper._get_currency("") == "USD"
        
        # Test currency overrides
        scraper.currency_overrides = {"EUR": "EUR", "GBP": "GBP"}
        assert scraper._get_currency("eur") == "EUR"
        assert scraper._get_currency("GBP") == "GBP"

    def test_category_whitelist_matching(self) -> None:
        scraper = create_scraper(category_whitelist=["Steam", "Epic"])
        
        # Test matching categories
        assert scraper._is_category_allowed("Steam Keys") is True
        assert scraper._is_category_allowed("Epic Games Store") is True
        assert scraper._is_category_allowed("Steam - Action Games") is True
        
        # Test non-matching categories
        assert scraper._is_category_allowed("PlayStation Games") is False
        assert scraper._is_category_allowed("Xbox Store") is False
        
        # Test empty/whitespace
        assert scraper._is_category_allowed("") is True
        assert scraper._is_category_allowed(None) is True

    def test_delivery_eta_normalization(self) -> None:
        scraper = create_scraper()
        
        # Test valid delivery times
        assert scraper._normalize_delivery_eta("2-5 minutes") == "2-5 minutes"
        assert scraper._normalize_delivery_eta("Instant") == "Instant"
        assert scraper._normalize_delivery_eta("1-24 hours") == "1-24 hours"
        
        # Test invalid/empty
        assert scraper._normalize_delivery_eta("") is None
        assert scraper._normalize_delivery_eta("unknown") is None
        assert scraper._normalize_delivery_eta(None) is None

    def test_warranty_normalization(self) -> None:
        scraper = create_scraper()
        
        # Test valid warranties
        assert scraper._normalize_warranty("14-day guarantee") == "14-day guarantee"
        assert scraper._normalize_warranty("30 days") == "30 days"
        
        # Test invalid/empty
        assert scraper._normalize_warranty("") is None
        assert scraper._normalize_warranty("none") is None
        assert scraper._normalize_warranty("N/A") is None
        assert scraper._normalize_warranty("0") is None
        assert scraper._normalize_warranty(None) is None


class TestG2AProductRecordNormalization:
    def test_normalize_complete_record(self) -> None:
        scraper = create_scraper()
        raw = {
            "title": "Test Game Steam Key",
            "category": "Steam Keys",
            "price": 19.99,
            "currency": "USD",
            "minPieces": 1,
            "maxPieces": 10,
            "sellerReputation": "4.5",
            "soldNumber": 456,
            "stock": 8,
            "deliveryEstimates": "2-5 minutes",
            "guaranteeTiers": "14-day guarantee",
            "refillAvailable": True,
            "description": "Digital delivery",
            "url": "/product/123",
            "metadata": {"sellerId": "seller123"}
        }
        
        record = scraper.normalize_record(raw)
        
        assert record.product_name == "Test Game Steam Key"
        assert record.category == "Steam Keys"
        assert record.price == 1999  # Converted to cents
        assert record.currency == "USD"
        assert record.min_quantity == 1.0
        assert record.max_quantity == 10.0
        assert record.seller_rating == 0.9  # 4.5/5 normalized
        assert record.sold_amount == 456
        assert record.stock == 8
        assert record.delivery_eta == "2-5 minutes"
        assert record.refill_available is True
        assert record.warranty == "14-day guarantee"
        assert "/product/123" in record.product_url
        assert record.hidden_link_metadata["sellerId"] == "seller123"

    def test_normalize_partial_record(self) -> None:
        scraper = create_scraper()
        raw = {
            "title": "Incomplete Product",
            "price": 9.99,
            "currency": "EUR",
            "url": "/product/456"
        }
        
        record = scraper.normalize_record(raw)
        
        assert record.product_name == "Incomplete Product"
        assert record.price == 1079  # 9.99 * 1.08 * 100
        assert record.currency == "EUR"
        assert record.category is None
        assert record.min_quantity is None
        assert record.max_quantity is None
        assert record.seller_rating is None

    def test_normalize_different_field_variations(self) -> None:
        scraper = create_scraper()
        raw = {
            "productName": "Alternative Title",
            "gameCategory": "Action",
            "amount": 15.50,
            "currencyCode": "USD",
            "minQuantity": 5,
            "maxQuantity": 100,
            "sellerRating": "3.8/5",
            "sold_count": 234,
            "stockQuantity": 12,
            "deliveryTime": "Instant",
            "warranty": "7 days",
            "is_refillable": False,
            "productDescription": "Fast delivery",
            "link": "/alt/789"
        }
        
        record = scraper.normalize_record(raw)
        
        assert record.product_name == "Alternative Title"
        assert record.category == "Action"
        assert record.price == 1550
        assert record.min_quantity == 5.0
        assert record.max_quantity == 100.0
        assert record.seller_rating == 0.76  # 3.8/5 normalized
        assert record.sold_amount == 234
        assert record.stock == 12
        assert record.delivery_eta == "Instant"
        assert record.refill_available is False
        assert record.warranty == "7 days"
        assert "/alt/789" in record.product_url


class TestG2AEdgeCases:
    def test_empty_response(self) -> None:
        scraper = create_scraper()
        response = create_response("")
        request = RequestSpec(url="https://www.g2a.com/marketplace/search?page=1")
        
        listings = scraper.parse_listing(response, request)
        assert len(listings) == 0

    def test_invalid_json_response(self) -> None:
        scraper = create_scraper()
        response = create_response("invalid json{")
        request = RequestSpec(url="https://www.g2a.com/marketplace/search?page=1")
        
        # Should fallback to HTML parsing
        listings = scraper.parse_listing(response, request)
        assert isinstance(listings, list)

    def test_malformed_html_response(self) -> None:
        scraper = create_scraper()
        response = create_response("<html><body><div>malformed</div>")
        request = RequestSpec(url="https://www.g2a.com/marketplace/search?page=1")
        
        listings = scraper.parse_listing(response, request)
        # Should handle gracefully and return empty or partial results
        assert isinstance(listings, list)

    def test_conversion_rates(self) -> None:
        scraper = create_scraper()
        
        # Test known conversion rates
        assert scraper._convert_to_usd(100, "EUR") == 108.0
        assert scraper._convert_to_usd(100, "GBP") == 127.0
        assert scraper._convert_to_usd(100, "PLN") == 25.0
        
        # Test unknown currency (should return same value)
        assert scraper._convert_to_usd(100, "XXX") == 100.0