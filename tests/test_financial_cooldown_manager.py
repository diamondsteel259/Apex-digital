"""Tests for financial cooldown manager with fail-fast config validation."""

import logging
from unittest.mock import MagicMock, patch

import pytest

from apex_core.financial_cooldown_manager import (
    DEFAULT_COOLDOWN_CONFIGS,
    CooldownConfigurationError,
    CooldownTier,
    FinancialCooldownConfig,
    FinancialCooldownManager,
    financial_cooldown,
    get_financial_cooldown_manager,
)


class TestDefaultCooldownConfigs:
    """Tests for the module-level DEFAULT_COOLDOWN_CONFIGS constant."""

    def test_default_configs_is_dict(self) -> None:
        """DEFAULT_COOLDOWN_CONFIGS should be a dictionary."""
        assert isinstance(DEFAULT_COOLDOWN_CONFIGS, dict)

    def test_default_configs_contains_known_commands(self) -> None:
        """DEFAULT_COOLDOWN_CONFIGS should contain all expected financial commands."""
        expected_commands = {
            "wallet_payment",
            "submitrefund",
            "manual_complete",
            "setref",
            "refund_approve",
            "refund_reject",
            "balance",
            "orders",
            "invites",
        }
        assert set(DEFAULT_COOLDOWN_CONFIGS.keys()) == expected_commands

    def test_default_configs_values_are_config_objects(self) -> None:
        """Each value in DEFAULT_COOLDOWN_CONFIGS should be a FinancialCooldownConfig."""
        for key, config in DEFAULT_COOLDOWN_CONFIGS.items():
            assert isinstance(config, FinancialCooldownConfig), f"Config for '{key}' is not FinancialCooldownConfig"
            assert isinstance(config.seconds, int), f"Config for '{key}' has non-int seconds"
            assert isinstance(config.tier, CooldownTier), f"Config for '{key}' has non-CooldownTier tier"
            assert isinstance(config.operation_type, str), f"Config for '{key}' has non-str operation_type"

    def test_default_configs_has_valid_cooldown_seconds(self) -> None:
        """All default configs should have positive cooldown seconds."""
        for key, config in DEFAULT_COOLDOWN_CONFIGS.items():
            assert config.seconds > 0, f"Config for '{key}' has non-positive seconds: {config.seconds}"


class TestGetConfigWithDefaults:
    """Tests for _get_config using default configurations."""

    def test_known_command_uses_default(self) -> None:
        """A known command without override should use the default config and log a warning."""
        manager = FinancialCooldownManager()

        with patch("apex_core.financial_cooldown_manager.logger") as mock_logger:
            config = manager._get_config("balance", bot=None)

        assert config.seconds == 10
        assert config.tier == CooldownTier.STANDARD
        assert config.operation_type == "query"
        mock_logger.warning.assert_called_once()
        assert "balance" in str(mock_logger.warning.call_args)
        assert "default" in str(mock_logger.warning.call_args).lower()

    def test_all_known_commands_return_defaults(self) -> None:
        """Each known command should return its default config when no bot/override is provided."""
        manager = FinancialCooldownManager()

        for command_key, expected_config in DEFAULT_COOLDOWN_CONFIGS.items():
            with patch("apex_core.financial_cooldown_manager.logger"):
                config = manager._get_config(command_key, bot=None)

            assert config.seconds == expected_config.seconds
            assert config.tier == expected_config.tier
            assert config.operation_type == expected_config.operation_type


