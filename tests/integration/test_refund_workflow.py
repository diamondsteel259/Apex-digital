import pytest


@pytest.mark.asyncio
async def test_refund_workflow_credits_wallet_and_logs_audit(db, product_factory, user_factory):
    user_id = await user_factory(7100, balance=5_000)
    product_id = await product_factory(price_cents=2_000)

    order_id, _ = await db.purchase_product(
        user_discord_id=user_id,
        product_id=product_id,
        price_paid_cents=2_000,
        discount_applied_percent=0.0,
    )

    await db.update_order_status(order_id, "fulfilled")

    refund_id = await db.create_refund_request(
        order_id=order_id,
        user_discord_id=user_id,
        amount_cents=2_000,
        reason="Service unavailable",
        proof_attachment_url="https://cdn.example/proof.png",
    )

    staff_id = await user_factory(9_001)
    await db.approve_refund(refund_id, staff_discord_id=staff_id)

    refund = await db.get_refund_by_id(refund_id)
    assert refund["status"] == "approved"
    assert refund["final_refund_cents"] == 1_800  # 10% fee

    user = await db.get_user(user_id)
    assert user["wallet_balance_cents"] == 4_800

    transactions = await db.get_wallet_transactions(user_id)
    assert any(
        txn["transaction_type"] == "refund" and txn["order_id"] == order_id for txn in transactions
    )
