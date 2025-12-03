"""Tests for referral cashback batching functionality."""

import pytest

from apex_core.database import Database


@pytest.mark.asyncio
async def test_get_all_pending_referral_cashbacks(tmp_path):
    """Test getting all pending referral cashbacks."""
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    await db.connect()

    try:
        # Create test users
        referrer_1 = 100
        referrer_2 = 200
        referred_1 = 101
        referred_2 = 201

        await db.ensure_user(referrer_1)
        await db.ensure_user(referrer_2)
        await db.ensure_user(referred_1)
        await db.ensure_user(referred_2)

        # Create referrals
        await db.create_referral(referrer_1, referred_1)
        await db.create_referral(referrer_2, referred_2)

        # Log purchases
        await db.log_referral_purchase(referred_1, 1, 10000)  # $100 -> $0.50
        await db.log_referral_purchase(referred_2, 2, 20000)  # $200 -> $1.00

        # Get all pending cashbacks
        pending = await db.get_all_pending_referral_cashbacks()

        assert len(pending) == 2
        assert any(
            p["referrer_id"] == referrer_1 and p["pending_cents"] == 50
            for p in pending
        )
        assert any(
            p["referrer_id"] == referrer_2 and p["pending_cents"] == 100
            for p in pending
        )

    finally:
        await db.close()


@pytest.mark.asyncio
async def test_get_pending_cashback_for_user(tmp_path):
    """Test getting pending cashback for specific user."""
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    await db.connect()

    try:
        referrer_id = 100
        referred_1 = 101
        referred_2 = 102

        await db.ensure_user(referrer_id)
        await db.ensure_user(referred_1)
        await db.ensure_user(referred_2)

        await db.create_referral(referrer_id, referred_1)
        await db.create_referral(referrer_id, referred_2)

        await db.log_referral_purchase(referred_1, 1, 10000)  # $0.50
        await db.log_referral_purchase(referred_2, 2, 20000)  # $1.00

        pending = await db.get_pending_cashback_for_user(referrer_id)

        assert pending["pending_cents"] == 150
        assert pending["referral_count"] == 2
        assert not pending["is_blacklisted"]
        assert len(pending["referral_details"]) == 2

    finally:
        await db.close()


@pytest.mark.asyncio
async def test_mark_cashback_paid(tmp_path):
    """Test marking cashback as paid."""
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    await db.connect()

    try:
        referrer_id = 100
        referred_id = 101

        await db.ensure_user(referrer_id)
        await db.ensure_user(referred_id)

        await db.create_referral(referrer_id, referred_id)
        await db.log_referral_purchase(referred_id, 1, 10000)  # $0.50

        # Verify pending before
        pending_before = await db.get_pending_cashback_for_user(referrer_id)
        assert pending_before["pending_cents"] == 50

        # Mark as paid
        await db.mark_cashback_paid(referrer_id, 50)

        # Verify pending after
        pending_after = await db.get_pending_cashback_for_user(referrer_id)
        assert pending_after["pending_cents"] == 0

        # Verify stats
        stats = await db.get_referral_stats(referrer_id)
        assert stats["total_earned_cents"] == 50
        assert stats["total_paid_cents"] == 50
        assert stats["pending_cents"] == 0

    finally:
        await db.close()


@pytest.mark.asyncio
async def test_blacklisted_user_excluded_from_pending(tmp_path):
    """Test that blacklisted users are excluded from pending cashbacks."""
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    await db.connect()

    try:
        referrer_id = 100
        referred_id = 101

        await db.ensure_user(referrer_id)
        await db.ensure_user(referred_id)

        await db.create_referral(referrer_id, referred_id)
        await db.log_referral_purchase(referred_id, 1, 10000)  # $0.50

        # Verify pending before blacklist
        pending_before = await db.get_all_pending_referral_cashbacks()
        assert len(pending_before) == 1
        assert pending_before[0]["referrer_id"] == referrer_id

        # Blacklist user
        await db.blacklist_referral_user(referrer_id)

        # Verify excluded from pending
        pending_after = await db.get_all_pending_referral_cashbacks()
        assert len(pending_after) == 0

    finally:
        await db.close()


