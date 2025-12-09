"""Tests for admin bypass logging elevation to INFO level."""

import discord
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from apex_core.financial_cooldown_manager import financial_cooldown, get_financial_cooldown_manager
from apex_core.rate_limiter import enforce_interaction_rate_limit, rate_limit


class TestAdminBypassLogging:
    """Test that admin bypass events are logged at INFO level."""

    @pytest.fixture
    def mock_admin_member(self):
        """Create a mock admin member."""
        member = MagicMock()
        member.id = 12345
        member.mention = "<@12345>"
        admin_role = MagicMock()
        admin_role.id = 42  # Admin role ID matches sample_config
        member.roles = [admin_role]
        return member

    @pytest.fixture
    def mock_non_admin_member(self):
        """Create a mock non-admin member."""
        member = MagicMock()
        member.id = 54321
        member.mention = "<@54321>"
        non_admin_role = MagicMock()
        non_admin_role.id = 1001  # Non-admin role
        member.roles = [non_admin_role]
        return member

    @pytest.fixture
    def mock_guild(self, mock_admin_member, mock_non_admin_member):
        """Create a mock guild with admin role configured."""
        guild = MagicMock()
        guild.id = 987654321
        guild.get_member.side_effect = lambda uid: {
            12345: mock_admin_member,
            54321: mock_non_admin_member,
        }.get(uid)
        return guild

    @pytest.fixture
    def mock_bot(self, mock_guild, sample_config):
        """Create a mock bot with config containing admin role."""
        from discord.ext import commands
        
        bot = MagicMock(spec=commands.Bot)
        bot.config = sample_config
        bot.guilds = [mock_guild]
        return bot

    @pytest.fixture
    def mock_interaction(self, mock_bot, mock_admin_member):
        """Create a mock interaction for admin user."""
        interaction = MagicMock(spec=discord.Interaction)
        interaction.user = mock_admin_member
        interaction.guild = mock_bot.guilds[0]
        interaction.channel = MagicMock()
        interaction.response = MagicMock()
        interaction.response.is_done.return_value = False
        interaction.client = mock_bot
        return interaction

    @pytest.mark.asyncio
    async def test_decorator_admin_bypass_logs_info(self, mock_bot, mock_interaction):
        """Test that @rate_limit decorator logs INFO when admin bypasses."""
        
        with patch('apex_core.rate_limiter.logger') as mock_rate_logger:
            @rate_limit(cooldown=60, max_uses=5, admin_bypass=True)
            async def test_command(self, interaction):
                return "success"
            
            # Setup bot on self object
            self_mock = MagicMock()
            self_mock.bot = mock_bot
            
            # Execute the decorated command
            await test_command(self_mock, mock_interaction)
            
            # Verify INFO logging was called with proper context
            mock_rate_logger.info.assert_called_once()
            log_message = mock_rate_logger.info.call_args[0][0]
            assert "Admin %s bypassed rate limit for %s" in log_message
            assert "(scope=%s, id=%s)" in log_message

    @pytest.mark.asyncio
    async def test_enforce_interaction_admin_bypass_logs_info(self, mock_bot, mock_interaction):
        """Test that enforce_interaction_rate_limit logs INFO when admin bypasses."""
        
        with patch('apex_core.rate_limiter.logger') as mock_rate_logger:
            await enforce_interaction_rate_limit(
                interaction=mock_interaction,
                command_key="test_button",
                cooldown=60,
                max_uses=5,
                admin_bypass=True,
            )
            
            # Verify INFO logging was called with proper context
            mock_rate_logger.info.assert_called_once()
            log_message = mock_rate_logger.info.call_args[0][0]
            assert "Admin %s bypassed rate limit for %s" in log_message
            assert "(scope=%s, id=%s)" in log_message

    @pytest.mark.asyncio
    async def test_financial_cooldown_admin_bypass_logs_info(self, mock_bot, mock_interaction):
        """Test that financial_cooldown decorator logs INFO when admin bypasses."""
        
        with patch('apex_core.financial_cooldown_manager.logger') as mock_financial_logger:
            @financial_cooldown(admin_bypass=True)
            async def test_financial_command(self, interaction):
                return "financial_success"
            
            # Setup bot on self object
            self_mock = MagicMock()
            self_mock.bot = mock_bot
            
            # Execute the decorated command
            result = await test_financial_command(self_mock, mock_interaction)
            assert result == "financial_success"
            
            # Verify INFO logging was called
            mock_financial_logger.info.assert_called_once()
            log_message = mock_financial_logger.info.call_args[0][0]
            assert "Admin %s bypassed financial cooldown for %s" in log_message

    @pytest.mark.asyncio
    async def test_non_admin_bypass_does_not_log_info(self, mock_bot):
        """Test that non-admin users don't trigger bypass logging."""
        # Create non-admin interaction
        non_admin_member = MagicMock()
        non_admin_member.id = 54321
        non_admin_member.mention = "<@54321>"
        non_admin_member.roles = [MagicMock(id=1001)]  # Non-admin role
        
        interaction = MagicMock(spec=discord.Interaction)
        interaction.user = non_admin_member
        interaction.guild = mock_bot.guilds[0]
        interaction.channel = MagicMock()
        interaction.response = MagicMock()
        interaction.response.is_done.return_value = False
        interaction.client = mock_bot
        
        with patch('apex_core.rate_limiter.logger') as mock_rate_logger:
            # Test decorator bypass
            @rate_limit(cooldown=60, max_uses=5, admin_bypass=True)
            async def test_command(self, interaction):
                return "success"
            
            self_mock = MagicMock()
            self_mock.bot = mock_bot
            
            # Should not log bypass since user is not admin
            await test_command(self_mock, interaction)
            
            # Verify no INFO bypass logging occurred
            assert not any(call for call in mock_rate_logger.info.call_args_list 
                          if "bypass" in str(call))

    @pytest.mark.asyncio
    async def test_admin_bypass_disabled_no_logging(self, mock_bot, mock_interaction):
        """Test that disabled admin_bypass doesn't trigger bypass logging."""
        
        with patch('apex_core.rate_limiter.logger') as mock_rate_logger:
            @rate_limit(cooldown=60, max_uses=5, admin_bypass=False)
            async def test_command(self, interaction):
                return "success"
            
            self_mock = MagicMock()
            self_mock.bot = mock_bot
            
            # Execute command with admin but bypass disabled
            await test_command(self_mock, mock_interaction)
            
            # Verify no INFO bypass logging occurred
            assert not any(call for call in mock_rate_logger.info.call_args_list 
                          if "bypass" in str(call))

    @pytest.mark.asyncio
    async def test_scoped_rate_limit_bypass_logging(self, mock_bot, mock_interaction):
        """Test that scoped rate limiting includes scope/ID context in bypass logs."""
        
        with patch('apex_core.rate_limiter.logger') as mock_rate_logger:
            @rate_limit(cooldown=60, max_uses=5, per="channel", admin_bypass=True)
            async def test_channel_command(self, interaction):
                return "success"
            
            self_mock = MagicMock()
            self_mock.bot = mock_bot
            
            # Execute the decorated command
            await test_channel_command(self_mock, mock_interaction)
            
            # Verify INFO logging includes channel scope context
            mock_rate_logger.info.assert_called_once()
            log_message = mock_rate_logger.info.call_args[0][0]
            assert "Admin %s bypassed rate limit for %s" in log_message
            assert "(scope=%s, id=%s)" in log_message


