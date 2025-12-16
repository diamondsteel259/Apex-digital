from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True, frozen=True)
class ProductRecord:
    site_name: str
    site_kind: str

    product_name: str
    category: str | None
    price: float | None
    currency: str | None
    description: str | None

    min_quantity: float | None
    max_quantity: float | None

    seller_rating: float | None
    sold_amount: int | None
    stock: int | None

    delivery_eta: str | None
    refill_available: bool | None
    warranty: str | None

    product_url: str
    hidden_link_metadata: dict[str, Any] = field(default_factory=dict)

    scraped_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    source_updated_at: datetime | None = None

    def dedupe_key(self) -> str:
        return self.product_url

    def to_dict(self) -> dict[str, Any]:
        return {
            "site": self.site_name,
            "site_kind": self.site_kind,
            "name": self.product_name,
            "category": self.category,
            "price": self.price,
            "currency": self.currency,
            "description": self.description,
            "min_quantity": self.min_quantity,
            "max_quantity": self.max_quantity,
            "seller_rating": self.seller_rating,
            "sold_amount": self.sold_amount,
            "stock": self.stock,
            "delivery_eta": self.delivery_eta,
            "refill_available": self.refill_available,
            "warranty": self.warranty,
            "url": self.product_url,
            "hidden_link_metadata": self.hidden_link_metadata,
            "scraped_at": self.scraped_at.isoformat(),
            "source_updated_at": self.source_updated_at.isoformat() if self.source_updated_at else None,
        }


@dataclass(slots=True)
class SiteMetadata:
    site_name: str
    site_kind: str
    task_id: str

    started_at: datetime
    finished_at: datetime | None = None

    dry_run: bool = False

    requests_built: int = 0
    requests_executed: int = 0

    raw_records_parsed: int = 0
    records_normalized: int = 0

    errors: list[str] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class RequestSpec:
    url: str
    method: str = "GET"
    headers: dict[str, str] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)
    data: Any | None = None
    json: Any | None = None
    timeout_seconds: float | None = 30.0
    allow_redirects: bool = True


@dataclass(slots=True, frozen=True)
class HttpResponse:
    url: str
    status_code: int
    headers: dict[str, str]
    text: str
    content: bytes
    is_dry_run: bool = False


@dataclass(slots=True, frozen=True)
class ScrapeMetrics:
    sites_attempted: int
    sites_succeeded: int
    records_total: int
    records_deduped: int


@dataclass(slots=True, frozen=True)
class ScrapeEvent:
    ts: datetime
    event: str
    message: str
    site_name: str | None = None
    task_id: str | None = None
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ScrapeResult:
    records: list[ProductRecord]
    site_metadata: dict[str, SiteMetadata]
    metrics: ScrapeMetrics
    events: list[ScrapeEvent] = field(default_factory=list)