class TestGetConfigWithOverrides:
    """Tests for _get_config with bot.config.financial_cooldowns overrides."""

    def test_override_seconds_honored(self) -> None:
        """Override seconds from bot.config should be used."""
        manager = FinancialCooldownManager()

        mock_bot = MagicMock()
        mock_bot.config.financial_cooldowns = {"balance": 120}

        config = manager._get_config("balance", bot=mock_bot)

        assert config.seconds == 120  # overridden
        assert config.tier == CooldownTier.STANDARD  # from default
        assert config.operation_type == "query"  # from default

    def test_override_preserves_tier_and_operation_type(self) -> None:
        """Override should preserve tier and operation_type from defaults."""
        manager = FinancialCooldownManager()

        mock_bot = MagicMock()
        mock_bot.config.financial_cooldowns = {"wallet_payment": 60}

        config = manager._get_config("wallet_payment", bot=mock_bot)

        assert config.seconds == 60
        assert config.tier == CooldownTier.ULTRA_SENSITIVE
        assert config.operation_type == "payment"

    def test_override_for_unknown_command_uses_standard_tier(self) -> None:
        """Override for unknown command should use STANDARD tier and 'custom' operation_type."""
        manager = FinancialCooldownManager()

        mock_bot = MagicMock()
        mock_bot.config.financial_cooldowns = {"new_custom_command": 45}

        with patch("apex_core.financial_cooldown_manager.logger") as mock_logger:
            config = manager._get_config("new_custom_command", bot=mock_bot)

        assert config.seconds == 45
        assert config.tier == CooldownTier.STANDARD
        assert config.operation_type == "custom"
        mock_logger.warning.assert_called_once()
        assert "new_custom_command" in str(mock_logger.warning.call_args)

    def test_multiple_overrides(self) -> None:
        """Multiple overrides should all be honored."""
        manager = FinancialCooldownManager()

        mock_bot = MagicMock()
        mock_bot.config.financial_cooldowns = {
            "balance": 5,
            "orders": 15,
            "wallet_payment": 100,
        }

        balance_config = manager._get_config("balance", bot=mock_bot)
        orders_config = manager._get_config("orders", bot=mock_bot)
        payment_config = manager._get_config("wallet_payment", bot=mock_bot)

        assert balance_config.seconds == 5
        assert orders_config.seconds == 15
        assert payment_config.seconds == 100


class TestGetConfigMalformedBotConfig:
    """Tests for _get_config handling malformed bot.config scenarios."""

    def test_bot_without_config_attribute(self) -> None:
        """Bot without config attribute should fall back to defaults."""
        manager = FinancialCooldownManager()

        mock_bot = MagicMock(spec=[])  # No config attribute

        with patch("apex_core.financial_cooldown_manager.logger"):
            config = manager._get_config("balance", bot=mock_bot)

        assert config.seconds == DEFAULT_COOLDOWN_CONFIGS["balance"].seconds

    def test_config_without_financial_cooldowns(self) -> None:
        """Config without financial_cooldowns attribute should fall back to defaults."""
        manager = FinancialCooldownManager()

        mock_bot = MagicMock()
        del mock_bot.config.financial_cooldowns

        with patch("apex_core.financial_cooldown_manager.logger"):
            config = manager._get_config("balance", bot=mock_bot)

        assert config.seconds == DEFAULT_COOLDOWN_CONFIGS["balance"].seconds

    def test_financial_cooldowns_not_dict_falls_back(self) -> None:
        """Non-dict financial_cooldowns should fall back to defaults."""
        manager = FinancialCooldownManager()

        mock_bot = MagicMock()
        mock_bot.config.financial_cooldowns = "not a dict"

        with patch("apex_core.financial_cooldown_manager.logger"):
            config = manager._get_config("balance", bot=mock_bot)

        assert config.seconds == DEFAULT_COOLDOWN_CONFIGS["balance"].seconds

    def test_invalid_value_in_financial_cooldowns_logs_warning(self) -> None:
        """Invalid value type should log warning and fall back to defaults."""
        manager = FinancialCooldownManager()

        mock_bot = MagicMock()
        mock_bot.config.financial_cooldowns = {"balance": "not an int"}

        with patch("apex_core.financial_cooldown_manager.logger") as mock_logger:
            config = manager._get_config("balance", bot=mock_bot)

        # Should have logged a warning about failed read
        warning_calls = [str(c) for c in mock_logger.warning.call_args_list]
        assert any("Failed to read" in w for w in warning_calls)
        # Should still return default config
        assert config.seconds == DEFAULT_COOLDOWN_CONFIGS["balance"].seconds


