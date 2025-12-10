"""Regression tests for stabilized setup foundation."""

import asyncio
import unittest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
import discord
from discord.ext import commands

from cogs.setup import (
    SetupCog, SetupSession, RollbackInfo, SetupOperationError
)
from apex_core.database import Database


def create_mock_bot():
    """Create a mock bot instance."""
    bot = Mock()
    bot.config = Mock()
    bot.config.role_ids = Mock()
    bot.config.role_ids.admin = 12345
    bot.config.logging_channels = Mock()
    bot.config.logging_channels.audit = 67890
    bot.db = Mock(spec=Database)
    bot.get_channel = Mock()
    bot.get_guild = Mock()
    bot.get_user = Mock()
    bot.loop = asyncio.new_event_loop()
    return bot


def create_setup_cog(mock_bot):
    """Create a SetupCog instance with mocked dependencies."""
    cog = SetupCog(mock_bot)
    return cog


def create_mock_guild():
    """Create a mock Discord guild."""
    guild = Mock(spec=discord.Guild)
    guild.id = 98765
    guild.me = Mock()
    guild.me.guild_permissions = Mock()
    guild.text_channels = []
    return guild


def create_mock_channel(mock_guild):
    """Create a mock Discord text channel."""
    channel = Mock(spec=discord.TextChannel)
    channel.guild = mock_guild
    channel.id = 11111
    channel.name = "test-channel"
    channel.permissions_for = Mock()
    channel.permissions_for.return_value = Mock()
    channel.permissions_for.return_value.send_messages = True
    channel.permissions_for.return_value.embed_links = True
    return channel


class TestSessionKeyManagement(unittest.TestCase):
    """Test concurrent session safety with (guild_id, user_id) keys."""
    
    def test_session_key_generation(self):
        """Test that session keys are generated correctly."""
        mock_bot = create_mock_bot()
        cog = create_setup_cog(mock_bot)
        
        key = cog._get_session_key(123, 456)
        self.assertEqual(key, (123, 456))
        self.assertIsInstance(key, tuple)
        self.assertEqual(len(key), 2)
    
    def test_multiple_guilds_same_user(self):
        """Test that same user can have sessions in multiple guilds."""
        mock_bot = create_mock_bot()
        cog = create_setup_cog(mock_bot)
        
        # User 123 in guild 456
        key1 = cog._get_session_key(456, 123)
        # User 123 in guild 789
        key2 = cog._get_session_key(789, 123)
        
        self.assertNotEqual(key1, key2)
        self.assertEqual(key1, (456, 123))
        self.assertEqual(key2, (789, 123))
    
    def test_same_guild_different_users(self):
        """Test that different users can have sessions in same guild."""
        mock_bot = create_mock_bot()
        cog = create_setup_cog(mock_bot)
        
        # User 123 in guild 456
        key1 = cog._get_session_key(456, 123)
        # User 789 in guild 456
        key2 = cog._get_session_key(456, 789)
        
        self.assertNotEqual(key1, key2)
        self.assertEqual(key1, (456, 123))
        self.assertEqual(key2, (456, 789))


