import pytest


@pytest.mark.asyncio
async def test_get_distinct_main_categories_returns_sorted_unique(db, product_factory):
    await product_factory(main_category="Instagram", sub_category="Followers")
    await product_factory(main_category="YouTube", sub_category="Subscribers")
    await product_factory(main_category="Instagram", sub_category="Likes")

    categories = await db.get_distinct_main_categories()
    assert categories == sorted(categories)
    assert set(categories) >= {"Instagram", "YouTube"}


@pytest.mark.asyncio
async def test_get_products_by_category_filters_inactive_entries(db, product_factory):
    active_id = await product_factory(main_category="Twitter", sub_category="Followers", variant_name="Active")
    inactive_id = await product_factory(main_category="Twitter", sub_category="Followers", variant_name="Legacy")

    await db._connection.execute(
        "UPDATE products SET is_active = 0 WHERE id = ?",
        (inactive_id,),
    )
    await db._connection.commit()

    products = await db.get_products_by_category("Twitter", "Followers")
    names = [p["variant_name"] for p in products]
    assert "Active" in names
    assert "Legacy" not in names


@pytest.mark.asyncio
async def test_bulk_upsert_products_tracks_counts(db):
    products_to_add = [
        {
            "main_category": "Store",
            "sub_category": "Default",
            "service_name": "Alpha",
            "variant_name": "Starter",
            "price_cents": 1_000,
            "start_time": None,
            "duration": None,
            "refill_period": None,
            "additional_info": None,
            "role_id": None,
            "content_payload": None,
        }
    ]

    added, updated, deactivated = await db.bulk_upsert_products(
        products_to_add=products_to_add,
        products_to_update=[],
        product_ids_to_keep_active=[],
    )

    assert added == 1
    assert updated == 0
    assert deactivated >= 0