class TestGetConfigUnknownCommand:
    """Tests for _get_config with unknown commands (fail-fast behavior)."""

    def test_unknown_command_raises_error(self) -> None:
        """Unknown command without override should raise CooldownConfigurationError."""
        manager = FinancialCooldownManager()

        with patch("apex_core.financial_cooldown_manager.logger") as mock_logger:
            with pytest.raises(CooldownConfigurationError) as exc_info:
                manager._get_config("unknown_command", bot=None)

        assert exc_info.value.command_key == "unknown_command"
        assert "unknown_command" in str(exc_info.value)
        assert "DEFAULT_COOLDOWN_CONFIGS" in str(exc_info.value)
        mock_logger.warning.assert_called_once()
        assert "No cooldown configuration found" in str(mock_logger.warning.call_args)

    def test_unknown_command_error_lists_known_commands(self) -> None:
        """CooldownConfigurationError should list known commands."""
        manager = FinancialCooldownManager()

        with patch("apex_core.financial_cooldown_manager.logger"):
            with pytest.raises(CooldownConfigurationError) as exc_info:
                manager._get_config("totally_unknown", bot=None)

        error_message = str(exc_info.value)
        # Should list some known commands
        assert "balance" in error_message
        assert "wallet_payment" in error_message

    def test_unknown_command_with_empty_bot_config(self) -> None:
        """Unknown command with bot but empty financial_cooldowns should raise."""
        manager = FinancialCooldownManager()

        mock_bot = MagicMock()
        mock_bot.config.financial_cooldowns = {}

        with patch("apex_core.financial_cooldown_manager.logger"):
            with pytest.raises(CooldownConfigurationError):
                manager._get_config("unknown_command", bot=mock_bot)


class TestCooldownConfigurationError:
    """Tests for CooldownConfigurationError exception class."""

    def test_error_stores_command_key(self) -> None:
        """CooldownConfigurationError should store the command key."""
        error = CooldownConfigurationError("test_command", "Test message")
        assert error.command_key == "test_command"

    def test_error_message_format(self) -> None:
        """CooldownConfigurationError message should include command key and message."""
        error = CooldownConfigurationError("test_command", "Custom error details")
        assert "test_command" in str(error)
        assert "Custom error details" in str(error)

    def test_error_is_runtime_error(self) -> None:
        """CooldownConfigurationError should be a RuntimeError subclass."""
        error = CooldownConfigurationError("cmd", "msg")
        assert isinstance(error, RuntimeError)