@pytest.mark.asyncio
async def test_zero_pending_cashback(tmp_path):
    """Test handling of zero pending cashback."""
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    await db.connect()

    try:
        referrer_id = 100

        await db.ensure_user(referrer_id)

        # Get pending for user with no referrals
        pending = await db.get_pending_cashback_for_user(referrer_id)

        assert pending["pending_cents"] == 0
        assert pending["referral_count"] == 0
        assert not pending["is_blacklisted"]
        assert len(pending["referral_details"]) == 0

        # Get all pending (should be empty)
        all_pending = await db.get_all_pending_referral_cashbacks()
        assert len(all_pending) == 0

    finally:
        await db.close()


@pytest.mark.asyncio
async def test_multiple_purchases_accumulate(tmp_path):
    """Test that multiple purchases accumulate cashback correctly."""
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    await db.connect()

    try:
        referrer_id = 100
        referred_id = 101

        await db.ensure_user(referrer_id)
        await db.ensure_user(referred_id)

        await db.create_referral(referrer_id, referred_id)

        # Multiple purchases
        await db.log_referral_purchase(referred_id, 1, 10000)  # $0.50
        await db.log_referral_purchase(referred_id, 2, 20000)  # $1.00
        await db.log_referral_purchase(referred_id, 3, 15000)  # $0.75

        pending = await db.get_pending_cashback_for_user(referrer_id)

        # Total: $0.50 + $1.00 + $0.75 = $2.25
        assert pending["pending_cents"] == 225
        assert pending["referral_count"] == 1  # Still only 1 referred user

    finally:
        await db.close()


@pytest.mark.asyncio
async def test_partial_payment_tracking(tmp_path):
    """Test that partial payments don't result in double-payment."""
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    await db.connect()

    try:
        referrer_id = 100
        referred_id = 101

        await db.ensure_user(referrer_id)
        await db.ensure_user(referred_id)

        await db.create_referral(referrer_id, referred_id)
        await db.log_referral_purchase(referred_id, 1, 10000)  # $0.50

        # Mark as paid
        await db.mark_cashback_paid(referrer_id, 50)

        # Log another purchase
        await db.log_referral_purchase(referred_id, 2, 10000)  # Another $0.50

        # Should only show new pending
        pending = await db.get_pending_cashback_for_user(referrer_id)
        assert pending["pending_cents"] == 50  # Only new purchase

        # Mark this one paid too
        await db.mark_cashback_paid(referrer_id, 50)

        # Now should be zero
        pending_final = await db.get_pending_cashback_for_user(referrer_id)
        assert pending_final["pending_cents"] == 0

        # Check stats
        stats = await db.get_referral_stats(referrer_id)
        assert stats["total_earned_cents"] == 100  # Total earned
        assert stats["total_paid_cents"] == 100  # Total paid
        assert stats["pending_cents"] == 0

    finally:
        await db.close()


@pytest.mark.asyncio
async def test_create_referral_prevents_self_referral(tmp_path):
    db_path = tmp_path / "self.db"
    db = Database(db_path)
    await db.connect()

    try:
        await db.ensure_user(500)
        with pytest.raises(RuntimeError, match="Users cannot refer themselves"):
            await db.create_referral(500, 500)
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_duplicate_referral_prevention(tmp_path):
    db_path = tmp_path / "duplicate.db"
    db = Database(db_path)
    await db.connect()

    try:
        referrer_a = 600
        referrer_b = 601
        referred_id = 700

        await db.ensure_user(referrer_a)
        await db.ensure_user(referrer_b)
        await db.ensure_user(referred_id)

        await db.create_referral(referrer_a, referred_id)

        with pytest.raises(RuntimeError, match="already been referred"):
            await db.create_referral(referrer_b, referred_id)
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_get_referrer_for_user_returns_assignment(tmp_path):
    db_path = tmp_path / "referrer.db"
    db = Database(db_path)
    await db.connect()

    try:
        referrer_id = 800
        referred_id = 801

        await db.ensure_user(referrer_id)
        await db.ensure_user(referred_id)
        await db.create_referral(referrer_id, referred_id)

        result = await db.get_referrer_for_user(referred_id)
        assert result == referrer_id
    finally:
        await db.close()
