"""Refund management and approval workflow."""

from __future__ import annotations

import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import TYPE_CHECKING, Optional

import discord
from discord import app_commands
from discord.ext import commands

from apex_core.financial_cooldown_manager import financial_cooldown
from apex_core.rate_limiter import rate_limit
from apex_core.utils import create_embed, format_usd

if TYPE_CHECKING:
    from bot import ApexCoreBot

from apex_core.logger import get_logger

logger = get_logger()


def _cents_to_usd(cents: int) -> str:
    """Convert cents to USD string with proper formatting."""
    return format_usd(Decimal(cents) / Decimal(100))


def _usd_to_cents(usd_str: str) -> int:
    """Convert USD string to cents."""
    try:
        dollars = Decimal(usd_str.replace('$', '').replace(',', '').strip())
        return int((dollars * Decimal(100)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    except (ValueError, TypeError):
        raise ValueError(f"Invalid USD amount: {usd_str}")


class RefundManagementCog(commands.Cog):
    """Refund management with user submission and staff approval workflow."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @property
    def refund_settings(self):
        """Get refund settings from config or use defaults."""
        if hasattr(self.bot, 'config') and self.bot.config.refund_settings:
            return self.bot.config.refund_settings
        # Default settings if not configured
        from apex_core.config import RefundSettings
        return RefundSettings(enabled=True, max_days=3, handling_fee_percent=10.0)

    # region Helpers
    def _is_admin(self, member: discord.Member | None) -> bool:
        """Check if user has admin role."""
        if member is None:
            return False
        admin_role_id = self.bot.config.role_ids.admin
        return any(role.id == admin_role_id for role in getattr(member, "roles", []))

    def _resolve_member(self, interaction: discord.Interaction) -> discord.Member | None:
        """Resolve member from interaction."""
        if isinstance(interaction.user, discord.Member):
            return interaction.user
        if interaction.guild:
            return interaction.guild.get_member(interaction.user.id)
        return None

    async def _send_audit_log(self, guild: discord.Guild, embed: discord.Embed) -> None:
        """Send embed to audit channel."""
        audit_channel_id = self.bot.config.logging_channels.audit
        audit_channel = guild.get_channel(audit_channel_id)
        if isinstance(audit_channel, discord.TextChannel):
            try:
                await audit_channel.send(embed=embed)
            except discord.HTTPException as e:
                logger.warning("Failed to send audit log: %s", e)

    async def _send_dm_confirmation(self, user: discord.User, embed: discord.Embed) -> None:
        """Send DM confirmation to user."""
        try:
            await user.send(embed=embed)
        except discord.HTTPException as e:
            logger.warning("Failed to send DM to user %s: %s", user.id, e)

    # endregion

    # region User Commands
    @app_commands.command(name="submitrefund", description="Submit a refund request")
    @app_commands.describe(
        order_id="The order ID to refund",
        amount="Requested refund amount in USD",
        reason="Detailed reason for refund request",
    )
    @rate_limit(cooldown=3600, max_uses=1, per="user", config_key="submitrefund")
    @financial_cooldown()
    async def submitrefund(
        self,
        interaction: discord.Interaction,
        order_id: str,
        amount: str,
        reason: str,
    ) -> None:
        """Submit a refund request for an order."""
        logger.info(
            "Command: /submitrefund | Order: %s | Amount: %s | User: %s (%s) | Guild: %s | Reason: %s",
            order_id,
            amount,
            interaction.user.name,
            interaction.user.id,
            interaction.guild_id,
            reason[:100],  # First 100 chars
        )
        
        if not self.refund_settings.enabled:
            logger.warning("Refund system disabled | User: %s attempted submitrefund", interaction.user.id)
            await interaction.response.send_message(
                "Refund system is currently disabled.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            order_id_int = int(order_id)
            amount_cents = _usd_to_cents(amount)
            logger.debug("Parsed refund request | Order: %s | Amount: %s cents | User: %s", order_id_int, amount_cents, interaction.user.id)
        except ValueError as e:
            logger.warning("Invalid refund input | Order: %s | Amount: %s | User: %s | Error: %s", order_id, amount, interaction.user.id, str(e))
            await interaction.followup.send(
                f"Invalid input: {e}",
                ephemeral=True
            )
            return

        # Validate order belongs to user and is within refund window
        logger.debug("Validating order for refund | Order: %s | User: %s | Max days: %s", order_id_int, interaction.user.id, self.refund_settings.max_days)
        order = await self.bot.db.validate_order_for_refund(
            order_id_int,
            interaction.user.id,
            self.refund_settings.max_days,
        )

        if not order:
            logger.warning(
                "Order not eligible for refund | Order: %s | User: %s | Max days: %s",
                order_id_int,
                interaction.user.id,
                self.refund_settings.max_days,
            )
            await interaction.followup.send(
                f"Order #{order_id} not found, not eligible for refund, or outside the {self.refund_settings.max_days}-day window. "
                "Only fulfilled or refill orders within the refund period are eligible.",
                ephemeral=True
            )
            return
        
        logger.debug("Order validated for refund | Order: %s | User: %s", order_id_int, interaction.user.id)

        # Create refund request
        try:
            logger.info(
                "Creating refund request | Order: %s | User: %s | Amount: %s cents | Handling fee: %s%%",
                order_id_int,
                interaction.user.id,
                amount_cents,
                self.refund_settings.handling_fee_percent,
            )
            refund_id = await self.bot.db.create_refund_request(
                order_id=order_id_int,
                user_discord_id=interaction.user.id,
                amount_cents=amount_cents,
                reason=reason,
                handling_fee_percent=self.refund_settings.handling_fee_percent,
            )
            logger.info("Refund request created | Refund ID: %s | Order: %s | User: %s", refund_id, order_id_int, interaction.user.id)

            # Get refund details for confirmation
            refund = await self.bot.db.get_refund_by_id(refund_id)
            if not refund:
                logger.error("Failed to retrieve created refund | Refund ID: %s | User: %s", refund_id, interaction.user.id)
                raise RuntimeError("Failed to retrieve created refund")

            # Send confirmation to user
            embed = create_embed(
                title="🛡️ Refund Request Submitted",
                description=f"Your refund request has been submitted and is pending review.",
                color=discord.Color.orange(),
                timestamp=True,
            )
            embed.add_field(name="Reference ID", value=f"#{refund_id}", inline=True)
            embed.add_field(name="Order ID", value=f"#{order_id}", inline=True)
            embed.add_field(name="Status", value="Pending Review", inline=True)
            embed.add_field(
                name="Requested Amount",
                value=_cents_to_usd(refund["requested_amount_cents"]),
                inline=True,
            )
            embed.add_field(
                name="Handling Fee (10%)",
                value=_cents_to_usd(refund["handling_fee_cents"]),
                inline=True,
            )
            embed.add_field(
                name="Final Refund Amount",
                value=_cents_to_usd(refund["final_refund_cents"]),
                inline=True,
            )
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.set_footer(text="You will be notified when your request is reviewed.")

            await self._send_dm_confirmation(interaction.user, embed)

            # Notify staff in tickets channel
            tickets_channel_id = self.bot.config.logging_channels.tickets
            if interaction.guild:
                tickets_channel = interaction.guild.get_channel(tickets_channel_id)
                if isinstance(tickets_channel, discord.TextChannel):
                    staff_embed = create_embed(
                        title="🛡️ New Refund Request",
                        description=f"User {interaction.user.mention} has submitted a refund request.",
                        color=discord.Color.orange(),
                        timestamp=True,
                    )
                    staff_embed.add_field(name="Refund ID", value=f"#{refund_id}", inline=True)
                    staff_embed.add_field(name="Order ID", value=f"#{order_id}", inline=True)
                    staff_embed.add_field(name="User", value=interaction.user.mention, inline=True)
                    staff_embed.add_field(
                        name="Requested Amount",
                        value=_cents_to_usd(refund["requested_amount_cents"]),
                        inline=True,
                    )
                    staff_embed.add_field(
                        name="Final Refund",
                        value=_cents_to_usd(refund["final_refund_cents"]),
                        inline=True,
                    )
                    staff_embed.add_field(name="Reason", value=reason, inline=False)

                    admin_role_id = self.bot.config.role_ids.admin
                    admin_role = interaction.guild.get_role(admin_role_id)
                    content = f"{admin_role.mention}" if admin_role else ""

                    await tickets_channel.send(content=content, embed=staff_embed)

            await interaction.followup.send(
                f"✅ Refund request submitted! Reference ID: #{refund_id}\n"
                f"You will receive a DM with confirmation details.",
                ephemeral=True
            )

            logger.info(
                "Refund request #%s submitted by user %s for order %s (amount: %s)",
                refund_id, interaction.user.id, order_id, _cents_to_usd(amount_cents)
            )

        except Exception as e:
            logger.error("Failed to create refund request: %s", e)
            await interaction.followup.send(
                "Failed to submit refund request. Please try again later.",
                ephemeral=True
            )

    # endregion

    # region Staff Commands
    @commands.command(name="refund-approve", aliases=["refund_approve"])
    @commands.has_permissions(administrator=True)
    @rate_limit(cooldown=60, max_uses=10, per="user", config_key="refund_approve", admin_bypass=False)
    @financial_cooldown()
    async def refund_approve(
        self,
        ctx: commands.Context,
        user: discord.User,
        order_id: int,
        amount: str,
        *,
        reason: str = "Approved by staff"
    ) -> None:
        """Approve a refund request and credit user wallet.
        
        Usage: !refund-approve @user order_id amount [reason]
        """
        logger.info(
            "Command: !refund-approve | User: %s | Order: %s | Amount: %s | Staff: %s",
            user.id, order_id, amount, ctx.author.id
        )
        if not self.refund_settings.enabled:
            await ctx.send("Refund system is currently disabled.")
            return

        await ctx.trigger_typing()

        try:
            amount_cents = _usd_to_cents(amount)
        except ValueError as e:
            await ctx.send(f"Invalid amount: {e}")
            return

        # Find pending refund for this user and order
        user_refunds = await self.bot.db.get_user_refunds(user.id, status="pending")
        target_refund = None
        for refund in user_refunds:
            if refund["order_id"] == order_id:
                target_refund = refund
                break

        if not target_refund:
            await ctx.send(
                f"No pending refund request found for user {user.mention} and order #{order_id}."
            )
            return

        try:
            # Approve the refund
            await self.bot.db.approve_refund(
                refund_id=target_refund["id"],
                staff_discord_id=ctx.author.id,
                approved_amount_cents=amount_cents,
                handling_fee_percent=self.refund_settings.handling_fee_percent,
            )

            # Get updated refund details
            approved_refund = await self.bot.db.get_refund_by_id(target_refund["id"])
            if not approved_refund:
                raise RuntimeError("Failed to retrieve approved refund")

            # Send confirmation DM to user
            user_embed = create_embed(
                title="✅ Refund Approved",
                description="Your refund request has been approved and credited to your wallet.",
                color=discord.Color.green(),
                timestamp=True,
            )
            user_embed.add_field(
                name="Original Amount",
                value=_cents_to_usd(approved_refund["requested_amount_cents"]),
                inline=True,
            )
            user_embed.add_field(
                name="Handling Fee (10%)",
                value=_cents_to_usd(approved_refund["handling_fee_cents"]),
                inline=True,
            )
            user_embed.add_field(
                name="Final Amount",
                value=_cents_to_usd(approved_refund["final_refund_cents"]),
                inline=True,
            )
            user_embed.add_field(
                name="Refunded to wallet",
                value=f"On {approved_refund['resolved_at'].split()[0] if approved_refund['resolved_at'] else 'today'}",
                inline=False,
            )
            user_embed.set_footer(text="Thank you for your patience!")

            await self._send_dm_confirmation(user, user_embed)

            # Send audit log
            audit_embed = create_embed(
                title="✅ Refund Approved",
                description=f"Refund request approved by {ctx.author.mention}",
                color=discord.Color.green(),
                timestamp=True,
            )
            audit_embed.add_field(name="Refund ID", value=f"#{approved_refund['id']}", inline=True)
            audit_embed.add_field(name="Order ID", value=f"#{order_id}", inline=True)
            audit_embed.add_field(name="User", value=user.mention, inline=True)
            audit_embed.add_field(
                name="Approved Amount",
                value=_cents_to_usd(approved_refund["final_refund_cents"]),
                inline=True,
            )
            audit_embed.add_field(name="Approved By", value=ctx.author.mention, inline=True)
            audit_embed.add_field(name="Reason", value=reason, inline=False)

            await self._send_audit_log(ctx.guild, audit_embed)

            await ctx.send(
                f"✅ Refund approved for {user.mention}! "
                f"Amount {_cents_to_usd(approved_refund['final_refund_cents'])} credited to wallet."
            )

            logger.info(
                "Refund #%s approved by staff %s for user %s (amount: %s)",
                approved_refund['id'], ctx.author.id, user.id,
                _cents_to_usd(approved_refund['final_refund_cents'])
            )

        except ValueError as e:
            await ctx.send(f"Error approving refund: {e}")
        except Exception as e:
            logger.error("Failed to approve refund: %s", e)
            await ctx.send("Failed to approve refund. Please check the logs.")

    @commands.command(name="refund-reject", aliases=["refund_reject"])
    @commands.has_permissions(administrator=True)
    @financial_cooldown()
    async def refund_reject(
        self,
        ctx: commands.Context,
        user: discord.User,
        order_id: int,
        *,
        reason: str
    ) -> None:
        """Reject a refund request.
        
        Usage: !refund-reject @user order_id reason
        """
        logger.info(
            "Command: !refund-reject | User: %s | Order: %s | Staff: %s | Reason: %s",
            user.id, order_id, ctx.author.id, reason
        )
        if not self.refund_settings.enabled:
            await ctx.send("Refund system is currently disabled.")
            return

        await ctx.trigger_typing()

        # Find pending refund for this user and order
        user_refunds = await self.bot.db.get_user_refunds(user.id, status="pending")
        target_refund = None
        for refund in user_refunds:
            if refund["order_id"] == order_id:
                target_refund = refund
                break

        if not target_refund:
            await ctx.send(
                f"No pending refund request found for user {user.mention} and order #{order_id}."
            )
            return

        try:
            # Reject the refund
            await self.bot.db.reject_refund(
                refund_id=target_refund["id"],
                staff_discord_id=ctx.author.id,
                rejection_reason=reason,
            )

            # Send rejection DM to user
            user_embed = create_embed(
                title="❌ Refund Request Rejected",
                description="Your refund request has been reviewed and rejected.",
                color=discord.Color.red(),
                timestamp=True,
            )
            user_embed.add_field(name="Order ID", value=f"#{order_id}", inline=True)
            user_embed.add_field(name="Rejection Reason", value=reason, inline=False)
            user_embed.set_footer(text="If you have questions, please open a support ticket.")

            await self._send_dm_confirmation(user, user_embed)

            # Send audit log
            audit_embed = create_embed(
                title="❌ Refund Rejected",
                description=f"Refund request rejected by {ctx.author.mention}",
                color=discord.Color.red(),
                timestamp=True,
            )
            audit_embed.add_field(name="Refund ID", value=f"#{target_refund['id']}", inline=True)
            audit_embed.add_field(name="Order ID", value=f"#{order_id}", inline=True)
            audit_embed.add_field(name="User", value=user.mention, inline=True)
            audit_embed.add_field(name="Rejected By", value=ctx.author.mention, inline=True)
            audit_embed.add_field(name="Rejection Reason", value=reason, inline=False)

            await self._send_audit_log(ctx.guild, audit_embed)

            await ctx.send(
                f"❌ Refund rejected for {user.mention}. User has been notified."
            )

            logger.info(
                "Refund #%s rejected by staff %s for user %s (reason: %s)",
                target_refund['id'], ctx.author.id, user.id, reason
            )

        except Exception as e:
            logger.error("Failed to reject refund: %s", e)
            await ctx.send("Failed to reject refund. Please check the logs.")

    @commands.command(name="pending-refunds", aliases=["pending_refunds"])
    @commands.has_permissions(administrator=True)
    async def pending_refunds(self, ctx: commands.Context) -> None:
        """Show all pending refund requests."""
        if not self.refund_settings.enabled:
            await ctx.send("Refund system is currently disabled.")
            return

        await ctx.trigger_typing()

        try:
            pending_refunds = await self.bot.db.get_pending_refunds()

            if not pending_refunds:
                await ctx.send("No pending refund requests found.")
                return

            embed = create_embed(
                title="🛡️ Pending Refund Requests",
                description=f"Found {len(pending_refunds)} pending refund request(s).",
                color=discord.Color.orange(),
                timestamp=True,
            )

            for refund in pending_refunds[:10]:  # Show max 10 to avoid embed size limits
                user = ctx.bot.get_user(refund["user_discord_id"])
                user_mention = user.mention if user else f"<@{refund['user_discord_id']}>"
                
                value = (
                    f"**User:** {user_mention}\n"
                    f"**Amount:** {_cents_to_usd(refund['requested_amount_cents'])} "
                    f"→ {_cents_to_usd(refund['final_refund_cents'])}\n"
                    f"**Reason:** {refund['reason'][:100]}{'...' if len(refund['reason']) > 100 else ''}"
                )
                
                embed.add_field(
                    name=f"Refund #{refund['id']} - Order #{refund['order_id']}",
                    value=value,
                    inline=False,
                )

            if len(pending_refunds) > 10:
                embed.set_footer(text=f"Showing 10 of {len(pending_refunds)} pending requests")

            await ctx.send(embed=embed)

        except Exception as e:
            logger.error("Failed to fetch pending refunds: %s", e)
            await ctx.send("Failed to fetch pending refunds. Please check the logs.")

    # endregion

    # region Error Handlers
    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        """Handle application command errors."""
        if isinstance(error, app_commands.CommandOnCooldown):
            await interaction.response.send_message(
                f"This command is on cooldown. Try again in {error.retry_after:.1f} seconds.",
                ephemeral=True,
            )
        else:
            logger.error("Refund command error: %s", error)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "An error occurred while processing your request.",
                    ephemeral=True,
                )

    async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        """Handle command errors."""
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("You don't have permission to use this command.")
        elif isinstance(error, commands.UserNotFound):
            await ctx.send("User not found.")
        else:
            logger.error("Refund command error: %s", error)
            await ctx.send("An error occurred while processing your command.")

    # endregion


async def setup(bot: commands.Bot) -> None:
    """Setup the RefundManagementCog."""
    await bot.add_cog(RefundManagementCog(bot))