class TestFinancialCooldownDecorator:
    """Tests for the financial_cooldown decorator with fail-fast behavior."""

    @pytest.mark.asyncio
    async def test_decorator_raises_on_unknown_command(self) -> None:
        """Decorator should re-raise CooldownConfigurationError for unknown commands."""
        import discord

        class FakeCog:
            def __init__(self) -> None:
                self.bot = None

            @financial_cooldown()
            async def unknown_financial_command(self, interaction: discord.Interaction) -> str:
                return "success"

        cog = FakeCog()
        # Create a mock that passes isinstance(x, discord.Interaction) check
        mock_interaction = MagicMock(spec=discord.Interaction)
        mock_interaction.user = MagicMock()
        mock_interaction.user.id = 12345
        mock_interaction.guild = MagicMock()
        mock_interaction.response = MagicMock()
        mock_interaction.response.is_done.return_value = False

        with patch("apex_core.financial_cooldown_manager.logger") as mock_logger:
            with pytest.raises(CooldownConfigurationError) as exc_info:
                await cog.unknown_financial_command(mock_interaction)

        assert "unknown_financial_command" in str(exc_info.value)
        # Should have logged an error
        mock_logger.error.assert_called_once()
        assert "unknown_financial_command" in str(mock_logger.error.call_args)

    @pytest.mark.asyncio
    async def test_decorator_works_for_known_command(self) -> None:
        """Decorator should work normally for known commands."""
        import discord

        class FakeCog:
            def __init__(self) -> None:
                self.bot = None

            @financial_cooldown()
            async def balance(self, interaction: discord.Interaction) -> str:
                return "balance_result"

        cog = FakeCog()
        mock_interaction = MagicMock(spec=discord.Interaction)
        mock_interaction.user = MagicMock()
        mock_interaction.user.id = 12345
        mock_interaction.guild = MagicMock()
        mock_interaction.response = MagicMock()
        mock_interaction.response.is_done.return_value = False

        # Reset global manager state
        manager = get_financial_cooldown_manager()
        await manager.reset_cooldown(12345, "balance")

        with patch("apex_core.financial_cooldown_manager.logger"):
            result = await cog.balance(mock_interaction)

        assert result == "balance_result"

    @pytest.mark.asyncio
    async def test_decorator_with_unknown_command_and_override_still_fails(self) -> None:
        """Decorator with overrides should still fail for unknown commands (_get_config is called first)."""
        import discord

        class FakeCog:
            def __init__(self) -> None:
                self.bot = None

            @financial_cooldown(seconds=30, tier=CooldownTier.STANDARD, operation_type="custom")
            async def custom_operation(self, interaction: discord.Interaction) -> str:
                return "custom_result"

        cog = FakeCog()
        mock_interaction = MagicMock(spec=discord.Interaction)
        mock_interaction.user = MagicMock()
        mock_interaction.user.id = 99999
        mock_interaction.guild = MagicMock()
        mock_interaction.response = MagicMock()
        mock_interaction.response.is_done.return_value = False

        # Reset any previous cooldown
        manager = get_financial_cooldown_manager()
        await manager.reset_cooldown(99999, "custom_operation")

        # This should raise because custom_operation is not in defaults
        # Even with decorator params, _get_config is called first
        with patch("apex_core.financial_cooldown_manager.logger"):
            with pytest.raises(CooldownConfigurationError):
                await cog.custom_operation(mock_interaction)


class TestManagerIntegration:
    """Integration tests for FinancialCooldownManager."""

    @pytest.mark.asyncio
    async def test_check_and_set_cooldown(self) -> None:
        """Test basic cooldown check and set functionality."""
        manager = FinancialCooldownManager()

        # Initially not on cooldown
        is_on_cooldown, remaining = await manager.check_cooldown(123, "balance")
        assert not is_on_cooldown
        assert remaining == 0

        # Set cooldown
        await manager.set_cooldown(123, "balance", 60)

        # Now on cooldown
        is_on_cooldown, remaining = await manager.check_cooldown(123, "balance")
        assert is_on_cooldown
        assert remaining > 0

    @pytest.mark.asyncio
    async def test_reset_cooldown(self) -> None:
        """Test cooldown reset functionality."""
        manager = FinancialCooldownManager()

        await manager.set_cooldown(456, "orders", 30)
        is_on_cooldown, _ = await manager.check_cooldown(456, "orders")
        assert is_on_cooldown

        result = await manager.reset_cooldown(456, "orders")
        assert result is True

        is_on_cooldown, _ = await manager.check_cooldown(456, "orders")
        assert not is_on_cooldown

    @pytest.mark.asyncio
    async def test_get_all_user_cooldowns(self) -> None:
        """Test getting all cooldowns for a user."""
        manager = FinancialCooldownManager()

        await manager.set_cooldown(789, "balance", 30)
        await manager.set_cooldown(789, "orders", 60)

        cooldowns = await manager.get_all_user_cooldowns(789)
        assert "balance" in cooldowns
        assert "orders" in cooldowns
        assert cooldowns["balance"] > 0
        assert cooldowns["orders"] > 0


class TestGlobalManagerInstance:
    """Tests for the global manager singleton."""

    def test_get_financial_cooldown_manager_returns_same_instance(self) -> None:
        """get_financial_cooldown_manager should return the same instance."""
        manager1 = get_financial_cooldown_manager()
        manager2 = get_financial_cooldown_manager()
        assert manager1 is manager2

    def test_global_manager_is_financial_cooldown_manager(self) -> None:
        """Global manager should be a FinancialCooldownManager instance."""
        manager = get_financial_cooldown_manager()
        assert isinstance(manager, FinancialCooldownManager)
