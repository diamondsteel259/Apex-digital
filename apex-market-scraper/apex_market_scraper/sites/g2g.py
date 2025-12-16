from __future__ import annotations

import json
import re
from typing import Any, Mapping
from urllib.parse import urljoin

from apex_market_scraper.core.models import HttpResponse, ProductRecord, RequestSpec
from apex_market_scraper.sites.base import BaseSiteScraper
from apex_market_scraper.sites.registry import register


@register("g2g")
class G2GScraper(BaseSiteScraper):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.base_url = str(self.site.params.get("base_url", "https://www.g2g.com"))
        self.category = str(self.site.params.get("category", ""))
        self.max_pages = int(self.site.params.get("max_pages", 5))
        self.default_currency = str(self.site.params.get("default_currency", "USD"))
        self.currency_overrides = dict(self.site.params.get("currency_overrides", {}))

    def build_requests(self) -> list[RequestSpec]:
        requests = []
        
        if self.category:
            category_path = self.category
        else:
            category_path = "offers"
        
        for page in range(1, self.max_pages + 1):
            url = urljoin(self.base_url, f"{category_path}?page={page}")
            requests.append(
                RequestSpec(
                    url=url,
                    headers={
                        "Accept": "application/json, text/html",
                        "Accept-Language": "en-US,en;q=0.9",
                    },
                )
            )
        
        return requests

    def parse_listing(self, response: HttpResponse, request: RequestSpec) -> list[Mapping[str, Any]]:
        if response.is_dry_run:
            return self._generate_dry_run_data(request)
        
        try:
            data = json.loads(response.text)
            if isinstance(data, dict) and "listings" in data:
                return self._parse_json_listings(data)
        except (json.JSONDecodeError, ValueError):
            pass
        
        return self._parse_html_listings(response.text, request.url)

    def normalize_record(self, raw: Mapping[str, Any]) -> ProductRecord:
        price = self._normalize_price(raw.get("price"), raw.get("currency"))
        
        min_qty = raw.get("minQty")
        max_qty = raw.get("maxQty")
        
        seller_rating = self._parse_rating(raw.get("sellerRating"))
        sold_count = self._parse_int(raw.get("soldCount"))
        stock = self._parse_int(raw.get("stock"))
        
        delivery_eta = self._normalize_delivery_eta(raw.get("deliveryEta"))
        warranty = self._normalize_warranty(raw.get("warranty"))
        refill_available = self._parse_bool(raw.get("refillAvailable"))
        
        return ProductRecord(
            site_name=self.site.name,
            site_kind=self.site.kind,
            product_name=str(raw.get("title") or ""),
            category=str(raw.get("category")) if raw.get("category") else None,
            price=price,
            currency=self._get_currency(raw.get("currency")),
            description=str(raw.get("description")) if raw.get("description") else None,
            min_quantity=float(min_qty) if min_qty is not None else None,
            max_quantity=float(max_qty) if max_qty is not None else None,
            seller_rating=seller_rating,
            sold_amount=sold_count,
            stock=stock,
            delivery_eta=delivery_eta,
            refill_available=refill_available,
            warranty=warranty,
            product_url=str(raw.get("url") or ""),
            hidden_link_metadata=dict(raw.get("metadata") or {}),
        )

    def _generate_dry_run_data(self, request: RequestSpec) -> list[Mapping[str, Any]]:
        return [
            {
                "title": "G2G Gaming Currency - 1000 Gold",
                "category": self.category or "gaming",
                "price": 9.99,
                "currency": "USD",
                "minQty": 1,
                "maxQty": 100,
                "sellerRating": "4.8",
                "soldCount": 523,
                "stock": 50,
                "deliveryEta": "5-10 minutes",
                "warranty": "30 days",
                "refillAvailable": True,
                "description": "Fast delivery, 24/7 support",
                "url": f"{request.url}#listing-1",
                "metadata": {"listingId": "dry-run-1"},
            }
        ]

    def _parse_json_listings(self, data: dict[str, Any]) -> list[Mapping[str, Any]]:
        listings: list[Mapping[str, Any]] = []
        items = data.get("listings", [])
        
        for item in items:
            if not isinstance(item, dict):
                continue
            
            if not self._has_critical_fields(item):
                self.logger.warning("Skipping listing missing critical fields: %s", item.get("id"))
                continue
            
            listings.append(self._extract_listing_data(item))
        
        return listings

    def _parse_html_listings(self, html: str, base_url: str) -> list[Mapping[str, Any]]:
        listings: list[Mapping[str, Any]] = []
        
        listing_pattern = r'<div[^>]*class="[^"]*listing-item[^"]*"[^>]*>(.*?)</div>\s*</div>'
        matches = re.finditer(listing_pattern, html, re.DOTALL | re.IGNORECASE)
        
        for match in matches:
            listing_html = match.group(1)
            listing_data = self._extract_from_html(listing_html, base_url)
            
            if listing_data and self._has_critical_fields(listing_data):
                listings.append(listing_data)
            elif listing_data:
                self.logger.warning("Skipping listing missing critical fields")
        
        return listings

    def _extract_listing_data(self, item: dict[str, Any]) -> dict[str, Any]:
        stock = item.get("stock")
        if stock is None:
            stock = item.get("stockQuantity")
        
        sold_count = item.get("soldCount")
        if sold_count is None:
            sold_count = item.get("sold_count")
        
        min_qty = item.get("minQuantity")
        if min_qty is None:
            min_qty = item.get("min_qty")
        
        max_qty = item.get("maxQuantity")
        if max_qty is None:
            max_qty = item.get("max_qty")
        
        delivery_eta = item.get("deliveryTime")
        if delivery_eta is None:
            delivery_eta = item.get("delivery_eta")
        
        refill = item.get("refillAvailable")
        if refill is None:
            refill = item.get("refill")
        
        return {
            "title": item.get("title") or item.get("name") or "",
            "category": item.get("category"),
            "price": item.get("price"),
            "currency": item.get("currency") or self.default_currency,
            "minQty": min_qty,
            "maxQty": max_qty,
            "sellerRating": item.get("seller", {}).get("rating") if isinstance(item.get("seller"), dict) else item.get("sellerRating"),
            "soldCount": sold_count,
            "stock": stock,
            "deliveryEta": delivery_eta,
            "warranty": item.get("warranty"),
            "refillAvailable": refill,
            "description": item.get("description"),
            "url": item.get("url") or item.get("link") or "",
            "metadata": {
                "listingId": item.get("id") or item.get("listingId"),
                "sellerId": item.get("seller", {}).get("id") if isinstance(item.get("seller"), dict) else item.get("sellerId"),
                "preorder": item.get("preorder", False),
            },
        }

    def _extract_from_html(self, html: str, base_url: str) -> dict[str, Any] | None:
        try:
            title_match = re.search(r'<h[23][^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</h[23]>', html, re.DOTALL | re.IGNORECASE)
            title = self._clean_html(title_match.group(1)) if title_match else ""
            
            price_match = re.search(r'data-price="([^"]+)"', html)
            if not price_match:
                price_match = re.search(r'<span[^>]*class="[^"]*price[^"]*"[^>]*>.*?([0-9]+\.?[0-9]*)', html)
            price = float(price_match.group(1)) if price_match else None
            
            currency_match = re.search(r'data-currency="([^"]+)"', html)
            currency = currency_match.group(1) if currency_match else self.default_currency
            
            url_match = re.search(r'href="([^"]+)"', html)
            url = urljoin(base_url, url_match.group(1)) if url_match else base_url
            
            stock_match = re.search(r'data-stock="([^"]+)"', html)
            stock = int(stock_match.group(1)) if stock_match else None
            
            seller_rating_match = re.search(r'data-rating="([^"]+)"', html)
            seller_rating = seller_rating_match.group(1) if seller_rating_match else None
            
            return {
                "title": title,
                "category": None,
                "price": price,
                "currency": currency,
                "minQty": None,
                "maxQty": None,
                "sellerRating": seller_rating,
                "soldCount": None,
                "stock": stock,
                "deliveryEta": None,
                "warranty": None,
                "refillAvailable": None,
                "description": None,
                "url": url,
                "metadata": {},
            }
        except Exception as e:
            self.logger.warning("Failed to extract listing from HTML: %s", e)
            return None

    def _has_critical_fields(self, item: dict[str, Any]) -> bool:
        has_title = bool(item.get("title") or item.get("name"))
        has_price = item.get("price") is not None
        has_url = bool(item.get("url") or item.get("link"))
        
        return has_title and has_price and has_url

    def _normalize_price(self, price: Any, currency: str | None) -> float | None:
        if price is None:
            return None
        
        try:
            price_float = float(price)
            
            actual_currency = self._get_currency(currency)
            if actual_currency != "USD":
                price_float = self._convert_to_usd(price_float, actual_currency)
            
            return round(price_float * 100, 2)
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
        }
        
        rate = conversion_rates.get(from_currency, 1.0)
        return price * rate

    def _parse_rating(self, value: Any) -> float | None:
        if value is None:
            return None
        
        try:
            if isinstance(value, str):
                value = value.replace("/5", "").strip()
                match = re.search(r'([0-9]+\.?[0-9]*)', value)
                if match:
                    return float(match.group(1))
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
            return value.lower() in ("true", "yes", "1", "available")
        
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