class TestEligibleChannelsPrecomputation(unittest.TestCase):
    """Test permission validation at setup start."""
    
    def test_missing_manage_channels_permission(self):
        """Test setup fails early when bot lacks Manage Channels permission."""
        async def run_test():
            mock_bot = create_mock_bot()
            cog = create_setup_cog(mock_bot)
            mock_guild = create_mock_guild()
            
            mock_guild.me.guild_permissions.manage_channels = False
            
            with self.assertRaises(SetupOperationError) as cm:
                await cog._precompute_eligible_channels(mock_guild)
            
            self.assertIn("Manage Channels", str(cm.exception))
        
        asyncio.run(run_test())
    
    def test_no_eligible_channels(self):
        """Test setup fails when no channels have required permissions."""
        async def run_test():
            mock_bot = create_mock_bot()
            cog = create_setup_cog(mock_bot)
            mock_guild = create_mock_guild()
            
            mock_guild.me.guild_permissions.manage_channels = True
            
            # Create channels without proper permissions
            channel1 = Mock()
            channel1.permissions_for.return_value.send_messages = False
            channel1.permissions_for.return_value.embed_links = True
            
            channel2 = Mock()
            channel2.permissions_for.return_value.send_messages = True
            channel2.permissions_for.return_value.embed_links = False
            
            mock_guild.text_channels = [channel1, channel2]
            
            with self.assertRaises(SetupOperationError) as cm:
                await cog._precompute_eligible_channels(mock_guild)
            
            self.assertIn("No eligible channels", str(cm.exception))
        
        asyncio.run(run_test())
    
    def test_successful_eligible_channels_computation(self):
        """Test successful computation of eligible channels."""
        async def run_test():
            mock_bot = create_mock_bot()
            cog = create_setup_cog(mock_bot)
            mock_guild = create_mock_guild()
            mock_channel = create_mock_channel(mock_guild)
            
            mock_guild.me.guild_permissions.manage_channels = True
            mock_guild.text_channels = [mock_channel]
            
            eligible = await cog._precompute_eligible_channels(mock_guild)
            
            self.assertEqual(len(eligible), 1)
            self.assertIn(mock_channel, eligible)
            self.assertTrue(mock_channel.permissions_for.return_value.send_messages)
            self.assertTrue(mock_channel.permissions_for.return_value.embed_links)
        
        asyncio.run(run_test())


class TestAtomicTransactions(unittest.TestCase):
    """Test atomic database transactions for panel deployment."""
    
    def test_successful_transaction(self):
        """Test successful database transaction commits properly."""
        async def run_test():
            mock_bot = create_mock_bot()
            transaction_mock = AsyncMock()
            transaction_mock.execute_insert = AsyncMock(return_value=123)
            
            # Create proper async context manager
            class MockTx:
                async def __aenter__(self):
                    return transaction_mock
                async def __aexit__(self, *args):
                    return False
            
            mock_bot.db.transaction = Mock(return_value=MockTx())
            
            async with mock_bot.db.transaction() as tx:
                result = await tx.execute_insert(
                    "INSERT INTO permanent_messages (type, message_id) VALUES (?, ?)",
                    ("products", 456)
                )
            
            # Verify transaction context manager was used correctly
            self.assertEqual(result, 123)
            mock_bot.db.transaction.assert_called_once()
        
        asyncio.run(run_test())
    
    def test_transaction_rollback_on_error(self):
        """Test transaction rolls back on exception."""
        async def run_test():
            mock_bot = create_mock_bot()
            transaction_mock = AsyncMock()
            rollback_called = False
            
            class MockTx:
                async def __aenter__(self):
                    return transaction_mock
                
                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    nonlocal rollback_called
                    if exc_type:
                        # Mark that rollback should happen
                        rollback_called = True
                    return False
            
            mock_bot.db.transaction = Mock(return_value=MockTx())
            
            with self.assertRaises(ValueError):
                async with mock_bot.db.transaction():
                    raise ValueError("test error")
            
            # Verify rollback was triggered
            self.assertTrue(rollback_called)
        
        asyncio.run(run_test())
    
    def test_panel_deployment_uses_transaction(self):
        """Test _deploy_panel uses database transaction."""
        async def run_test():
            mock_bot = create_mock_bot()
            cog = create_setup_cog(mock_bot)
            mock_guild = Mock()
            mock_guild.id = 98765
            mock_channel = Mock()
            mock_channel.id = 11111
            mock_message = Mock()
            mock_message.id = 789
            
            # Create a session for the deployment
            session = SetupSession(
                guild_id=98765,
                user_id=123,
                panel_types=["products"],
                current_index=0,
                completed_panels=[],
                rollback_stack=[],
                eligible_channels=[mock_channel],
                session_lock=asyncio.Lock()
            )
            cog.setup_sessions[(98765, 123)] = session
            
            mock_channel.send = AsyncMock(return_value=mock_message)
            mock_bot.db.find_panel = AsyncMock(return_value=None)
            
            # Mock transaction context manager properly
            transaction_mock = Mock()
            transaction_mock.execute_insert = AsyncMock(return_value=456)
            transaction_mock.execute = AsyncMock()
            
            class MockTx:
                def __init__(self):
                    self.tx = transaction_mock
                
                async def __aenter__(self):
                    return self.tx
                
                async def __aexit__(self, *args):
                    return False
            
            mock_bot.db.transaction = Mock(return_value=MockTx())
            
            # Mock panel creation methods
            cog._create_product_panel = AsyncMock(return_value=(Mock(), Mock()))
            cog._log_audit = AsyncMock()
            
            result = await cog._deploy_panel(
                "products", mock_channel, mock_guild, 123
            )
            
            self.assertTrue(result)
            mock_bot.db.transaction.assert_called_once()
        
        asyncio.run(run_test())


