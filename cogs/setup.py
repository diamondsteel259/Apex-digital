from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional, Any, Dict, List
from dataclasses import dataclass
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from apex_core.utils import create_embed, format_usd

logger = logging.getLogger(__name__)


@dataclass
class RollbackInfo:
    """Information needed for rollback operations."""
    operation_type: str
    panel_type: str
    channel_id: Optional[int] = None
    message_id: Optional[int] = None
    previous_message_id: Optional[int] = None
    panel_id: Optional[int] = None
    guild_id: Optional[int] = None
    user_id: Optional[int] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)


@dataclass
class SetupSession:
    """Session state for setup wizard with concurrent guild support."""
    guild_id: int
    user_id: int
    panel_types: list[str]
    current_index: int
    completed_panels: list[str]
    rollback_stack: list[RollbackInfo]
    eligible_channels: list[discord.TextChannel]
    started_at: Optional[datetime] = None
    timestamp: Optional[datetime] = None
    session_lock: asyncio.Lock = None
    
    def __post_init__(self):
        if self.started_at is None:
            self.started_at = datetime.now(timezone.utc)
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)
        if self.session_lock is None:
            self.session_lock = asyncio.Lock()


@dataclass
class WizardState:
    """State tracking for multi-step setup wizard."""
    user_id: int
    guild_id: int
    panel_types: List[str]
    current_index: int
    completed_panels: List[str]
    rollback_stack: List[RollbackInfo]
    started_at: datetime
    
    def __post_init__(self):
        if self.started_at is None:
            self.started_at = datetime.now(timezone.utc)


class SetupOperationError(Exception):
    """Custom exception for setup operation failures."""
    def __init__(self, message: str, rollback_info: Optional[RollbackInfo] = None):
        super().__init__(message)
        self.rollback_info = rollback_info


class SetupMenuSelect(discord.ui.Select["SetupMenuView"]):
    """Select menu for choosing which panels to setup."""
    
    def __init__(self) -> None:
        options = [
            discord.SelectOption(label="Product Catalog Panel (storefront)", value="products", emoji="1️⃣"),
            discord.SelectOption(label="Support & Refund Buttons", value="support", emoji="2️⃣"),
            discord.SelectOption(label="Help Guide", value="help", emoji="3️⃣"),
            discord.SelectOption(label="Review System Guide", value="reviews", emoji="4️⃣"),
            discord.SelectOption(label="All of the above", value="all", emoji="5️⃣"),
        ]
        super().__init__(
            placeholder="Select what to setup...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        cog: SetupCog = interaction.client.get_cog("SetupCog")  # type: ignore
        if not cog:
            await interaction.response.send_message(
                "Setup cog not loaded.", ephemeral=True
            )
            return

        selection = self.values[0]
        await cog._handle_setup_selection(interaction, selection)


class SetupMenuView(discord.ui.View):
    """View for the initial setup menu."""
    
    def __init__(self) -> None:
        super().__init__(timeout=300)
        self.add_item(SetupMenuSelect())
    
    async def on_timeout(self) -> None:
        """Handle view timeout by notifying the original invoker."""
        try:
            if hasattr(self, 'original_interaction') and self.original_interaction:
                await self.original_interaction.followup.send(
                    "⏰ Setup menu timed out. Please run the setup command again.",
                    ephemeral=True
                )
        except Exception as e:
            logger.error(f"Failed to send timeout message: {e}")


class ContinueSetupButton(discord.ui.Button):
    """Button to continue setting up next panel."""
    
    def __init__(self, panel_type: str, user_id: int) -> None:
        super().__init__(
            label=f"Continue: Setup {panel_type.title()} Panel",
            style=discord.ButtonStyle.primary,
            emoji="▶️"
        )
        self.panel_type = panel_type
        self.user_id = user_id
    
    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "You can't use this button.", ephemeral=True
            )
            return
        
        # Show the modal for the next panel
        modal = ChannelInputModal(self.panel_type)
        await interaction.response.send_modal(modal)


class ContinueSetupView(discord.ui.View):
    """View with button to continue multi-panel setup."""
    
    def __init__(self, panel_type: str, user_id: int) -> None:
        super().__init__(timeout=300)
        self.add_item(ContinueSetupButton(panel_type, user_id))
    
    async def on_timeout(self) -> None:
        """Handle view timeout by notifying the original invoker."""
        try:
            if hasattr(self, 'original_interaction') and self.original_interaction:
                await self.original_interaction.followup.send(
                    "⏰ Setup timed out. Please run the setup command again.",
                    ephemeral=True
                )
        except Exception as e:
            logger.error(f"Failed to send timeout message: {e}")


class ChannelInputModal(discord.ui.Modal, title="Channel Selection"):
    """Modal for users to input the channel destination."""
    
    channel_input = discord.ui.TextInput(
        label="Channel name or #mention",
        placeholder="e.g., products or #products",
        required=True,
        max_length=100,
    )

    def __init__(self, panel_type: str, session: Optional[SetupSession] = None) -> None:
        super().__init__()
        self.panel_type = panel_type
        self.session = session
        # Update title to show which panel we're setting up
        self.title = f"Deploy {panel_type.title()} Panel"

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        cog: SetupCog = interaction.client.get_cog("SetupCog")  # type: ignore
        if not cog:
            await interaction.followup.send("Setup cog not loaded.", ephemeral=True)
            return

        await cog._process_channel_input(interaction, self.channel_input.value, self.panel_type, self.session)


