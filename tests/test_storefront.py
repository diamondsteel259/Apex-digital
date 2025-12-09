import pytest
from unittest.mock import Mock, patch
import discord

from cogs.storefront import _build_payment_embed, _validate_payment_method, _safe_get_metadata
from apex_core.config import PaymentMethod


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


class TestPaymentMethodValidation:
    """Test payment method validation and embed building robustness."""

    def test_validate_payment_method_valid(self):
        """Test validation of a valid payment method."""
        method = PaymentMethod(
            name="Test Wallet",
            instructions="Pay using your wallet balance",
            emoji="💳",
            metadata={"type": "internal", "is_enabled": True}
        )
        
        is_valid, reason = _validate_payment_method(method)
        assert is_valid is True
        assert reason == ""

    def test_validate_payment_method_none(self):
        """Test validation of None payment method."""
        is_valid, reason = _validate_payment_method(None)
        assert is_valid is False
        assert "Payment method is None" in reason

    def test_validate_payment_method_missing_attributes(self):
        """Test validation of payment method with missing attributes."""
        # Missing name
        method = Mock()
        del method.name
        is_valid, reason = _validate_payment_method(method)
        assert is_valid is False
        assert "missing 'name' attribute" in reason

    def test_validate_payment_method_invalid_name(self):
        """Test validation of payment method with invalid name."""
        method = PaymentMethod(
            name="",  # Empty name
            instructions="Pay using your wallet balance",
            metadata={}
        )
        
        is_valid, reason = _validate_payment_method(method)
        assert is_valid is False
        assert "name is invalid" in reason

    def test_validate_payment_method_invalid_instructions(self):
        """Test validation of payment method with None instructions."""
        method = PaymentMethod(
            name="Test Method",
            instructions=None,  # None instructions
            metadata={}
        )
        
        is_valid, reason = _validate_payment_method(method)
        assert is_valid is False
        assert "has invalid instructions" in reason

    def test_validate_payment_method_invalid_instructions_empty(self):
        """Test validation of payment method with empty instructions."""
        method = PaymentMethod(
            name="Test Method",
            instructions="",  # Empty instructions
            metadata={}
        )
        
        is_valid, reason = _validate_payment_method(method)
        assert is_valid is False
        assert "has invalid instructions" in reason

    def test_validate_payment_method_none_metadata(self):
        """Test validation of payment method with None metadata."""
        method = PaymentMethod(
            name="Test Method",
            instructions="Pay using test method",
            metadata=None  # None metadata
        )
        
        is_valid, reason = _validate_payment_method(method)
        assert is_valid is False
        assert "has None metadata" in reason

    def test_validate_payment_method_non_dict_metadata(self):
        """Test validation of payment method with non-dict metadata."""
        method = PaymentMethod(
            name="Test Method",
            instructions="Pay using test method",
            metadata="not a dict"  # Non-dict metadata
        )
        
        is_valid, reason = _validate_payment_method(method)
        assert is_valid is False
        assert "metadata is not a dict" in reason

    def test_safe_get_metadata_with_valid_dict(self):
        """Test safe metadata access with valid dict."""
        metadata = {"pay_id": "123", "url": "https://example.com"}
        
        assert _safe_get_metadata(metadata, "pay_id") == "123"
        assert _safe_get_metadata(metadata, "missing_key", "default") == "default"
        assert _safe_get_metadata(metadata, "missing_key") is None

    def test_safe_get_metadata_with_none(self):
        """Test safe metadata access with None."""
        assert _safe_get_metadata(None, "key") is None
        assert _safe_get_metadata(None, "key", "default") == "default"

    def test_safe_get_metadata_with_non_dict(self):
        """Test safe metadata access with non-dict."""
        assert _safe_get_metadata("not a dict", "key") is None
        assert _safe_get_metadata("not a dict", "key", "default") == "default"

    def test_safe_get_metadata_with_non_list_networks(self):
        """Test safe metadata access with networks that aren't lists."""
        metadata = {"networks": "not a list"}
        networks = _safe_get_metadata(metadata, "networks")
        assert networks == "not a list"

    @pytest.mark.asyncio
    async def test_build_payment_embed_with_valid_methods(self):
        """Test payment embed building with valid payment methods."""
        product = {
            "variant_name": "Test Product",
            "service_name": "Test Service", 
            "start_time": "1 hour"
        }
        
        user = Mock()
        user.display_avatar.url = "https://example.com/avatar.png"
        user.balance_cents = 1000
        
        payment_methods = [
            PaymentMethod(
                name="Wallet",
                instructions="Use your wallet balance",
                emoji="💳",
                metadata={"type": "internal"}
            ),
            PaymentMethod(
                name="Binance",
                instructions="Pay via Binance",
                emoji="🟡",
                metadata={"pay_id": "12345", "url": "https://binance.com"}
            )
        ]
        
        embed = _build_payment_embed(
            product=product,
            user=user,
            final_price_cents=500,
            user_balance_cents=1000,
            payment_methods=payment_methods
        )
        
        assert embed.title == "💳 Payment Options for Test Product"
        assert "Available Payment Methods" in embed.fields[0].value
        assert "💳 **Wallet**" in embed.fields[0].value
        assert "🟡 **Binance**" in embed.fields[0].value

    @pytest.mark.asyncio 
    async def test_build_payment_embed_skips_invalid_methods(self):
        """Test payment embed building skips invalid payment methods with logging."""
        product = {
            "variant_name": "Test Product",
            "service_name": "Test Service",
            "start_time": "1 hour"
        }
        
        user = Mock()
        user.display_avatar.url = "https://example.com/avatar.png"
        
        # Mix of valid and invalid payment methods
        payment_methods = [
            PaymentMethod(
                name="Valid Method",
                instructions="Valid instructions",
                emoji="✅",
                metadata={"is_enabled": True}
            ),
            PaymentMethod(
                name="Invalid Method",
                instructions=None,  # Invalid - None instructions
                emoji="❌",
                metadata={}
            ),
            PaymentMethod(
                name=None,  # Invalid - None name
                instructions="Some instructions", 
                emoji="❌",
                metadata={}
            ),
            PaymentMethod(
                name="Another Valid",
                instructions="More valid instructions",
                emoji="✅", 
                metadata={"type": "test"}
            )
        ]
        
        with patch('cogs.storefront.logger') as mock_logger:
            embed = _build_payment_embed(
                product=product,
                user=user,
                final_price_cents=500,
                user_balance_cents=1000,
                payment_methods=payment_methods
            )
            
            # Check that invalid methods were logged
            assert mock_logger.warning.called
            warning_calls = [call.args[0] for call in mock_logger.warning.call_args_list]
            
            # Should have warnings for the invalid methods
            assert any("has invalid instructions" in call for call in warning_calls)
            assert any("name is invalid" in call for call in warning_calls)
            
            # Valid methods should still appear in embed
            embed_text = embed.fields[0].value
            assert "✅ **Valid Method**" in embed_text
            assert "✅ **Another Valid**" in embed_text
            # Invalid methods should not appear
            assert "Invalid Method" not in embed_text

    @pytest.mark.asyncio
    async def test_build_payment_embed_with_none_metadata(self):
        """Test payment embed building handles None metadata gracefully."""
        product = {
            "variant_name": "Test Product", 
            "service_name": "Test Service",
            "start_time": "1 hour"
        }
        
        user = Mock()
        user.display_avatar.url = "https://example.com/avatar.png"
        
        payment_methods = [
            PaymentMethod(
                name="Method with None metadata",
                instructions="Valid instructions",
                emoji="❓",
                metadata=None  # None metadata - should be skipped with warning
            )
        ]
        
        with patch('cogs.storefront.logger') as mock_logger:
            embed = _build_payment_embed(
                product=product,
                user=user, 
                final_price_cents=500,
                user_balance_cents=1000,
                payment_methods=payment_methods
            )
            
            # Check that method with None metadata was skipped
            assert mock_logger.warning.called
            warning_call = mock_logger.warning.call_args
            assert "has None metadata" in warning_call.args[0]
            
            # Check that no payment methods field is added when all are invalid
            assert len(embed.fields) == 1  # Only the "Important Information" field

    @pytest.mark.asyncio
    async def test_build_payment_embed_with_disabled_methods(self):
        """Test payment embed building respects disabled payment methods."""
        product = {
            "variant_name": "Test Product",
            "service_name": "Test Service", 
            "start_time": "1 hour"
        }
        
        user = Mock()
        user.display_avatar.url = "https://example.com/avatar.png"
        
        payment_methods = [
            PaymentMethod(
                name="Enabled Method",
                instructions="Enabled instructions",
                emoji="✅",
                metadata={"is_enabled": True}
            ),
            PaymentMethod(
                name="Disabled Method", 
                instructions="Disabled instructions",
                emoji="❌",
                metadata={"is_enabled": False}
            ),
            PaymentMethod(
                name="No Enable Flag",
                instructions="No flag instructions",
                emoji="❓",
                metadata={"other": "data"}  # No is_enabled - should be enabled by default
            )
        ]
        
        embed = _build_payment_embed(
            product=product,
            user=user,
            final_price_cents=500,
            user_balance_cents=1000,
            payment_methods=payment_methods
        )
        
        embed_text = embed.fields[0].value
        # Both methods without explicit is_enabled=False should appear
        assert "✅ **Enabled Method**" in embed_text
        assert "❓ **No Enable Flag**" in embed_text
        # Method with is_enabled=False should not appear
        assert "Disabled Method" not in embed_text

    @pytest.mark.asyncio
    async def test_build_payment_embed_with_missing_metadata_keys(self):
        """Test payment embed building handles missing metadata keys gracefully."""
        product = {
            "variant_name": "Test Product",
            "service_name": "Test Service",
            "start_time": "1 hour"
        }
        
        user = Mock()
        user.display_avatar.url = "https://example.com/avatar.png"
        
        payment_methods = [
            PaymentMethod(
                name="Binance",
                instructions="Pay via Binance",
                emoji="🟡",
                metadata={"pay_id": "12345"}  # Missing url, warning
            ),
            PaymentMethod(
                name="Tip.cc", 
                instructions="Pay via Tip.cc",
                emoji="💰",
                metadata={"command": "tip {amount}"}  # Missing url, warning
            ),
            PaymentMethod(
                name="PayPal",
                instructions="Pay via PayPal", 
                emoji="💙",
                metadata={"payment_link": "https://paypal.com"}  # Missing payout_email
            )
        ]
        
        embed = _build_payment_embed(
            product=product,
            user=user,
            final_price_cents=500,
            user_balance_cents=1000,
            payment_methods=payment_methods
        )
        
        embed_text = embed.fields[0].value
        
        # Should only show available metadata fields
        assert "🟡 **Binance**" in embed_text
        assert "• **Pay ID:** `12345`" in embed_text
        # PayPal should appear but without specific metadata since it doesn't match handler
        assert "💙 **PayPal**" in embed_text
        assert "Pay via PayPal" in embed_text
        # Missing specific metadata fields should not cause errors
        assert "• **Email:**" not in embed_text  # No payout_email shown

    @pytest.mark.asyncio
    async def test_build_payment_embed_with_empty_payment_methods(self):
        """Test payment embed building handles empty payment methods list."""
        product = {
            "variant_name": "Test Product",
            "service_name": "Test Service",
            "start_time": "1 hour"
        }
        
        user = Mock()
        user.display_avatar.url = "https://example.com/avatar.png"
        
        # Empty list should not cause errors
        embed = _build_payment_embed(
            product=product,
            user=user,
            final_price_cents=500,
            user_balance_cents=1000,
            payment_methods=[]
        )
        
        # Should only have the important information field
        assert len(embed.fields) == 1
        assert "Important Information" in embed.fields[0].name
        assert "Available Payment Methods" not in str(embed.fields)
