import pytest


@pytest.mark.asyncio
async def test_referral_workflow_tracks_cashback_and_blacklist(db, product_factory, user_factory):
    referrer_id = await user_factory(7200)
    referred_id = await user_factory(7201, balance=10_000)

    await db.create_referral(referrer_id, referred_id)

    product_id = await product_factory(price_cents=5_000)
    await db.purchase_product(
        user_discord_id=referred_id,
        product_id=product_id,
        price_paid_cents=5_000,
        discount_applied_percent=0.0,
    )

    pending = await db.get_pending_cashback_for_user(referrer_id)
    assert pending["pending_cents"] == 25  # 0.5% of 5,000
    assert pending["referral_count"] == 1

    await db.mark_cashback_paid(referrer_id, pending["pending_cents"])
    stats = await db.get_referral_stats(referrer_id)
    assert stats["total_paid_cents"] == 25

    await db.blacklist_referral_user(referrer_id)
    all_pending = await db.get_all_pending_referral_cashbacks()
    assert all_pending == []