class PanelTypeModal(discord.ui.Modal, title="Select Panel Type"):
    """Modal for selecting which panel to deploy or modify."""
    
    panel_type = discord.ui.TextInput(
        label="Panel type (products/support/help/reviews)",
        placeholder="Type the panel type",
        required=True,
        max_length=50,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        cog: SetupCog = interaction.client.get_cog("SetupCog")  # type: ignore
        if not cog:
            await interaction.followup.send("Setup cog not loaded.", ephemeral=True)
            return

        await cog._show_deployment_menu(interaction, self.panel_type.value)


class DeploymentSelectView(discord.ui.View):
    """View for selecting deployment actions."""
    
    def __init__(self, interaction_user_id: int) -> None:
        super().__init__(timeout=300)
        self.interaction_user_id = interaction_user_id
    
    async def on_timeout(self) -> None:
        """Handle view timeout by notifying the original invoker."""
        try:
            if hasattr(self, 'original_interaction') and self.original_interaction:
                await self.original_interaction.followup.send(
                    "⏰ Deployment menu timed out. Please try again.",
                    ephemeral=True
                )
        except Exception as e:
            logger.error(f"Failed to send timeout message: {e}")

    @discord.ui.button(label="Deploy New", style=discord.ButtonStyle.primary, emoji="🚀")
    async def deploy_new(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id != self.interaction_user_id:
            await interaction.response.send_message("You can't use this button.", ephemeral=True)
            return

        cog: SetupCog = interaction.client.get_cog("SetupCog")  # type: ignore
        if not cog:
            await interaction.response.send_message("Setup cog not loaded.", ephemeral=True)
            return

        await interaction.response.send_modal(PanelTypeModal())

    @discord.ui.button(label="Update", style=discord.ButtonStyle.secondary, emoji="✏️")
    async def update_panel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id != self.interaction_user_id:
            await interaction.response.send_message("You can't use this button.", ephemeral=True)
            return

        cog: SetupCog = interaction.client.get_cog("SetupCog")  # type: ignore
        if not cog:
            await interaction.response.send_message("Setup cog not loaded.", ephemeral=True)
            return

        await interaction.response.send_modal(PanelTypeModal())

    @discord.ui.button(label="Remove", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def remove_panel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id != self.interaction_user_id:
            await interaction.response.send_message("You can't use this button.", ephemeral=True)
            return

        cog: SetupCog = interaction.client.get_cog("SetupCog")  # type: ignore
        if not cog:
            await interaction.response.send_message("Setup cog not loaded.", ephemeral=True)
            return

        await interaction.response.send_modal(PanelTypeModal())

    @discord.ui.button(label="Done", style=discord.ButtonStyle.success, emoji="✅")
    async def done(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id != self.interaction_user_id:
            await interaction.response.send_message("You can't use this button.", ephemeral=True)
            return

        await interaction.response.send_message("Setup wizard complete!", ephemeral=True)


class SetupCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # Use (guild_id, user_id) tuple as key to allow concurrent setups in different guilds
        self.setup_sessions: dict[tuple[int, int], SetupSession] = {}
        # Keep legacy states for backward compatibility during migration
        self.user_states: dict[int, WizardState] = {}
        # Clean up expired states every 5 minutes
        self.bot.loop.create_task(self._cleanup_expired_states())

    def _is_admin(self, member: discord.Member | None) -> bool:
        if member is None:
            return False
        admin_role_id = self.bot.config.role_ids.admin
        return any(role.id == admin_role_id for role in getattr(member, "roles", []))

    @asynccontextmanager
    async def _atomic_operation(self, session: SetupSession, operation_name: str):
        """Context manager for atomic operations with automatic rollback using session lock."""
        try:
            async with session.session_lock:
                yield session.rollback_stack
        except Exception as e:
            logger.error(f"Atomic operation '{operation_name}' failed: {e}")
            await self._execute_rollback_stack(session, f"Failed operation: {operation_name}")
            raise

    async def _execute_rollback_stack(self, rollback_stack: List[RollbackInfo], reason: str) -> None:
        """Execute a stack of rollback operations."""
        for rollback_info in reversed(rollback_stack):
            try:
                await self._rollback_single_operation(rollback_info)
                logger.info(f"Rolled back {rollback_info.operation_type} for {rollback_info.panel_type}")
            except Exception as e:
                logger.error(f"Failed to rollback {rollback_info.operation_type}: {e}")
        
        # Log the rollback operation
        if rollback_stack:
            await self._log_rollback_operation(rollback_stack, reason)

    async def _rollback_single_operation(self, rollback_info: RollbackInfo) -> None:
        """Rollback a single operation based on its type."""
        if rollback_info.operation_type == "message_sent":
            if rollback_info.channel_id and rollback_info.message_id:
                channel = self.bot.get_channel(rollback_info.channel_id)
                if isinstance(channel, discord.TextChannel):
                    try:
                        message = await channel.fetch_message(rollback_info.message_id)
                        await message.delete()
                    except discord.NotFound:
                        pass  # Message already deleted
                    except discord.Forbidden:
                        logger.warning(f"No permission to delete message {rollback_info.message_id}")

        elif rollback_info.operation_type == "panel_created":
            if rollback_info.panel_id:
                await self.bot.db.remove_panel(rollback_info.panel_id)

        elif rollback_info.operation_type == "panel_updated":
            # For panel updates, restore the previous message ID if available
            if rollback_info.panel_id and rollback_info.previous_message_id:
                try:
                    await self.bot.db.update_panel(rollback_info.panel_id, rollback_info.previous_message_id)
                    logger.info(f"Restored previous message ID {rollback_info.previous_message_id} for panel {rollback_info.panel_id}")
                except Exception as e:
                    logger.error(f"Failed to restore previous message ID: {e}")
            else:
                logger.info(f"Panel update rollback for panel_id {rollback_info.panel_id} - manual cleanup may be needed")

    async def _log_rollback_operation(self, rollback_stack: List[RollbackInfo], reason: str) -> None:
        """Log rollback operations to audit channel."""
        if not rollback_stack:
            return

        # Get guild from first rollback info
        guild_id = rollback_stack[0].guild_id
        if not guild_id:
            return

        guild = self.bot.get_guild(guild_id)
        if not guild:
            return

        embed = create_embed(
            title="🔄 Setup Rollback Executed",
            description=f"**Reason:** {reason}\n**Operations Rolled Back:** {len(rollback_stack)}",
            color=discord.Color.orange(),
        )

        for i, rollback_info in enumerate(rollback_stack[:5], 1):  # Limit to first 5 for embed size
            embed.add_field(
                name=f"{i}. {rollback_info.operation_type}",
                value=f"Panel: {rollback_info.panel_type}\nTime: {rollback_info.timestamp.strftime('%H:%M:%S')}",
                inline=False,
            )

        if len(rollback_stack) > 5:
            embed.add_field(
                name="Additional Operations",
                value=f"... and {len(rollback_stack) - 5} more",
                inline=False,
            )

        embed.set_footer(text="Apex Core • Setup Recovery")
        
        try:
            audit_channel_id = self.bot.config.logging_channels.audit
            if audit_channel_id:
                audit_channel = guild.get_channel(audit_channel_id)
                if isinstance(audit_channel, discord.TextChannel):
                    await audit_channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Failed to log rollback: {e}")

    async def _validate_operation_prerequisites(self, guild: discord.Guild, channel: discord.TextChannel) -> None:
        """Validate that all prerequisites are met for setup operations."""
        if not guild.me.guild_permissions.manage_channels:
            raise SetupOperationError("Bot needs 'Manage Channels' permission")

        if not channel.permissions_for(guild.me).send_messages:
            raise SetupOperationError(f"Bot cannot send messages in {channel.mention}")
        
        if not channel.permissions_for(guild.me).embed_links:
            raise SetupOperationError(f"Bot cannot embed links in {channel.mention}")

        # Test database connection
        try:
            await self.bot.db.get_deployments(guild.id)
        except Exception as e:
            raise SetupOperationError(f"Database connection failed: {e}")

    async def _precompute_eligible_channels(self, guild: discord.Guild) -> list[discord.TextChannel]:
        """Pre-compute eligible channels at setup start to surface permission issues early.
        
        Args:
            guild: The Discord guild to check channels for
            
        Returns:
            List of eligible text channels with required permissions
            
        Raises:
            SetupOperationError: If bot lacks required permissions for the guild
        """
        if not guild.me.guild_permissions.manage_channels:
            raise SetupOperationError("Bot needs 'Manage Channels' permission to setup panels")

        eligible_channels = []
        for channel in guild.text_channels:
            if (channel.permissions_for(guild.me).send_messages and 
                channel.permissions_for(guild.me).embed_links):
                eligible_channels.append(channel)
        
        if not eligible_channels:
            raise SetupOperationError(
                "No eligible channels found. Bot needs 'Send Messages' and 'Embed Links' "
                "permissions in at least one text channel."
            )
        
        return eligible_channels

    def _get_session_key(self, guild_id: int, user_id: int) -> tuple[int, int]:
        """Get the session key for a guild and user combination."""
        return (guild_id, user_id)

    async def _cleanup_wizard_state(self, user_id: int, reason: str) -> None:
        """Clean up wizard state and rollback any incomplete operations."""
        # Handle legacy user states
        if user_id in self.user_states:
            state = self.user_states[user_id]
            
            # Rollback any incomplete operations
            if hasattr(state, 'rollback_stack') and state.rollback_stack:
                await self._execute_rollback_stack(state.rollback_stack, f"Wizard cleanup: {reason}")
            
            # Remove state
            del self.user_states[user_id]
            logger.info(f"Cleaned up wizard state for user {user_id}: {reason}")

    async def _cleanup_setup_session(self, guild_id: int, user_id: int, reason: str) -> None:
        """Clean up setup session and rollback any incomplete operations."""
        session_key = self._get_session_key(guild_id, user_id)
        
        if session_key in self.setup_sessions:
            session = self.setup_sessions[session_key]
            
            # Rollback any incomplete operations
            if session.rollback_stack:
                await self._execute_rollback_stack(session.rollback_stack, f"Session cleanup: {reason}")
            
            # Remove session
            del self.setup_sessions[session_key]
            logger.info(f"Cleaned up setup session for guild {guild_id}, user {user_id}: {reason}")

    async def _cleanup_expired_states(self) -> None:
        """Clean up expired wizard states and setup sessions."""
        while True:
            try:
                await asyncio.sleep(300)  # Check every 5 minutes
                current_time = datetime.now(timezone.utc)
                expired_users = []
                expired_sessions = []

                # Check legacy user states
                for user_id, state in self.user_states.items():
                    # Expire after 30 minutes of inactivity
                    if hasattr(state, 'started_at') and (current_time - state.started_at).total_seconds() > 1800:
                        expired_users.append(user_id)

                # Check new setup sessions
                for (guild_id, user_id), session in self.setup_sessions.items():
                    # Expire after 30 minutes of inactivity
                    if (current_time - session.started_at).total_seconds() > 1800:
                        expired_sessions.append((guild_id, user_id))

                # Clean up expired states
                for user_id in expired_users:
                    await self._cleanup_wizard_state(user_id, "Session expired")

                for guild_id, user_id in expired_sessions:
                    await self._cleanup_setup_session(guild_id, user_id, "Session expired")

            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")

    async def _cleanup_expired_states_manual(self) -> int:
        """Manually clean up expired wizard states and return count."""
        current_time = datetime.now(timezone.utc)
        expired_users = []

        for user_id, state in self.user_states.items():
            # Expire after 30 minutes of inactivity
            if hasattr(state, 'started_at') and (current_time - state.started_at).total_seconds() > 1800:
                expired_users.append(user_id)

        for user_id in expired_users:
            await self._cleanup_wizard_state(user_id, "Manual expired cleanup")

        return len(expired_users)

    async def _deploy_panel(self, panel_type: str, channel: discord.TextChannel, 
                          guild: discord.Guild, user_id: int) -> bool:
        """Deploy a panel with atomic transaction support."""
        
        # Find existing session for this guild and user
        session_key = self._get_session_key(guild.id, user_id)
        session = self.setup_sessions.get(session_key)
        
        if not session:
            logger.error(f"No setup session found for guild {guild.id}, user {user_id}")
            return False

        try:
            # Get the panel embed and view
            if panel_type == "products":
                embed, view = await self._create_product_panel()
            elif panel_type == "support":
                embed, view = await self._create_support_panel()
            elif panel_type == "help":
                embed, view = await self._create_help_panel()
            elif panel_type == "reviews":
                embed, view = await self._create_reviews_panel()
            else:
                raise SetupOperationError(f"Unknown panel type: {panel_type}")

            # Check if this is an update to an existing panel
            existing_panel = await self.bot.db.find_panel(panel_type, guild.id)
            previous_message_id = existing_panel["message_id"] if existing_panel else None
            
            # Store sent messages for rollback cleanup
            sent_messages: list[tuple[int, int]] = []  # (channel_id, message_id)

            async with self.bot.db.transaction() as tx:
                # Send the panel message
                message = await channel.send(embed=embed, view=view)
                sent_messages.append((channel.id, message.id))
                
                # Create rollback info for message
                message_rollback = RollbackInfo(
                    operation_type="message_sent",
                    panel_type=panel_type,
                    channel_id=channel.id,
                    message_id=message.id,
                    guild_id=guild.id,
                    user_id=user_id
                )
                session.rollback_stack.append(message_rollback)

                if existing_panel:
                    # Update existing panel
                    await tx.execute(
                        """
                        UPDATE permanent_messages 
                        SET message_id = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        (message.id, existing_panel["id"])
                    )
                    
                    # Add rollback info for panel update
                    update_rollback = RollbackInfo(
                        operation_type="panel_updated",
                        panel_type=panel_type,
                        panel_id=existing_panel["id"],
                        previous_message_id=previous_message_id,
                        guild_id=guild.id,
                        user_id=user_id
                    )
                    session.rollback_stack.append(update_rollback)
                else:
                    # Create new panel record
                    panel_id = await tx.execute_insert(
                        """
                        INSERT INTO permanent_messages 
                        (type, message_id, channel_id, guild_id, title, description, created_by_staff_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (panel_type, message.id, channel.id, guild.id, embed.title, embed.description, user_id)
                    )
                    
                    # Add rollback info for panel creation
                    create_rollback = RollbackInfo(
                        operation_type="panel_created",
                        panel_type=panel_type,
                        panel_id=panel_id,
                        guild_id=guild.id,
                        user_id=user_id
                    )
                    session.rollback_stack.append(create_rollback)

            # Log successful deployment
            await self._log_audit(
                guild,
                f"Panel Deployed: {panel_type}",
                f"**Channel:** {channel.mention}\n**Message ID:** {message.id}"
            )

            return True

        except Exception as e:
            # Clean up any sent messages if transaction failed
            for channel_id, message_id in sent_messages:
                try:
                    channel = self.bot.get_channel(channel_id)
                    if isinstance(channel, discord.TextChannel):
                        message = await channel.fetch_message(message_id)
                        await message.delete()
                except (discord.NotFound, discord.Forbidden, AttributeError):
                    pass
            
            logger.error(f"Failed to deploy {panel_type} panel: {e}")
            return False

    async def _log_audit(self, guild: discord.Guild, action: str, details: str) -> None:
        """Log setup actions to audit channel."""
        try:
            audit_channel_id = self.bot.config.logging_channels.audit
            if not audit_channel_id:
                return

            audit_channel = guild.get_channel(audit_channel_id)
            if not isinstance(audit_channel, discord.TextChannel):
                return

            embed = create_embed(
                title="🔧 Setup Action",
                description=f"**Action:** {action}\n**Details:** {details}",
                color=discord.Color.blurple(),
            )
            embed.set_footer(text="Apex Core • Setup Audit")
            await audit_channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Failed to log audit: {e}")

    def _get_panel_emoji(self, panel_type: str) -> str:
        """Get emoji for panel type."""
        emojis = {
            "products": "🛍️",
            "support": "🛟",
            "help": "❓",
            "reviews": "⭐",
        }
        return emojis.get(panel_type, "📌")

    async def _create_product_panel(self) -> tuple[discord.Embed, discord.ui.View]:
        """Create the product catalog panel."""
        from cogs.storefront import CategorySelectView

        categories = await self.bot.db.get_distinct_main_categories()

        embed = create_embed(
            title="🛍️ Apex Core: Products",
            description="Select a product from the drop-down menu to view details and open a support ticket.",
            color=discord.Color.gold(),
        )
        embed.set_footer(text="Apex Core • Storefront")

        view = CategorySelectView(categories) if categories else discord.ui.View()
        return embed, view

    async def _create_support_panel(self) -> tuple[discord.Embed, discord.ui.View]:
        """Create the support & refund buttons panel."""
        from cogs.ticket_management import TicketPanelView

        embed = create_embed(
            title="🛟 Support Options",
            description="Need help? Our support team is here to assist you!",
            color=discord.Color.blue(),
        )

        embed.add_field(
            name="🛒 General Support",
            value="Click to open a general support ticket for product questions or issues.",
            inline=False,
        )

        embed.add_field(
            name="🛡️ Refund Support",
            value="Click to request a refund for an existing order.",
            inline=False,
        )

        embed.set_footer(text="Apex Core • Support System")

        view = TicketPanelView()

        return embed, view

    async def _create_help_panel(self) -> tuple[discord.Embed, discord.ui.View]:
        """Create the help guide panel."""
        embed = create_embed(
            title="❓ How to Use Apex Core",
            description="Everything you need to know about our services.",
            color=discord.Color.green(),
        )

        embed.add_field(
            name="📖 How to Browse Products",
            value="React to the Product Catalog panel with numbers to navigate categories and view available products.",
            inline=False,
        )

        embed.add_field(
            name="💳 How to Make Purchases",
            value="Once you've selected a product, click 'Open Ticket' and follow the payment instructions.",
            inline=False,
        )

        embed.add_field(
            name="💰 How to Use Your Wallet",
            value="Use `/wallet balance` to check your balance, `/deposit` to add funds, and pay directly with your wallet balance.",
            inline=False,
        )

        embed.add_field(
            name="🎫 How to Open Tickets",
            value="Click the 'Open Ticket' button when browsing products, or use the Support Options panel.",
            inline=False,
        )

        embed.add_field(
            name="💔 How to Request Refunds",
            value="Use the 'Refund Support' button in the Support Options panel to submit a refund request.",
            inline=False,
        )

        embed.add_field(
            name="👥 How to Invite Friends",
            value="Use `/referral invite` to get your unique referral link and earn cashback from your friends' purchases!",
            inline=False,
        )

        embed.add_field(
            name="📞 Need Help?",
            value="Open a support ticket and our team will assist you within operating hours.",
            inline=False,
        )

        embed.set_footer(text="Apex Core • Help & Support")

        return embed, discord.ui.View()

    async def _create_reviews_panel(self) -> tuple[discord.Embed, discord.ui.View]:
        """Create the review system guide panel."""
        embed = create_embed(
            title="⭐ Share Your Experience",
            description="Help other customers and earn rewards!",
            color=discord.Color.gold(),
        )

        embed.add_field(
            name="📝 How to Leave a Review",
            value="Use the `/review` command in any channel to share your experience with our service.",
            inline=False,
        )

        embed.add_field(
            name="⭐ Rating System",
            value="Rate your experience from 1-5 stars (1=Poor, 5=Excellent).",
            inline=False,
        )

        embed.add_field(
            name="💬 Write Your Feedback",
            value="Provide detailed feedback between 50-1000 characters. Be honest and constructive!",
            inline=False,
        )

        embed.add_field(
            name="📸 Optional Photo Proof",
            value="Attach a screenshot or image to prove your experience (optional but recommended).",
            inline=False,
        )

        embed.add_field(
            name="🏆 Earn Rewards",
            value="Upon approval, you'll earn:\n• **@Apex Insider** role\n• **0.5% discount** on future purchases",
            inline=False,
        )

        embed.add_field(
            name="✅ What Gets Approved?",
            value="Honest, constructive reviews with clear details are more likely to be approved.",
            inline=False,
        )

        embed.add_field(
            name="📌 Guidelines",
            value="• No profanity or harassment\n• No spam or duplicate reviews\n• Be respectful to other users",
            inline=False,
        )

        embed.add_field(
            name="📢 Submit Your Review Today!",
            value="Your feedback helps us improve and helps other customers make informed decisions.",
            inline=False,
        )

        embed.set_footer(text="Apex Core • Review System")

        return embed, discord.ui.View()

    async def _deploy_panel(self, panel_type: str, channel: discord.TextChannel, 
                          guild: discord.Guild, user_id: int) -> bool:
        """Deploy a panel with atomic transaction support."""
        
        # Find existing session for this guild and user
        session_key = self._get_session_key(guild.id, user_id)
        session = self.setup_sessions.get(session_key)
        
        if not session:
            logger.error(f"No setup session found for guild {guild.id}, user {user_id}")
            return False

        try:
            # Get the panel embed and view
            if panel_type == "products":
                embed, view = await self._create_product_panel()
            elif panel_type == "support":
                embed, view = await self._create_support_panel()
            elif panel_type == "help":
                embed, view = await self._create_help_panel()
            elif panel_type == "reviews":
                embed, view = await self._create_reviews_panel()
            else:
                raise SetupOperationError(f"Unknown panel type: {panel_type}")

            # Check if this is an update to an existing panel
            existing_panel = await self.bot.db.find_panel(panel_type, guild.id)
            previous_message_id = existing_panel["message_id"] if existing_panel else None
            
            # Store sent messages for rollback cleanup
            sent_messages: list[tuple[int, int]] = []  # (channel_id, message_id)

            async with self.bot.db.transaction() as tx:
                # Send the panel message
                message = await channel.send(embed=embed, view=view)
                sent_messages.append((channel.id, message.id))
                
                # Create rollback info for message
                message_rollback = RollbackInfo(
                    operation_type="message_sent",
                    panel_type=panel_type,
                    channel_id=channel.id,
                    message_id=message.id,
                    guild_id=guild.id,
                    user_id=user_id
                )
                session.rollback_stack.append(message_rollback)

                if existing_panel:
                    # Update existing panel
                    await tx.execute(
                        """
                        UPDATE permanent_messages 
                        SET message_id = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        (message.id, existing_panel["id"])
                    )
                    
                    # Add rollback info for panel update
                    update_rollback = RollbackInfo(
                        operation_type="panel_updated",
                        panel_type=panel_type,
                        panel_id=existing_panel["id"],
                        previous_message_id=previous_message_id,
                        guild_id=guild.id,
                        user_id=user_id
                    )
                    session.rollback_stack.append(update_rollback)
                else:
                    # Create new panel record
                    panel_id = await tx.execute_insert(
                        """
                        INSERT INTO permanent_messages 
                        (type, message_id, channel_id, guild_id, title, description, created_by_staff_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (panel_type, message.id, channel.id, guild.id, embed.title, embed.description, user_id)
                    )
                    
                    # Add rollback info for panel creation
                    create_rollback = RollbackInfo(
                        operation_type="panel_created",
                        panel_type=panel_type,
                        panel_id=panel_id,
                        guild_id=guild.id,
                        user_id=user_id
                    )
                    session.rollback_stack.append(create_rollback)

            # Log successful deployment
            await self._log_audit(
                guild,
                f"Panel Deployed: {panel_type}",
                f"**Channel:** {channel.mention}\n**Message ID:** {message.id}"
            )

            return True

        except Exception as e:
            # Clean up any sent messages if transaction failed
            for channel_id, message_id in sent_messages:
                try:
                    channel = self.bot.get_channel(channel_id)
                    if isinstance(channel, discord.TextChannel):
                        message = await channel.fetch_message(message_id)
                        await message.delete()
                except (discord.NotFound, discord.Forbidden, AttributeError):
                    pass
            
            logger.error(f"Failed to deploy {panel_type} panel: {e}")
            return False

    async def _handle_setup_selection(
        self, interaction: discord.Interaction, selection: str
    ) -> None:
        """Handle setup menu selection and create setup session."""
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command must be used in a server.", ephemeral=True
            )
            return

        # Pre-compute eligible channels early to surface permission issues
        try:
            eligible_channels = await self._precompute_eligible_channels(interaction.guild)
        except SetupOperationError as e:
            await interaction.response.send_message(f"❌ {str(e)}", ephemeral=True)
            return

        # Create panel types list based on selection
        panel_types = ["products", "support", "help", "reviews"]
        if selection == "all":
            selected_panels = panel_types
        else:
            selected_panels = [selection]

        # Create setup session key
        session_key = self._get_session_key(interaction.guild.id, interaction.user.id)

        # Check for existing session and clean it up
        if session_key in self.setup_sessions:
            await self._cleanup_setup_session(
                interaction.guild.id, 
                interaction.user.id, 
                "New setup selection"
            )

        # Create new setup session with per-session lock
        session = SetupSession(
            guild_id=interaction.guild.id,
            user_id=interaction.user.id,
            panel_types=selected_panels,
            current_index=0,
            completed_panels=[],
            rollback_stack=[],
            eligible_channels=eligible_channels,
            started_at=datetime.now(timezone.utc),
            session_lock=asyncio.Lock(),
        )
        self.setup_sessions[session_key] = session

        # Show success message with eligible channels
        channels_text = "\n".join([f"• {channel.mention}" for channel in eligible_channels[:5]])
        if len(eligible_channels) > 5:
            channels_text += f"\n... and {len(eligible_channels) - 5} more channels"

        await interaction.response.send_message(
            f"✅ **Setup session started!**\n\n"
            f"**Eligible channels found:** {len(eligible_channels)}\n"
            f"{channels_text}\n\n"
            f"**Setting up:** {', '.join([p.title() for p in selected_panels])}\n\n"
            f"Now deploying **{selected_panels[0].title()}** panel...",
            ephemeral=True
        )

        # Start with the first panel deployment
        await self._start_panel_deployment(interaction, selected_panels[0], session)

    async def _start_panel_deployment(self, interaction: discord.Interaction, 
                                    panel_type: str, session: SetupSession) -> None:
        """Start panel deployment for a specific panel type."""
        # Show channel selection modal with eligible channels
        modal = ChannelInputModal(panel_type, session)
        await interaction.followup.send_modal(modal)

    async def _process_channel_input(
        self, interaction: discord.Interaction, channel_input: str, 
        panel_type: str, session: Optional[SetupSession] = None
    ) -> None:
        """Process channel input and deploy panel with comprehensive error recovery."""
        if interaction.guild is None:
            await interaction.followup.send(
                "This command must be used in a server.", ephemeral=True
            )
            return

        # Use provided session or look up by guild/user
        if session is None:
            session_key = self._get_session_key(interaction.guild.id, interaction.user.id)
            session = self.setup_sessions.get(session_key)
            
            if session is None:
                await interaction.followup.send(
                    "❌ Setup session not found. Please start setup again.",
                    ephemeral=True
                )
                return

        # Validate session state
        if session.current_index >= len(session.panel_types):
            await interaction.followup.send(
                "Setup complete!", ephemeral=True
            )
            return

        # Find the channel from user input
        channel = self._find_channel_by_input(interaction.guild, channel_input)
        if not channel:
            await interaction.followup.send(
                f"❌ Channel `{channel_input}` not found. Please try again.",
                ephemeral=True,
            )
            return

        # Check if channel is in eligible channels list
        if channel not in session.eligible_channels:
            await interaction.followup.send(
                f"❌ Channel {channel.mention} is not eligible. "
                "Bot needs 'Send Messages' and 'Embed Links' permissions.",
                ephemeral=True
            )
            return

        # Use the panel_type from the modal (ensures consistency)
        # but verify it matches what we expect
        expected_panel = session.panel_types[session.current_index]
        if panel_type != expected_panel:
            logger.warning(
                f"Panel type mismatch: modal={panel_type}, expected={expected_panel}. Using modal value."
            )

        # Deploy the panel with error handling
        try:
            success = await self._deploy_panel(
                panel_type,
                channel,
                interaction.guild,
                interaction.user.id,
            )

            if not success:
                await interaction.followup.send(
                    f"❌ Failed to deploy {panel_type} panel. Please try again.",
                    ephemeral=True,
                )
                return

            # Update session state
            session.current_index += 1
            session.completed_panels.append(panel_type)

            emoji = self._get_panel_emoji(panel_type)
            
            # Check if there are more panels to deploy
            if session.current_index < len(session.panel_types):
                next_panel = session.panel_types[session.current_index]
                next_emoji = self._get_panel_emoji(next_panel)
                
                # Send success message with button to continue
                view = ContinueSetupView(next_panel, interaction.user.id)
                await interaction.followup.send(
                    f"{emoji} ✅ Deployed to {channel.mention}\n\n"
                    f"{next_emoji} Ready to setup **{next_panel.title()} Panel** next!",
                    view=view,
                    ephemeral=True,
                )
            else:
                # All panels deployed
                await interaction.followup.send(
                    f"{emoji} ✅ Deployed to {channel.mention}\n\n"
                    "🎉 All panels deployed successfully!",
                    ephemeral=True,
                )
                # Clean up session
                await self._cleanup_setup_session(
                    session.guild_id, 
                    session.user_id, 
                    "Setup completed successfully"
                )

        except SetupOperationError as e:
            error_msg = f"❌ Failed to deploy {panel_type} panel"
            if "permission" in str(e).lower():
                error_msg += f": {str(e)}"
            else:
                error_msg += ". The operation has been rolled back."
            
            await interaction.followup.send(error_msg, ephemeral=True)
            
            # Log the error for debugging
            logger.error(f"Setup operation failed for user {interaction.user.id}: {e}")
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ An unexpected error occurred while deploying the {panel_type} panel. "
                "The operation has been rolled back.",
                ephemeral=True,
            )
            logger.error(f"Unexpected error in setup for user {interaction.user.id}: {e}")

    def _find_channel_by_input(self, guild: discord.Guild, channel_input: str) -> Optional[discord.TextChannel]:
        """Find a text channel by user input (name, mention, or ID)."""
        if channel_input.startswith("#"):
            channel_input = channel_input[1:]

        for channel in guild.text_channels:
            if (channel.name.lower() == channel_input.lower() or 
                str(channel.id) == channel_input):
                return channel
        
        return None

    async def _show_deployment_menu(
        self, interaction: discord.Interaction, panel_type_input: str
    ) -> None:
        """Show current deployments and allow management."""
        if interaction.guild is None:
            await interaction.followup.send(
                "This command must be used in a server.", ephemeral=True
            )
            return

        panel_type = panel_type_input.lower().strip()
        if panel_type not in ["products", "support", "help", "reviews"]:
            await interaction.followup.send(
                f"❌ Invalid panel type: {panel_type}\n"
                "Valid types: products, support, help, reviews",
                ephemeral=True,
            )
            return

        existing = await self.bot.db.find_panel(panel_type, interaction.guild.id)

        if existing:
            emoji = self._get_panel_emoji(panel_type)
            embed = create_embed(
                title=f"{emoji} {panel_type.title()} Panel Status",
                description=f"Deployed to <#{existing['channel_id']}> (Message ID: {existing['message_id']})",
                color=discord.Color.green(),
            )
        else:
            emoji = self._get_panel_emoji(panel_type)
            embed = create_embed(
                title=f"{emoji} {panel_type.title()} Panel",
                description="Not deployed yet.",
                color=discord.Color.orange(),
            )

        view = DeploymentSelectView(interaction.user.id)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @commands.command(name="setup")
    async def setup(self, ctx: commands.Context) -> None:
        """Interactive setup wizard for Apex Core panels."""
        if ctx.guild is None:
            await ctx.send("This command can only be used in a server.")
            return

        member = ctx.author if isinstance(ctx.author, discord.Member) else None
        if not self._is_admin(member):
            await ctx.send("Only admins can use this command.")
            return

        deployments = await self.bot.db.get_deployments(ctx.guild.id)
        panel_types = ["products", "support", "help", "reviews"]
        deployed_types = {d["type"] for d in deployments}

        embed = create_embed(
            title="🔧 Apex Core Setup Wizard",
            description="Current Deployments & Options",
            color=discord.Color.blurple(),
        )

        deployment_info = ""
        for panel_type in panel_types:
            emoji = self._get_panel_emoji(panel_type)
            if panel_type in deployed_types:
                panel = next((d for d in deployments if d["type"] == panel_type), None)
                if panel:
                    deployment_info += f"{emoji} ✅ {panel_type.title()} - <#{panel['channel_id']}> (Message ID: {panel['message_id']})\n"
            else:
                deployment_info += f"{emoji} ❌ {panel_type.title()} - Not deployed\n"

        embed.add_field(
            name="Current Status",
            value=deployment_info if deployment_info else "No panels deployed yet.",
            inline=False,
        )

        embed.add_field(
            name="What would you like to do?",
            value="1️⃣ Product Catalog Panel (storefront)\n"
                  "2️⃣ Support & Refund Buttons\n"
                  "3️⃣ Help Guide\n"
                  "4️⃣ Review System Guide\n"
                  "5️⃣ All of the above",
            inline=False,
        )
        embed.set_footer(text="Select from dropdown to continue")

        view = SetupMenuView()
        await ctx.send(embed=embed, view=view)

    @commands.command(name="setup-cleanup")
    async def setup_cleanup(self, ctx: commands.Context) -> None:
        """Clean up failed setup operations and orphaned states (Admin only)."""
        if ctx.guild is None:
            await ctx.send("This command can only be used in a server.")
            return

        member = ctx.author if isinstance(ctx.author, discord.Member) else None
        if not self._is_admin(member):
            await ctx.send("Only admins can use this command.")
            return

        embed = create_embed(
            title="🧹 Setup Cleanup Options",
            description="Select what to clean up:",
            color=discord.Color.blue(),
        )

        # Count active states
        active_states = len(self.user_states)
        embed.add_field(
            name="Active Wizard States",
            value=f"{active_states} user(s) have active setup sessions",
            inline=False,
        )

        # Check for orphaned panels
        try:
            deployments = await self.bot.db.get_deployments(ctx.guild.id)
            orphaned_count = 0
            for deployment in deployments:
                channel = ctx.guild.get_channel(deployment["channel_id"])
                if not channel:
                    orphaned_count += 1
                else:
                    try:
                        await channel.fetch_message(deployment["message_id"])
                    except discord.NotFound:
                        orphaned_count += 1

            embed.add_field(
                name="Orphaned Panels",
                value=f"{orphaned_count} panel(s) with missing channels/messages",
                inline=False,
            )
        except Exception as e:
            embed.add_field(
                name="Database Error",
                value=f"Could not check panels: {e}",
                inline=False,
            )

        view = CleanupMenuView(ctx.guild.id, ctx.author.id)
        await ctx.send(embed=embed, view=view)

    @commands.command(name="setup-status")
    async def setup_status(self, ctx: commands.Context) -> None:
        """Show current setup status and active sessions (Admin only)."""
        if ctx.guild is None:
            await ctx.send("This command can only be used in a server.")
            return

        member = ctx.author if isinstance(ctx.author, discord.Member) else None
        if not self._is_admin(member):
            await ctx.send("Only admins can use this command.")
            return

        embed = create_embed(
            title="📊 Setup Status Report",
            description="Current system status",
            color=discord.Color.green(),
        )

        # Active wizard states
        if self.user_states:
            active_sessions = []
            for user_id, state in self.user_states.items():
                user = self.bot.get_user(user_id)
                username = user.name if user else f"User {user_id}"
                
                if isinstance(state, WizardState):
                    progress = f"{state.current_index}/{len(state.panel_types)}"
                    next_panel = state.panel_types[state.current_index] if state.current_index < len(state.panel_types) else "Complete"
                    active_sessions.append(f"• {username}: {progress} (Next: {next_panel})")
                else:
                    # Legacy state format
                    current = state.get("current_index", 0)
                    total = len(state.get("panel_types", []))
                    active_sessions.append(f"• {username}: {current}/{total} (Legacy format)")

            embed.add_field(
                name="Active Setup Sessions",
                value="\n".join(active_sessions) if active_sessions else "None",
                inline=False,
            )
        else:
            embed.add_field(
                name="Active Setup Sessions",
                value="None",
                inline=False,
            )

        # Recent deployments
        try:
            deployments = await self.bot.db.get_deployments(ctx.guild.id)
            if deployments:
                deployment_info = []
                for deployment in deployments[-5:]:  # Last 5 deployments
                    channel = ctx.guild.get_channel(deployment["channel_id"])
                    channel_name = channel.name if channel else f"Deleted Channel ({deployment['channel_id']})"
                    deployment_info.append(
                        f"• {deployment['type'].title()}: {channel_name} ({deployment['message_id']})"
                    )
                
                embed.add_field(
                    name="Recent Deployments",
                    value="\n".join(deployment_info),
                    inline=False,
                )
            else:
                embed.add_field(
                    name="Recent Deployments",
                    value="No panels deployed",
                    inline=False,
                )
        except Exception as e:
            embed.add_field(
                name="Database Status",
                value=f"Error: {e}",
                inline=False,
            )

        embed.set_footer(text="Apex Core • Setup Status")
        await ctx.send(embed=embed)

    async def _handle_cleanup_selection(
        self, interaction: discord.Interaction, selection: str, guild_id: int, user_id: int
    ) -> None:
        """Handle cleanup selection with comprehensive error recovery."""
        if interaction.user.id != user_id:
            await interaction.response.send_message(
                "You can't use this menu.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        guild = self.bot.get_guild(guild_id)
        if not guild:
            await interaction.followup.send("Guild not found.", ephemeral=True)
            return

        try:
            if selection == "expired_states":
                cleaned_count = await self._cleanup_expired_states_manual()
                await interaction.followup.send(
                    f"✅ Cleaned up {cleaned_count} expired wizard states.", ephemeral=True
                )

            elif selection == "all_states":
                cleaned_count = len(self.user_states)
                for user_id in list(self.user_states.keys()):
                    await self._cleanup_wizard_state(user_id, "Manual cleanup")
                await interaction.followup.send(
                    f"✅ Cleaned up {cleaned_count} wizard states.", ephemeral=True
                )

            elif selection == "orphaned_panels":
                cleaned_count = await self._cleanup_orphaned_panels(guild)
                await interaction.followup.send(
                    f"✅ Cleaned up {cleaned_count} orphaned panels.", ephemeral=True
                )

            elif selection == "full_cleanup":
                # Clean states first
                states_cleaned = len(self.user_states)
                for user_id in list(self.user_states.keys()):
                    await self._cleanup_wizard_state(user_id, "Full cleanup")

                # Then clean orphaned panels
                panels_cleaned = await self._cleanup_orphaned_panels(guild)

                await interaction.followup.send(
                    f"✅ Full cleanup complete:\n"
                    f"• {states_cleaned} wizard states cleaned\n"
                    f"• {panels_cleaned} orphaned panels cleaned",
                    ephemeral=True,
                )

            # Log the cleanup action
            await self._log_audit(
                guild,
                f"Setup Cleanup: {selection}",
                f"**Performed by:** {interaction.user.mention}\n**Action:** {selection}",
            )

        except Exception as e:
            logger.error(f"Cleanup operation failed: {e}")
            await interaction.followup.send(
                f"❌ Cleanup failed: {e}", ephemeral=True
            )

    async def _cleanup_expired_states_manual(self) -> int:
        """Manually clean up expired wizard states and return count."""
        current_time = datetime.now(timezone.utc)
        expired_users = []

        for user_id, state in self.user_states.items():
            # Expire after 30 minutes of inactivity
            if (current_time - state.started_at).total_seconds() > 1800:
                expired_users.append(user_id)

        for user_id in expired_users:
            await self._cleanup_wizard_state(user_id, "Manual expired cleanup")

        return len(expired_users)

    async def _cleanup_orphaned_panels(self, guild: discord.Guild) -> int:
        """Clean up orphaned panels and return count."""
        try:
            deployments = await self.bot.db.get_deployments(guild.id)
            orphaned_count = 0

            for deployment in deployments:
                channel = guild.get_channel(deployment["channel_id"])
                if not channel:
                    # Channel doesn't exist, remove from database
                    await self.bot.db.remove_panel(deployment["id"])
                    orphaned_count += 1
                    logger.info(f"Removed orphaned panel {deployment['id']} - channel {deployment['channel_id']} not found")
                else:
                    try:
                        # Try to fetch the message
                        await channel.fetch_message(deployment["message_id"])
                    except discord.NotFound:
                        # Message doesn't exist, remove from database
                        await self.bot.db.remove_panel(deployment["id"])
                        orphaned_count += 1
                        logger.info(f"Removed orphaned panel {deployment['id']} - message {deployment['message_id']} not found")
                    except discord.Forbidden:
                        # No permission to access message, consider it orphaned
                        await self.bot.db.remove_panel(deployment["id"])
                        orphaned_count += 1
                        logger.warning(f"Removed orphaned panel {deployment['id']} - no permission to access message {deployment['message_id']}")

            return orphaned_count

        except Exception as e:
            logger.error(f"Failed to cleanup orphaned panels: {e}")
            raise


class CleanupMenuSelect(discord.ui.Select["CleanupMenuView"]):
    """Select menu for cleanup options."""
    
    def __init__(self) -> None:
        options = [
            discord.SelectOption(label="Clean Expired States", value="expired_states", emoji="1️⃣"),
            discord.SelectOption(label="Clean All States", value="all_states", emoji="2️⃣"),
            discord.SelectOption(label="Clean Orphaned Panels", value="orphaned_panels", emoji="3️⃣"),
            discord.SelectOption(label="Full Cleanup", value="full_cleanup", emoji="4️⃣"),
        ]
        super().__init__(
            placeholder="Select cleanup action...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        cog: SetupCog = interaction.client.get_cog("SetupCog")  # type: ignore
        if not cog:
            await interaction.response.send_message(
                "Setup cog not loaded.", ephemeral=True
            )
            return

        selection = self.values[0]
        view = self.view  # Get the parent view
        await cog._handle_cleanup_selection(interaction, selection, view.guild_id, view.user_id)


class CleanupMenuView(discord.ui.View):
    """View for cleanup menu."""
    
    def __init__(self, guild_id: int, user_id: int) -> None:
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.user_id = user_id
        self.add_item(CleanupMenuSelect())


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SetupCog(bot))
