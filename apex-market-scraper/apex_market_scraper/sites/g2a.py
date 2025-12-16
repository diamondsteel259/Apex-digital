from __future__ import annotations

import json
import re
from typing import Any, Mapping
from urllib.parse import urljoin

from apex_market_scraper.core.models import HttpResponse, ProductRecord, RequestSpec
from apex_market_scraper.sites.base import BaseSiteScraper
from apex_market_scraper.sites.registry import register


@register("g2a")
class G2AScraper(BaseSiteScraper):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.base_url = str(self.site.params.get("base_url", "https://www.g2a.com"))
        self.category = str(self.site.params.get("category", ""))
        self.max_pages = int(self.site.params.get("max_pages", 5))
        self.default_currency = str(self.site.params.get("default_currency", "USD"))
        self.currency_overrides = dict(self.site.params.get("currency_overrides", {}))
        self.category_whitelist = list(self.site.params.get("category_whitelist", []))

    def build_requests(self) -> list[RequestSpec]:
        requests = []
        
        if self.category:
            category_path = f"marketplace/search/{self.category}"
        else:
            category_path = "marketplace/search"
        
        for page in range(1, self.max_pages + 1):
            url = urljoin(self.base_url, f"{category_path}?page={page}")
            requests.append(
                RequestSpec(
                    url=url,
                    headers={
                        "Accept": "application/json, text/html",
                        "Accept-Language": "en-US,en;q=0.9",
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    },
                )
            )
        
        return requests

    def parse_listing(self, response: HttpResponse, request: RequestSpec) -> list[Mapping[str, Any]]:
        if response.is_dry_run:
            return self._generate_dry_run_data(request)
        
        try:
            data = json.loads(response.text)
            if isinstance(data, dict) and ("products" in data or "items" in data):
                return self._parse_json_listings(data)
        except (json.JSONDecodeError, ValueError):
            pass
        
        return self._parse_html_listings(response.text, request.url)

    def normalize_record(self, raw: Mapping[str, Any]) -> ProductRecord:
        price = self._normalize_price(raw.get("price") or raw.get("amount") or raw.get("priceUsd"), raw.get("currency") or raw.get("currencyCode"))
        
        min_qty = raw.get("minPieces") or raw.get("minQuantity")
        max_qty = raw.get("maxPieces") or raw.get("maxQuantity")
        
        seller_rating = self._parse_rating(raw.get("sellerReputation") or raw.get("sellerRating"))
        sold_count = self._parse_int(raw.get("soldNumber") or raw.get("soldCount") or raw.get("sold_count"))
        stock = self._parse_int(raw.get("stock") or raw.get("stockQuantity"))
        
        delivery_eta = self._normalize_delivery_eta(raw.get("deliveryEstimates") or raw.get("deliveryEta") or raw.get("deliveryTime"))
        warranty = self._normalize_warranty(raw.get("guaranteeTiers") or raw.get("warranty"))
        
        # Handle refill available field with fallbacks - preserve boolean false values
        refill_available = None
        if "refillAvailable" in raw:
            refill_available = self._parse_bool(raw["refillAvailable"])
        elif "is_refillable" in raw:
            refill_available = self._parse_bool(raw["is_refillable"])
        elif "refill" in raw:
            refill_available = self._parse_bool(raw["refill"])
        
        category = raw.get("category") or raw.get("gameCategory") or raw.get("platformCategory")
        
        return ProductRecord(
            site_name=self.site.name,
            site_kind=self.site.kind,
            product_name=str(raw.get("title") or raw.get("productName") or ""),
            category=str(category) if category else None,
            price=price,
            currency=self._get_currency(raw.get("currency") or raw.get("currencyCode")),
            description=str(raw.get("description")) if raw.get("description") else None,
            min_quantity=float(min_qty) if min_qty is not None else None,
            max_quantity=float(max_qty) if max_qty is not None else None,
            seller_rating=seller_rating,
            sold_amount=sold_count,
            stock=stock,
            delivery_eta=delivery_eta,
            refill_available=refill_available,
            warranty=warranty,
            product_url=str(raw.get("url") or raw.get("link") or ""),
            hidden_link_metadata=dict(raw.get("metadata") or {}),
        )

    def _generate_dry_run_data(self, request: RequestSpec) -> list[Mapping[str, Any]]:
        return [
            {
                "title": "G2A Steam Key - Popular Game",
                "productName": "G2A Steam Key - Popular Game",
                "category": self.category or "gaming",
                "price": 19.99,
                "currency": "USD",
                "minPieces": 1,
                "maxPieces": 50,
                "sellerReputation": "4.7",
                "soldNumber": 1247,
                "stock": 25,
                "deliveryEstimates": "2-5 minutes",
                "guaranteeTiers": "14-day guarantee",
                "refillAvailable": True,
                "description": "Instant digital delivery, 24/7 customer support",
                "url": f"{request.url}#listing-1",
                "metadata": {"listingId": "dry-run-1"},
            }
        ]

    def _parse_json_listings(self, data: dict[str, Any]) -> list[Mapping[str, Any]]:
        listings: list[Mapping[str, Any]] = []
        items = data.get("products", data.get("items", []))
        
        for item in items:
            if not isinstance(item, dict):
                continue
            
            if not self._has_critical_fields(item):
                self.logger.warning("Skipping listing missing critical fields: %s", item.get("id"))
                continue
            
            # Check category whitelist if configured
            if self.category_whitelist and not self._is_category_allowed(item.get("category")):
                continue
            
            listings.append(self._extract_listing_data(item))
        
        return listings

    def _parse_html_listings(self, html: str, base_url: str) -> list[Mapping[str, Any]]:
        listings: list[Mapping[str, Any]] = []
        
        # G2A HTML structure patterns - updated to match their actual layout
        listing_pattern = r'<div[^>]*class="[^"]*product-card[^"]*"[^>]*>(.*?)</div>\s*</div>'
        matches = re.finditer(listing_pattern, html, re.DOTALL | re.IGNORECASE)
        
        for match in matches:
            listing_html = match.group(1)
            listing_data = self._extract_from_html(listing_html, base_url)
            
            if listing_data and self._has_critical_fields(listing_data):
                # Check category whitelist if configured
                if self.category_whitelist and not self._is_category_allowed(listing_data.get("category")):
                    continue
                listings.append(listing_data)
            elif listing_data:
                self.logger.warning("Skipping listing missing critical fields")
        
        return listings

    def _extract_listing_data(self, item: dict[str, Any]) -> dict[str, Any]:
        stock = item.get("stock") or item.get("stockQuantity")
        
        sold_count = item.get("soldNumber")
        if sold_count is None:
            sold_count = item.get("sold_count") or item.get("soldCount")
        
        min_qty = item.get("minPieces")
        if min_qty is None:
            min_qty = item.get("minQuantity") or item.get("min_pieces")
        
        max_qty = item.get("maxPieces")
        if max_qty is None:
            max_qty = item.get("maxQuantity") or item.get("max_pieces")
        
        delivery_eta = item.get("deliveryEstimates")
        if delivery_eta is None:
            delivery_eta = item.get("delivery_eta") or item.get("deliveryTime")
        
        refill = item.get("refillAvailable")
        if refill is None:
            refill = item.get("refill") or item.get("is_refillable")
        
        # Extract seller reputation as percentage
        seller_rep = item.get("sellerReputation")
        if seller_rep is None:
            seller_data = item.get("seller", {})
            if isinstance(seller_data, dict):
                seller_rep = seller_data.get("reputation") or seller_data.get("rating")
            else:
                seller_rep = item.get("sellerRating")
        
        return {
            "title": item.get("title") or item.get("productName") or item.get("name") or "",
            "category": item.get("category") or item.get("gameCategory") or item.get("platformCategory"),
            "price": item.get("price") or item.get("priceUsd") or item.get("amount"),
            "currency": item.get("currency") or item.get("currencyCode") or self.default_currency,
            "minPieces": min_qty,
            "maxPieces": max_qty,
            "sellerReputation": seller_rep or item.get("sellerRating"),
            "soldNumber": sold_count,
            "stock": stock,
            "deliveryEstimates": delivery_eta,
            "guaranteeTiers": item.get("guaranteeTiers") or item.get("warranty"),
            "refillAvailable": refill,
            "description": item.get("description") or item.get("productDescription"),
            "url": item.get("url") or item.get("link") or item.get("productUrl") or "",
            "metadata": {
                "listingId": item.get("id") or item.get("listingId") or item.get("productId"),
                "sellerId": item.get("seller", {}).get("id") if isinstance(item.get("seller"), dict) else item.get("sellerId"),
                "platform": item.get("platform") or item.get("gamePlatform"),
                "region": item.get("region") or item.get("gameRegion"),
                "preorder": item.get("preorder", False),
            },
        }

    def _extract_from_html(self, html: str, base_url: str) -> dict[str, Any] | None:
        try:
            # Extract title
            title_match = re.search(r'<h[23][^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</h[23]>', html, re.DOTALL | re.IGNORECASE)
            title = self._clean_html(title_match.group(1)) if title_match else ""
            
            # Extract price with various G2A patterns
            price_match = re.search(r'data-price="([^"]+)"', html)
            if not price_match:
                price_match = re.search(r'<span[^>]*class="[^"]*price[^"]*"[^>]*>.*?([0-9]+\.?[0-9]*)', html)
            if not price_match:
                price_match = re.search(r'[\$€£¥]\s*([0-9]+\.?[0-9]*)', html)
            price = float(price_match.group(1)) if price_match else None
            
            # Extract currency
            currency_match = re.search(r'data-currency="([^"]+)"', html)
            if not currency_match:
                currency_symbol_match = re.search(r'[\$€£¥]', html)
                currency = None
                if currency_symbol_match:
                    currency_symbol = currency_symbol_match.group(0)
                    currency_map = {"$": "USD", "€": "EUR", "£": "GBP", "¥": "JPY"}
                    currency = currency_map.get(currency_symbol, self.default_currency)
            else:
                currency = currency_match.group(1) if currency_match else self.default_currency
            
            if not currency_match and not currency_symbol_match:
                currency = self.default_currency
            
            # Extract URL
            url_match = re.search(r'href="([^"]+)"', html)
            url = urljoin(base_url, url_match.group(1)) if url_match else base_url
            
            # Extract stock
            stock_match = re.search(r'data-stock="([^"]+)"', html)
            stock = int(stock_match.group(1)) if stock_match else None
            
            # Extract seller reputation
            seller_rating_match = re.search(r'data-rating="([^"]+)"', html)
            seller_rating = seller_rating_match.group(1) if seller_rating_match else None
            
            # Extract category
            category_match = re.search(r'data-category="([^"]+)"', html)
            category = category_match.group(1) if category_match else None
            
            # Extract min/max pieces
            min_pieces_match = re.search(r'data-min-pieces="([^"]+)"', html)
            max_pieces_match = re.search(r'data-max-pieces="([^"]+)"', html)
            min_pieces = int(min_pieces_match.group(1)) if min_pieces_match else None
            max_pieces = int(max_pieces_match.group(1)) if max_pieces_match else None
            
            # Extract delivery estimates
            delivery_match = re.search(r'data-delivery="([^"]+)"', html)
            delivery_eta = delivery_match.group(1) if delivery_match else None
            
            return {
                "title": title,
                "category": category,
                "price": price,
                "currency": currency,
                "minPieces": min_pieces,
                "maxPieces": max_pieces,
                "sellerReputation": seller_rating,
                "soldNumber": None,
                "stock": stock,
                "deliveryEstimates": delivery_eta,
                "guaranteeTiers": None,
                "refillAvailable": None,
                "description": None,
                "url": url,
                "metadata": {},
            }
        except Exception as e:
            self.logger.warning("Failed to extract listing from HTML: %s", e)
            return None

    def _has_critical_fields(self, item: dict[str, Any]) -> bool:
        has_title = bool(item.get("title") or item.get("productName") or item.get("name"))
        has_price = item.get("price") is not None or item.get("amount") is not None or item.get("priceUsd") is not None
        has_url = bool(item.get("url") or item.get("link"))
        
        return has_title and has_price and has_url

    def _is_category_allowed(self, category: str | None) -> bool:
        """Check if category is in the whitelist if configured."""
        if not self.category_whitelist or not category:
            return True
        
        category_lower = category.lower()
        return any(allowed.lower() in category_lower for allowed in self.category_whitelist)

    def _normalize_price(self, price: Any, currency: str | None) -> float | None:
        if price is None:
            return None
        
        try:
            price_float = float(price)
            
            actual_currency = self._get_currency(currency)
            if actual_currency != "USD":
                price_float = self._convert_to_usd(price_float, actual_currency)
            
            return round(price_float * 100)
        except (ValueError, TypeError):
            return None

    def _get_currency(self, currency: str | None) -> str:
        if not currency:
            return self.default_currency
        
        currency_upper = currency.upper()
        return self.currency_overrides.get(currency_upper, currency_upper)

    def _convert_to_usd(self, price: float, from_currency: str) -> float:
        conversion_rates = {
            "EUR": 1.08,
            "GBP": 1.27,
            "JPY": 0.0067,
            "CNY": 0.14,
            "KRW": 0.00075,
            "AUD": 0.65,
            "CAD": 0.72,
            "PLN": 0.25,
            "CZK": 0.044,
            "SEK": 0.095,
            "NOK": 0.094,
        }
        
        rate = conversion_rates.get(from_currency, 1.0)
        return price * rate

    def _parse_rating(self, value: Any) -> float | None:
        if value is None:
            return None
        
        try:
            if isinstance(value, str):
                # Handle percentage values like "95%" or "4.5/5"
                if "%" in value:
                    return float(value.replace("%", "")) / 100.0
                value = value.replace("/5", "").replace("/10", "").strip()
                match = re.search(r'([0-9]+\.?[0-9]*)', value)
                if match:
                    rating = float(match.group(1))
                    # Normalize to 0-1 scale
                    if rating > 1.0:
                        rating = rating / 5.0 if rating <= 5.0 else rating / 100.0
                    return rating
            return float(value)
        except (ValueError, TypeError):
            return None

    def _parse_int(self, value: Any) -> int | None:
        if value is None:
            return None
        
        try:
            if isinstance(value, str):
                value = re.sub(r'[^\d]', '', value)
            return int(value) if value else None
        except (ValueError, TypeError):
            return None

    def _parse_bool(self, value: Any) -> bool | None:
        if value is None:
            return None
        
        if isinstance(value, bool):
            return value
        
        if isinstance(value, str):
            return value.lower() in ("true", "yes", "1", "available", "in_stock")
        
        return bool(value)

    def _normalize_delivery_eta(self, value: Any) -> str | None:
        if not value:
            return None
        
        eta_str = str(value).strip()
        if not eta_str or eta_str.lower() == "unknown":
            return None
        
        return eta_str

    def _normalize_warranty(self, value: Any) -> str | None:
        if not value:
            return None
        
        warranty_str = str(value).strip()
        if not warranty_str or warranty_str.lower() in ("none", "n/a", "0"):
            return None
        
        return warranty_str

    def _clean_html(self, text: str) -> str:
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()