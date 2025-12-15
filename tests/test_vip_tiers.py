import pytest

from apex_core.utils.purchase import process_post_purchase
from apex_core.utils.vip import calculate_vip_tier


def test_calculate_vip_tier_returns_highest_role(sample_config):
    tier = calculate_vip_tier(25_000, sample_config)
    assert tier is not None
    assert tier.name == "Apex Elite"

    no_tier = calculate_vip_tier(100, sample_config)
    assert no_tier is not None
    assert no_tier.name == "Client"


@pytest.mark.asyncio
async def test_process_post_purchase_detects_promotion(db, sample_config, user_factory):
    user_id = await user_factory(4200)
    
    # Set initial lifetime spend to 5,000 to qualify for Apex VIP
    await db._connection.execute(
        "UPDATE users SET total_lifetime_spent_cents = ? WHERE discord_id = ?",
        (5_000, user_id),
    )
    await db._connection.commit()
    
    await db.update_wallet_balance(user_id, 5_000)

    old_tier, new_tier = await process_post_purchase(
        user_discord_id=user_id,
        amount_cents=20_000,
        db=db,
        config=sample_config,
    )

    assert old_tier is not None and old_tier.name == "Apex VIP"
    assert new_tier is not None and new_tier.name == "Apex Elite"
    assert new_tier.tier_priority < old_tier.tier_priority


@pytest.mark.asyncio
async def test_manual_role_assignment_helpers(db, user_factory):
    user_id = await user_factory(4201)

    await db.add_manually_assigned_role(user_id, "Legendary Donor")
    roles = await db.get_manually_assigned_roles(user_id)
    assert roles == ["Legendary Donor"]

    await db.remove_manually_assigned_role(user_id, "Legendary Donor")
    roles_after = await db.get_manually_assigned_roles(user_id)
    assert roles_after == []
