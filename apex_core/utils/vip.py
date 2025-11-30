"""VIP tier calculation utilities."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..config import Config, VipTier


def calculate_vip_tier(total_spent_cents: int, config: Config) -> VipTier | None:
    """
    Calculate VIP tier based on lifetime spending.
    
    Args:
        total_spent_cents: Total amount spent in cents
        config: Bot configuration with VIP thresholds
    
    Returns:
        VipTier object or None if user doesn't qualify for any tier
    """
    qualified_tier: VipTier | None = None
    
    for tier in sorted(config.vip_thresholds, key=lambda t: t.min_spend_cents, reverse=True):
        if total_spent_cents >= tier.min_spend_cents:
            qualified_tier = tier
            break
    
    return qualified_tier