class TestRollbackInfoExtension(unittest.TestCase):
    """Test RollbackInfo with previous_message_id for updates."""
    
    def test_rollback_info_creation(self):
        """Test RollbackInfo dataclass works with new fields."""
        rollback = RollbackInfo(
            operation_type="panel_updated",
            panel_type="products",
            panel_id=123,
            previous_message_id=456,
            guild_id=789,
            user_id=111
        )
        
        self.assertEqual(rollback.operation_type, "panel_updated")
        self.assertEqual(rollback.panel_type, "products")
        self.assertEqual(rollback.panel_id, 123)
        self.assertEqual(rollback.previous_message_id, 456)
        self.assertEqual(rollback.guild_id, 789)
        self.assertEqual(rollback.user_id, 111)
        self.assertIsNotNone(rollback.timestamp)
    
    def test_rollback_info_defaults(self):
        """Test RollbackInfo defaults work correctly."""
        rollback = RollbackInfo(
            operation_type="message_sent",
            panel_type="products"
        )
        
        self.assertIsNone(rollback.previous_message_id)
        self.assertIsNotNone(rollback.timestamp)


class TestTimeoutHandling(unittest.TestCase):
    """Test view timeout notifications."""
    
    def test_setup_menu_view_timeout(self):
        """Test SetupMenuView handles timeout correctly."""
        async def run_test():
            from cogs.setup import SetupMenuView
            
            view = SetupMenuView()
            view.original_interaction = AsyncMock()
            view.original_interaction.followup.send = AsyncMock()
            
            await view.on_timeout()
            
            view.original_interaction.followup.send.assert_called_once_with(
                "⏰ Setup menu timed out. Please run the setup command again.",
                ephemeral=True
            )
        
        asyncio.run(run_test())
    
    def test_continue_setup_view_timeout(self):
        """Test ContinueSetupView handles timeout correctly."""
        async def run_test():
            from cogs.setup import ContinueSetupView
            
            view = ContinueSetupView("products", 123)
            view.original_interaction = AsyncMock()
            view.original_interaction.followup.send = AsyncMock()
            
            await view.on_timeout()
            
            view.original_interaction.followup.send.assert_called_once_with(
                "⏰ Setup timed out. Please run the setup command again.",
                ephemeral=True
            )
        
        asyncio.run(run_test())
    
    def test_deployment_select_view_timeout(self):
        """Test DeploymentSelectView handles timeout correctly."""
        async def run_test():
            from cogs.setup import DeploymentSelectView
            
            view = DeploymentSelectView(123)
            view.original_interaction = AsyncMock()
            view.original_interaction.followup.send = AsyncMock()
            
            await view.on_timeout()
            
            view.original_interaction.followup.send.assert_called_once_with(
                "⏰ Deployment menu timed out. Please try again.",
                ephemeral=True
            )
        
        asyncio.run(run_test())