class TestBypassLoggingIntegration:
    """Integration tests for bypass logging behavior."""

    @pytest.mark.asyncio
    async def test_multiple_bypass_calls_logging(self, mock_bot):
        """Test that multiple bypass calls each generate their own INFO log."""
        
        # Create admin interaction
        admin_member = MagicMock()
        admin_member.id = 12345
        admin_member.mention = "<@12345>"
        admin_role = MagicMock()
        admin_role.id = 42
        admin_member.roles = [admin_role]
        
        guild = MagicMock()
        guild.id = 987654321
        guild.get_member.return_value = admin_member
        
        from discord.ext import commands
        
        bot = MagicMock(spec=commands.Bot)
        role_ids = MagicMock()
        role_ids.admin = 42
        config = MagicMock()
        config.role_ids = role_ids
        bot.config = config
        bot.guilds = [guild]
        
        async def create_interaction(command_key: str):
            interaction = MagicMock(spec=discord.Interaction)
            interaction.user = admin_member
            interaction.guild = guild
            interaction.channel = MagicMock()
            interaction.response = MagicMock()
            interaction.response.is_done.return_value = False
            interaction.client = bot
            return interaction
        
        with patch('apex_core.rate_limiter.logger') as mock_rate_logger:
            # Test multiple command bypasses
            commands = ["wallet_payment", "balance", "orders"]
            
            for command_key in commands:
                interaction = await create_interaction(command_key)
                await enforce_interaction_rate_limit(
                    interaction=interaction,
                    command_key=command_key,
                    cooldown=60,
                    max_uses=5,
                    admin_bypass=True,
                )
            
            # Verify each bypass was logged
            assert mock_rate_logger.info.call_count == 3
            for i, call in enumerate(mock_rate_logger.info.call_args_list):
                log_message = call[0][0]
                assert "Admin %s bypassed rate limit for %s" in log_message
                assert commands[i] in str(call[0])  # command name should be in the call arguments