import pytest

from apex_core.utils.purchase import process_post_purchase


@pytest.mark.asyncio
async def test_purchase_workflow_creates_order_and_updates_vip(db, product_factory, user_factory, sample_config):
    user_id = await user_factory(7000, balance=30_000)

    await db._connection.execute(
        "UPDATE users SET total_lifetime_spent_cents = ? WHERE discord_id = ?",
        (5000, user_id),
    )
    await db._connection.commit()

    product_id = await product_factory(price_cents=20_000)

    old_tier, new_tier = await process_post_purchase(
        user_discord_id=user_id,
        amount_cents=20_000,
        db=db,
        config=sample_config,
    )

    assert old_tier is not None and old_tier.name == "Apex VIP"
    assert new_tier is not None and new_tier.name == "Apex Elite"

    order_id, remaining_balance = await db.purchase_product(
        user_discord_id=user_id,
        product_id=product_id,
        price_paid_cents=20_000,
        discount_applied_percent=0.0,
        order_metadata="{\"source\": \"integration\"}",
    )

    assert remaining_balance == 10_000

    orders = await db.get_orders_for_user(user_id)
    assert any(order["id"] == order_id for order in orders)

    transactions = await db.get_wallet_transactions(user_id)
    assert any(txn["transaction_type"] == "purchase" and txn["order_id"] == order_id for txn in transactions)