class TestSetupSessionManagement(unittest.TestCase):
    """Test SetupSession lifecycle and management."""
    
    def test_setup_session_creation(self):
        """Test SetupSession is created correctly."""
        mock_bot = create_mock_bot()
        cog = create_setup_cog(mock_bot)
        mock_guild = create_mock_guild()
        
        channel1 = Mock()
        channel1.name = "channel1"
        
        session = SetupSession(
            guild_id=mock_guild.id,
            user_id=123,
            panel_types=["products", "support"],
            current_index=0,
            completed_panels=[],
            rollback_stack=[],
            eligible_channels=[channel1],
            started_at=None,
            session_lock=asyncio.Lock()
        )
        
        self.assertEqual(session.guild_id, mock_guild.id)
        self.assertEqual(session.user_id, 123)
        self.assertEqual(session.panel_types, ["products", "support"])
        self.assertEqual(session.current_index, 0)
        self.assertEqual(session.completed_panels, [])
        self.assertEqual(session.eligible_channels, [channel1])
        self.assertIsNotNone(session.session_lock)
        self.assertIsNotNone(session.timestamp)
    
    def test_session_cleanup(self):
        """Test setup session cleanup removes session properly."""
        async def run_test():
            mock_bot = create_mock_bot()
            cog = create_setup_cog(mock_bot)
            mock_guild = create_mock_guild()
            
            # Create a session with rollback items
            session_key = (mock_guild.id, 123)
            rollback_item = RollbackInfo(
                operation_type="panel_created",
                panel_type="products",
                panel_id=123
            )
            session = SetupSession(
                guild_id=mock_guild.id,
                user_id=123,
                panel_types=["products"],
                current_index=0,
                completed_panels=[],
                rollback_stack=[rollback_item],  # Non-empty rollback stack
                eligible_channels=[],
                started_at=None,
                session_lock=asyncio.Lock()
            )
            cog.setup_sessions[session_key] = session
            
            # Mock rollback execution
            cog._execute_rollback_stack = AsyncMock()
            
            await cog._cleanup_setup_session(mock_guild.id, 123, "Test cleanup")
            
            self.assertNotIn(session_key, cog.setup_sessions)
            cog._execute_rollback_stack.assert_called_once()
        
        asyncio.run(run_test())


class TestPanelDeploymentWithEligibleChannels(unittest.TestCase):
    """Test panel deployment respects eligible channels list."""
    
    def test_deployment_with_eligible_channel(self):
        """Test deployment succeeds with eligible channel."""
        async def run_test():
            mock_bot = create_mock_bot()
            cog = create_setup_cog(mock_bot)
            mock_guild = create_mock_guild()
            mock_channel = create_mock_channel(mock_guild)
            
            session_key = (mock_guild.id, 123)
            session = SetupSession(
                guild_id=mock_guild.id,
                user_id=123,
                panel_types=["products"],
                current_index=0,
                completed_panels=[],
                rollback_stack=[],
                eligible_channels=[mock_channel],
                started_at=None,
                session_lock=asyncio.Lock()
            )
            cog.setup_sessions[session_key] = session
            
            # Mock successful deployment
            cog._deploy_panel = AsyncMock(return_value=True)
            
            # Mock interaction properly
            interaction = AsyncMock()
            interaction.guild = mock_guild
            interaction.user = Mock()
            interaction.user.id = 123
            interaction.followup.send = AsyncMock()
            
            # Mock channel find
            with patch.object(cog, '_find_channel_by_input', return_value=mock_channel):
                await cog._process_channel_input(
                    interaction, "test-channel", "products", session
                )
            
            cog._deploy_panel.assert_called_once()
        
        asyncio.run(run_test())
    
    def test_deployment_rejects_ineligible_channel(self):
        """Test deployment fails with ineligible channel."""
        async def run_test():
            mock_bot = create_mock_bot()
            cog = create_setup_cog(mock_bot)
            mock_guild = create_mock_guild()
            
            channel1 = Mock()
            channel1.name = "eligible"
            
            channel2 = Mock()
            channel2.name = "ineligible"
            
            session_key = (mock_guild.id, 123)
            session = SetupSession(
                guild_id=mock_guild.id,
                user_id=123,
                panel_types=["products"],
                current_index=0,
                completed_panels=[],
                rollback_stack=[],
                eligible_channels=[channel1],  # Only channel1 is eligible
                started_at=None,
                session_lock=asyncio.Lock()
            )
            cog.setup_sessions[session_key] = session
            
            interaction = AsyncMock()
            interaction.guild = mock_guild
            interaction.followup.send = AsyncMock()
            
            with patch.object(cog, '_find_channel_by_input', return_value=channel2):
                await cog._process_channel_input(
                    interaction, "ineligible", "products", session
                )
            
            interaction.followup.send.assert_called_once()
            call_args = interaction.followup.send.call_args[0][0]
            self.assertIn("not eligible", call_args)
        
        asyncio.run(run_test())


