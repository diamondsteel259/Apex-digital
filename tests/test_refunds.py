import pytest


@pytest.mark.asyncio
async def test_create_refund_request_calculates_handling_fee(db, product_factory, user_factory):
    user_id = await user_factory(4100)
    product_id = await product_factory(price_cents=5_000)

    order_id = await db.create_order(
        user_discord_id=user_id,
        product_id=product_id,
        price_paid_cents=5_000,
        discount_applied_percent=0.0,
        status="fulfilled",
    )

    refund_id = await db.create_refund_request(
        order_id=order_id,
        user_discord_id=user_id,
        amount_cents=5_000,
        reason="Product defective",
        proof_attachment_url="https://cdn.example/proof.png",
        handling_fee_percent=12.5,
    )

    refund = await db.get_refund_by_id(refund_id)
    assert refund is not None
    assert refund["handling_fee_cents"] == 625
    assert refund["final_refund_cents"] == 4_375
    assert refund["status"] == "pending"


@pytest.mark.asyncio
async def test_validate_order_for_refund_enforces_time_window(db, product_factory, user_factory):
    user_id = await user_factory(4101)
    product_id = await product_factory()

    order_id = await db.create_order(
        user_discord_id=user_id,
        product_id=product_id,
        price_paid_cents=1_000,
        discount_applied_percent=0.0,
        status="fulfilled",
    )

    await db._connection.execute(
        "UPDATE orders SET created_at = datetime('now', '-10 days') WHERE id = ?",
        (order_id,),
    )
    await db._connection.commit()

    result = await db.validate_order_for_refund(order_id, user_id, max_days=3)
    assert result is None, "Orders outside the refund window must be rejected"

    await db._connection.execute(
        "UPDATE orders SET created_at = datetime('now', '-1 day') WHERE id = ?",
        (order_id,),
    )
    await db._connection.commit()

    result = await db.validate_order_for_refund(order_id, user_id, max_days=3)
    assert result is not None
    assert result["service_name"]


@pytest.mark.asyncio
async def test_approve_refund_updates_wallet_and_logs_transaction(db, product_factory, user_factory):
    user_id = await user_factory(4102)
    product_id = await product_factory(price_cents=3_000)

    order_id = await db.create_order(
        user_discord_id=user_id,
        product_id=product_id,
        price_paid_cents=3_000,
        discount_applied_percent=0.0,
        status="fulfilled",
    )

    refund_id = await db.create_refund_request(
        order_id=order_id,
        user_discord_id=user_id,
        amount_cents=3_000,
        reason="Service not delivered",
        handling_fee_percent=10.0,
    )

    staff_id = await user_factory(999_999)
    await db.approve_refund(refund_id, staff_discord_id=staff_id)

    user = await db.get_user(user_id)
    assert user["wallet_balance_cents"] == 2_700  # 10% handling fee

    transactions = await db.get_wallet_transactions(user_id)
    assert any(t["transaction_type"] == "refund" and t["amount_cents"] == 2_700 for t in transactions)

    refund = await db.get_refund_by_id(refund_id)
    assert refund["status"] == "approved"
    assert refund["resolved_by_staff_id"] == staff_id


@pytest.mark.asyncio
async def test_reject_refund_records_reason(db, product_factory, user_factory):
    user_id = await user_factory(4103)
    product_id = await product_factory()

    order_id = await db.create_order(
        user_discord_id=user_id,
        product_id=product_id,
        price_paid_cents=1_500,
        discount_applied_percent=0.0,
        status="fulfilled",
    )

    refund_id = await db.create_refund_request(
        order_id=order_id,
        user_discord_id=user_id,
        amount_cents=1_500,
        reason="Changed my mind",
    )

    staff_id = await user_factory(1_234)
    await db.reject_refund(refund_id, staff_discord_id=staff_id, rejection_reason="Policy violation")

    refund = await db.get_refund_by_id(refund_id)
    assert refund["status"] == "rejected"
    assert refund["rejection_reason"] == "Policy violation"
    assert refund["resolved_by_staff_id"] == staff_id


@pytest.mark.asyncio
async def test_get_pending_refunds_returns_only_open_items(db, product_factory, user_factory):
    user_id = await user_factory(4104)
    product_id = await product_factory()

    order_id = await db.create_order(
        user_discord_id=user_id,
        product_id=product_id,
        price_paid_cents=2_000,
        discount_applied_percent=0.0,
        status="fulfilled",
    )

    refund_id = await db.create_refund_request(
        order_id=order_id,
        user_discord_id=user_id,
        amount_cents=2_000,
        reason="Delayed",
    )

    pending = await db.get_pending_refunds()
    assert any(r["id"] == refund_id for r in pending)

    staff_id = await user_factory(1)
    await db.reject_refund(refund_id, staff_discord_id=staff_id, rejection_reason="Resolved")

    pending_after = await db.get_pending_refunds()
    assert all(r["id"] != refund_id for r in pending_after)