class TestBackwardCompatibility(unittest.TestCase):
    """Test backward compatibility with legacy WizardState."""
    
    def test_legacy_state_migration(self):
        """Test that legacy states are still handled correctly."""
        async def run_test():
            mock_bot = create_mock_bot()
            cog = create_setup_cog(mock_bot)
            mock_guild = create_mock_guild()
            
            from cogs.setup import WizardState
            
            # Create legacy state with rollback item
            rollback_item = RollbackInfo(
                operation_type="panel_created",
                panel_type="products",
                panel_id=123
            )
            legacy_state = WizardState(
                user_id=123,
                guild_id=mock_guild.id,
                panel_types=["products"],
                current_index=0,
                completed_panels=[],
                rollback_stack=[rollback_item],  # Non-empty rollback stack
                started_at=None
            )
            cog.user_states[123] = legacy_state
            
            # Test cleanup still works
            cog._execute_rollback_stack = AsyncMock()
            
            await cog._cleanup_wizard_state(123, "Test migration")
            
            self.assertNotIn(123, cog.user_states)
            cog._execute_rollback_stack.assert_called_once()
        
        asyncio.run(run_test())


class TestDatabaseIntegration(unittest.TestCase):
    """Test integration with database transaction helper."""
    
    def test_database_transaction_helper(self):
        """Test Database.transaction() method works correctly."""
        async def run_test():
            db = Database(":memory:")
            await db.connect()
            
            try:
                async with db.transaction() as tx:
                    await tx.execute("CREATE TABLE test (id INTEGER)")
                    await tx.execute("INSERT INTO test VALUES (1)")
                    
                    cursor = await tx.execute("SELECT * FROM test")
                    row = await cursor.fetchone()
                    self.assertEqual(row[0], 1)
                    
                # Verify transaction committed
                async with db.transaction() as tx:
                    cursor = await tx.execute("SELECT COUNT(*) FROM test")
                    count = await cursor.fetchone()
                    self.assertEqual(count[0], 1)
                    
            finally:
                await db.close()
        
        asyncio.run(run_test())
    
    def test_transaction_rollback_behavior(self):
        """Test transaction rolls back on error."""
        async def run_test():
            db = Database(":memory:")
            await db.connect()
            
            try:
                # Create table outside transaction
                async with db.transaction() as tx:
                    await tx.execute("CREATE TABLE test (id INTEGER)")
                
                # Try to insert with rollback
                try:
                    async with db.transaction() as tx:
                        await tx.execute("INSERT INTO test VALUES (1)")
                        raise Exception("Test rollback")
                except Exception:
                    pass
                    
                # Verify rollback worked - table exists but no rows inserted
                async with db.transaction() as tx:
                    cursor = await tx.execute("SELECT COUNT(*) FROM test")
                    count = await cursor.fetchone()
                    self.assertEqual(count[0], 0)  # Should be empty due to rollback
                    
            finally:
                await db.close()
        
        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()