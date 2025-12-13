from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from apex_core.financial_cooldown_manager import financial_cooldown
from apex_core.rate_limiter import rate_limit
from apex_core.utils import create_embed, format_usd

from apex_core.logger import get_logger

logger = get_logger()


class ReferralsCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def _is_admin(self, member: discord.Member | None) -> bool:
        if member is None:
            return False
        admin_role_id = self.bot.config.role_ids.admin
        return any(role.id == admin_role_id for role in getattr(member, "roles", []))

    def _resolve_member(self, interaction: discord.Interaction) -> discord.Member | None:
        if isinstance(interaction.user, discord.Member):
            return interaction.user
        if interaction.guild:
            return interaction.guild.get_member(interaction.user.id)
        return None

    @app_commands.command(name="invite", description="Get your referral link and earn cashback on referrals.")
    async def invite(self, interaction: discord.Interaction) -> None:
        logger.info("Command: /invite | User: %s", interaction.user.id)
        await interaction.response.defer(ephemeral=True, thinking=True)

        user_id = interaction.user.id

        try:
            stats = await self.bot.db.get_referral_stats(user_id)

            embed = create_embed(
                title="🎁 Your Referral Program",
                description=(
                    "Earn 0.5% cashback on all purchases made by users you refer!\n\n"
                    f"**Your Referral Code:** `{user_id}`\n\n"
                    "**How it works:**\n"
                    "1. Share your referral code with friends\n"
                    "2. They use `/setref {your_code}` when they join\n"
                    "3. You earn 0.5% cashback on their purchases\n"
                    "4. Cashback accumulates and can be paid out by staff"
                ),
                color=discord.Color.gold(),
            )

            embed.add_field(
                name="📊 Your Stats",
                value=(
                    f"**Total Invited:** {stats['referral_count']} users\n"
                    f"**Total Referred Spend:** {format_usd(stats['total_spend_cents'])}\n"
                    f"**Total Cashback Earned:** {format_usd(stats['total_earned_cents'])}\n"
                    f"**Pending Cashback:** {format_usd(stats['pending_cents'])}"
                ),
                inline=False,
            )

            embed.set_footer(text="Apex Core • Referral Program")

            await interaction.followup.send(embed=embed, ephemeral=True)

            try:
                dm_embed = create_embed(
                    title="🎁 Your Referral Link",
                    description=(
                        f"Your referral code is: `{user_id}`\n\n"
                        "Share this code with friends! They can use `/setref {your_code}` "
                        "to link their account to you.\n\n"
                        "**You earn 0.5% cashback on all their purchases!**"
                    ),
                    color=discord.Color.gold(),
                )
                dm_embed.set_footer(text="Apex Core • Referral Program")
                await interaction.user.send(embed=dm_embed)
            except discord.Forbidden:
                pass

        except Exception as e:
            logger.error(f"Error in invite command: {e}", exc_info=True)
            await interaction.followup.send(
                "An error occurred while fetching your referral information.",
                ephemeral=True,
            )

    @app_commands.command(name="profile", description="View your profile including referral stats.")
    @rate_limit(cooldown=60, max_uses=5, per="user", config_key="profile")
    async def profile(self, interaction: discord.Interaction, member: Optional[discord.Member] = None) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)

        target = member or interaction.user
        if member:
            requester = self._resolve_member(interaction)
            if not self._is_admin(requester):
                await interaction.followup.send(
                    "Only admins can view other members' profiles.",
                    ephemeral=True,
                )
                return

        try:
            user_row = await self.bot.db.get_user(target.id)
            if not user_row:
                await interaction.followup.send(
                    f"No profile found for {target.mention}.",
                    ephemeral=True,
                )
                return

            stats = await self.bot.db.get_referral_stats(target.id)
            order_count = await self.bot.db.count_orders_for_user(target.id)

            embed = create_embed(
                title=f"👤 Profile • {target.display_name}",
                description=f"User ID: {target.id}",
                color=discord.Color.blue(),
            )

            embed.add_field(
                name="💰 Wallet & Spending",
                value=(
                    f"**Balance:** {format_usd(user_row['wallet_balance_cents'])}\n"
                    f"**Lifetime Spent:** {format_usd(user_row['total_lifetime_spent_cents'])}\n"
                    f"**Total Orders:** {order_count}"
                ),
                inline=False,
            )

            embed.add_field(
                name="🎁 Referral Stats",
                value=(
                    f"**Total Referrals:** {stats['referral_count']} users\n"
                    f"**Referred Spend:** {format_usd(stats['total_spend_cents'])}\n"
                    f"**Cashback Earned:** {format_usd(stats['total_earned_cents'])}\n"
                    f"**Cashback Paid Out:** {format_usd(stats['total_paid_cents'])}\n"
                    f"**Pending Cashback:** {format_usd(stats['pending_cents'])}"
                ),
                inline=False,
            )

            embed.add_field(
                name="📅 Account Info",
                value=(
                    f"**Joined:** {target.created_at.strftime('%Y-%m-%d')}\n"
                    f"**First Purchase:** {user_row['created_at']}"
                ),
                inline=False,
            )

            embed.set_footer(text="Apex Core • User Profile")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in profile command: {e}", exc_info=True)
            await interaction.followup.send(
                "An error occurred while fetching profile information.",
                ephemeral=True,
            )

    @app_commands.command(name="invites", description="View detailed statistics about your referrals.")
    @rate_limit(cooldown=60, max_uses=3, per="user", config_key="invites")
    @financial_cooldown()
    async def invites(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)

        user_id = interaction.user.id

        try:
            stats = await self.bot.db.get_referral_stats(user_id)
            referrals = await self.bot.db.get_referrals(user_id)

            embed = create_embed(
                title="📊 Your Referral Stats",
                description=f"Detailed breakdown of your referral earnings.",
                color=discord.Color.blue(),
            )

            embed.add_field(
                name="Summary",
                value=(
                    f"**Total Invited:** {stats['referral_count']} users\n"
                    f"**Total Referred Spend:** {format_usd(stats['total_spend_cents'])}\n"
                    f"**Total Cashback Earned:** {format_usd(stats['total_earned_cents'])}\n"
                    f"**Cashback Paid Out:** {format_usd(stats['total_paid_cents'])}\n"
                    f"**Pending Cashback:** {format_usd(stats['pending_cents'])}"
                ),
                inline=False,
            )

            if referrals:
                referral_list = []
                for i, ref in enumerate(referrals[:10], 1):
                    if ref["is_blacklisted"]:
                        status = "🚫 Blacklisted"
                    else:
                        status = "✅ Active"
                    
                    referral_list.append(
                        f"{i}. <@{ref['referred_user_id']}> - "
                        f"{format_usd(ref['referred_total_spend_cents'])} spent - "
                        f"{format_usd(ref['cashback_earned_cents'])} earned - {status}"
                    )
                
                if len(referrals) > 10:
                    referral_list.append(f"... and {len(referrals) - 10} more")
                
                embed.add_field(
                    name=f"Your Referrals ({len(referrals)} total)",
                    value="\n".join(referral_list),
                    inline=False,
                )
            else:
                embed.add_field(
                    name="Your Referrals",
                    value="You haven't referred anyone yet. Share your referral code with friends!",
                    inline=False,
                )

            embed.set_footer(text="Apex Core • Referral Program")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in invites command: {e}", exc_info=True)
            await interaction.followup.send(
                "An error occurred while fetching your referral statistics.",
                ephemeral=True,
            )

    @app_commands.command(name="setref", description="Set your referrer to earn them cashback on your purchases.")
    @app_commands.describe(referrer_code="The referral code from the person who invited you")
    @rate_limit(cooldown=86400, max_uses=1, per="user", config_key="setref")
    @financial_cooldown()
    async def setref(self, interaction: discord.Interaction, referrer_code: str) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)

        user_id = interaction.user.id

        try:
            referrer_id = int(referrer_code.strip())
        except ValueError:
            await interaction.followup.send(
                "Invalid referral code. Please provide a valid numeric code.",
                ephemeral=True,
            )
            return

        if referrer_id == user_id:
            await interaction.followup.send(
                "You cannot refer yourself!",
                ephemeral=True,
            )
            return

        try:
            existing_referrer = await self.bot.db.get_referrer_for_user(user_id)
            if existing_referrer:
                await interaction.followup.send(
                    f"You have already been referred by <@{existing_referrer}>. "
                    "Each user can only be referred once.",
                    ephemeral=True,
                )
                return

            if interaction.guild:
                referrer_member = interaction.guild.get_member(referrer_id)
                if not referrer_member:
                    await interaction.followup.send(
                        "The referrer must be a member of this server.",
                        ephemeral=True,
                    )
                    return

            await self.bot.db.create_referral(referrer_id, user_id)

            embed = create_embed(
                title="✅ Referral Link Created",
                description=(
                    f"You have been successfully referred by <@{referrer_id}>!\n\n"
                    "They will earn 0.5% cashback on all your purchases. "
                    "Thank you for supporting them!"
                ),
                color=discord.Color.green(),
            )
            embed.set_footer(text="Apex Core • Referral Program")

            await interaction.followup.send(embed=embed, ephemeral=True)

            try:
                referrer_user = await self.bot.fetch_user(referrer_id)
                if referrer_user:
                    dm_embed = create_embed(
                        title="🎉 New Referral!",
                        description=(
                            f"{interaction.user.mention} ({interaction.user.name}) has joined using your referral code!\n\n"
                            "You will now earn 0.5% cashback on all their purchases."
                        ),
                        color=discord.Color.gold(),
                    )
                    dm_embed.set_footer(text="Apex Core • Referral Program")
                    await referrer_user.send(embed=dm_embed)
            except (discord.Forbidden, discord.NotFound):
                pass

            try:
                referred_dm_embed = create_embed(
                    title="✅ Referral Confirmed",
                    description=(
                        f"You were invited by {referrer_user.name if referrer_user else f'User {referrer_id}'}!\n\n"
                        "They will earn 0.5% cashback on your purchases. "
                        "Enjoy shopping at Apex Core!"
                    ),
                    color=discord.Color.green(),
                )
                referred_dm_embed.set_footer(text="Apex Core • Referral Program")
                await interaction.user.send(embed=referred_dm_embed)
            except discord.Forbidden:
                pass

        except RuntimeError as e:
            await interaction.followup.send(str(e), ephemeral=True)
        except Exception as e:
            logger.error(f"Error in setref command: {e}", exc_info=True)
            await interaction.followup.send(
                "An error occurred while setting your referrer.",
                ephemeral=True,
            )

    @commands.command(name="referral-blacklist", aliases=["refund-blacklist"])
    async def blacklist_referral(self, ctx: commands.Context, user: discord.Member) -> None:
        if not ctx.guild:
            return

        requester = ctx.author if isinstance(ctx.author, discord.Member) else None
        if not self._is_admin(requester):
            await ctx.send("❌ You do not have permission to use this command.")
            return

        try:
            success = await self.bot.db.blacklist_referral_user(user.id)

            if success:
                embed = create_embed(
                    title="🚫 User Blacklisted",
                    description=(
                        f"**User:** {user.mention} ({user.id})\n"
                        f"**Action:** All referral earnings have been marked as blacklisted.\n\n"
                        "This user can still use the store but will no longer earn referral cashback."
                    ),
                    color=discord.Color.red(),
                )
                embed.set_footer(text="Apex Core • Referral Management")
                await ctx.send(embed=embed)

                try:
                    dm_embed = create_embed(
                        title="⚠️ Referral Program Suspension",
                        description=(
                            "Your referral program access has been suspended due to policy violations.\n\n"
                            "You can still use the store, but you will no longer earn referral cashback.\n"
                            "Contact staff if you have questions."
                        ),
                        color=discord.Color.orange(),
                    )
                    dm_embed.set_footer(text="Apex Core • Referral Management")
                    await user.send(embed=dm_embed)
                except discord.Forbidden:
                    pass
            else:
                await ctx.send(f"❌ No referral records found for {user.mention}.")

        except Exception as e:
            logger.error(f"Error blacklisting user {user.id}: {e}", exc_info=True)
            await ctx.send("❌ An error occurred while blacklisting the user.")

    @commands.command(name="sendref-cashb")
    async def send_referral_cashback(
        self, ctx: commands.Context, user: Optional[discord.Member] = None
    ) -> None:
        """Process and payout referral cashback to eligible referrers.
        
        Usage:
            !sendref-cashb - Process all pending cashback (batch mode)
            !sendref-cashb @user - Process cashback for specific user only
        """
        if not ctx.guild:
            return

        requester = ctx.author if isinstance(ctx.author, discord.Member) else None
        if not self._is_admin(requester):
            await ctx.send("❌ You do not have permission to use this command.")
            return

        try:
            # Single user mode
            if user:
                await self._process_individual_cashback(ctx, user)
            # Batch mode
            else:
                await self._process_batch_cashback(ctx)

        except Exception as e:
            logger.error(f"Error in send_referral_cashback command: {e}", exc_info=True)
            await ctx.send("❌ An error occurred while processing referral cashback.")

    async def _process_individual_cashback(
        self, ctx: commands.Context, user: discord.Member
    ) -> None:
        """Process cashback for a single user."""
        try:
            # Get pending cashback for this user
            pending_data = await self.bot.db.get_pending_cashback_for_user(user.id)
            
            if pending_data["is_blacklisted"]:
                await ctx.send(f"❌ {user.mention} is blacklisted from earning referral cashback.")
                return
            
            if pending_data["pending_cents"] <= 0:
                await ctx.send(f"❌ {user.mention} has no pending cashback to process.")
                return
            
            # Create confirmation embed
            embed = create_embed(
                title="💰 Individual Referral Cashback Payout",
                description=f"Ready to process cashback for {user.mention}",
                color=discord.Color.gold(),
            )
            
            embed.add_field(
                name="Payment Details",
                value=(
                    f"**User:** {user.mention}\n"
                    f"**Amount:** {format_usd(pending_data['pending_cents'])}\n"
                    f"**Active Referrals:** {pending_data['referral_count']}"
                ),
                inline=False,
            )
            
            embed.set_footer(text="Click Confirm to process this payout")
            
            # Create confirmation view
            view = CashbackConfirmView(self, ctx, [pending_data["pending_cents"]], user.id)
            message = await ctx.send(embed=embed, view=view)
            view.message = message

        except Exception as e:
            logger.error(f"Error processing individual cashback for {user.id}: {e}", exc_info=True)
            await ctx.send("❌ An error occurred while processing individual cashback.")

    async def _process_batch_cashback(self, ctx: commands.Context) -> None:
        """Process cashback for all eligible referrers."""
        try:
            # Get all pending cashbacks
            pending_list = await self.bot.db.get_all_pending_referral_cashbacks()
            
            if not pending_list:
                embed = create_embed(
                    title="💰 Referral Cashback Batch",
                    description="No pending cashback to process at this time.",
                    color=discord.Color.blue(),
                )
                await ctx.send(embed=embed)
                return
            
            # Calculate totals
            total_users = len(pending_list)
            total_amount_cents = sum(p["pending_cents"] for p in pending_list)
            
            # Create summary embed
            embed = create_embed(
                title="💰 Referral Cashback Batch Summary",
                description="Ready to process pending referral cashback payouts",
                color=discord.Color.gold(),
            )
            
            embed.add_field(
                name="📊 Batch Statistics",
                value=(
                    f"**Users Receiving Payment:** {total_users}\n"
                    f"**Total Amount:** {format_usd(total_amount_cents)}\n"
                    f"**Average Per User:** {format_usd(total_amount_cents // total_users if total_users > 0 else 0)}"
                ),
                inline=False,
            )
            
            # Show top 10 payouts
            top_payouts = sorted(pending_list, key=lambda x: x["pending_cents"], reverse=True)[:10]
            top_list = []
            for i, p in enumerate(top_payouts, 1):
                top_list.append(
                    f"{i}. <@{p['referrer_id']}> - {format_usd(p['pending_cents'])} "
                    f"({p['referral_count']} referrals)"
                )
            
            embed.add_field(
                name="🏆 Top Payouts",
                value="\n".join(top_list) if top_list else "None",
                inline=False,
            )
            
            if len(pending_list) > 10:
                embed.add_field(
                    name="📋 Additional Payouts",
                    value=f"... and {len(pending_list) - 10} more users",
                    inline=False,
                )
            
            embed.set_footer(text="Click Confirm to process all payouts • This action cannot be undone")
            
            # Create confirmation view
            view = CashbackConfirmView(self, ctx, [p["pending_cents"] for p in pending_list])
            message = await ctx.send(embed=embed, view=view)
            view.message = message

        except Exception as e:
            logger.error(f"Error processing batch cashback: {e}", exc_info=True)
            await ctx.send("❌ An error occurred while processing batch cashback.")

    async def _execute_cashback_payout(
        self, pending_list: list[dict], batch_id: str
    ) -> dict:
        """Execute the actual cashback payout for all users.
        
        Returns:
            Dict with results: successful_count, failed_count, total_amount_cents, failed_users
        """
        successful_count = 0
        failed_count = 0
        total_paid_cents = 0
        failed_users = []
        
        for payout in pending_list:
            referrer_id = payout["referrer_id"]
            amount_cents = payout["pending_cents"]
            referral_count = payout["referral_count"]
            
            try:
                # Ensure user exists and has wallet
                await self.bot.db.ensure_user(referrer_id)
                
                # Credit wallet
                new_balance = await self.bot.db.update_wallet_balance(
                    referrer_id, amount_cents
                )
                
                # Create wallet transaction
                metadata = json.dumps({
                    "batch_id": batch_id,
                    "referral_count": referral_count,
                })
                
                await self.bot.db.log_wallet_transaction(
                    user_discord_id=referrer_id,
                    amount_cents=amount_cents,
                    balance_after_cents=new_balance,
                    transaction_type="referral_cashback",
                    description=f"Referral cashback - {referral_count} active referrals",
                    metadata=metadata,
                )
                
                # Mark cashback as paid in referrals table
                await self.bot.db.mark_cashback_paid(referrer_id, amount_cents)
                
                # Send DM to user
                try:
                    user = await self.bot.fetch_user(referrer_id)
                    if user:
                        dm_embed = create_embed(
                            title="💰 Referral Cashback Received!",
                            description=(
                                "Your referral cashback has been paid out!\n\n"
                                f"**Amount Credited:** {format_usd(amount_cents)}\n"
                                f"**From Referrals:** {referral_count} users\n"
                                f"**New Wallet Balance:** {format_usd(new_balance)}\n\n"
                                "Thank you for helping grow our community! 🎉"
                            ),
                            color=discord.Color.green(),
                        )
                        dm_embed.set_footer(text=f"Apex Core • Batch ID: {batch_id}")
                        await user.send(embed=dm_embed)
                except (discord.Forbidden, discord.NotFound):
                    logger.info(f"Could not DM user {referrer_id} about cashback payout")
                
                successful_count += 1
                total_paid_cents += amount_cents
                
                logger.info(
                    f"Referral cashback paid: {amount_cents} cents to user {referrer_id} "
                    f"(batch: {batch_id})"
                )
                
            except Exception as e:
                logger.error(
                    f"Failed to process cashback for user {referrer_id}: {e}",
                    exc_info=True,
                )
                failed_count += 1
                failed_users.append({"user_id": referrer_id, "error": str(e)})
        
        return {
            "successful_count": successful_count,
            "failed_count": failed_count,
            "total_amount_cents": total_paid_cents,
            "failed_users": failed_users,
        }


class CashbackConfirmView(discord.ui.View):
    """Confirmation view for cashback batch processing."""
    
    def __init__(
        self,
        cog: ReferralsCog,
        ctx: commands.Context,
        amounts: list[int],
        single_user_id: Optional[int] = None,
    ) -> None:
        super().__init__(timeout=120)
        self.cog = cog
        self.ctx = ctx
        self.amounts = amounts
        self.single_user_id = single_user_id
        self.message: Optional[discord.Message] = None
    
    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green, emoji="✅")
    async def confirm_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        # Verify user has permission
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(
                "Only the command issuer can confirm this action.",
                ephemeral=True,
            )
            return
        
        await interaction.response.defer()
        
        try:
            # Generate batch ID
            batch_id = f"BATCH-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
            
            # Get pending list
            if self.single_user_id:
                # Single user mode
                pending_data = await self.cog.bot.db.get_pending_cashback_for_user(
                    self.single_user_id
                )
                pending_list = [
                    {
                        "referrer_id": self.single_user_id,
                        "pending_cents": pending_data["pending_cents"],
                        "referral_count": pending_data["referral_count"],
                    }
                ]
            else:
                # Batch mode
                pending_list = await self.cog.bot.db.get_all_pending_referral_cashbacks()
            
            # Execute payouts
            results = await self.cog._execute_cashback_payout(pending_list, batch_id)
            
            # Create results embed
            embed = create_embed(
                title="✅ Referral Cashback Batch Complete",
                description="Cashback processing has finished",
                color=discord.Color.green(),
            )
            
            embed.add_field(
                name="📊 Results",
                value=(
                    f"**Users Paid:** {results['successful_count']}\n"
                    f"**Total Distributed:** {format_usd(results['total_amount_cents'])}\n"
                    f"**Failed:** {results['failed_count']}\n"
                    f"**Batch ID:** `{batch_id}`"
                ),
                inline=False,
            )
            
            if results["failed_users"]:
                failed_list = [
                    f"<@{f['user_id']}> - {f['error'][:50]}"
                    for f in results["failed_users"][:5]
                ]
                embed.add_field(
                    name="⚠️ Failed Payouts",
                    value="\n".join(failed_list),
                    inline=False,
                )
            
            embed.set_footer(text=f"Batch ID: {batch_id}")
            
            # Disable buttons
            for item in self.children:
                item.disabled = True
            
            await interaction.followup.edit_message(
                message_id=self.message.id if self.message else interaction.message.id,
                embed=embed,
                view=self,
            )
            
            # Log to audit channel
            try:
                audit_channel_id = self.cog.bot.config.logging_channels.audit
                if audit_channel_id:
                    audit_channel = self.cog.bot.get_channel(audit_channel_id)
                    if audit_channel:
                        audit_embed = create_embed(
                            title="💰 Referral Cashback Batch Processed",
                            description=f"Batch ID: `{batch_id}`",
                            color=discord.Color.gold(),
                        )
                        
                        audit_embed.add_field(
                            name="Summary",
                            value=(
                                f"**Users Paid:** {results['successful_count']}\n"
                                f"**Total Amount:** {format_usd(results['total_amount_cents'])}\n"
                                f"**Failed:** {results['failed_count']}\n"
                                f"**Processed By:** {self.ctx.author.mention}\n"
                                f"**Mode:** {'Individual' if self.single_user_id else 'Batch'}"
                            ),
                            inline=False,
                        )
                        
                        if self.single_user_id:
                            audit_embed.add_field(
                                name="Target User",
                                value=f"<@{self.single_user_id}>",
                                inline=False,
                            )
                        
                        audit_embed.set_footer(text=f"Batch ID: {batch_id}")
                        await audit_channel.send(embed=audit_embed)
            except Exception as e:
                logger.error(f"Failed to log to audit channel: {e}")
            
            self.stop()
            
        except Exception as e:
            logger.error(f"Error confirming cashback payout: {e}", exc_info=True)
            
            error_embed = create_embed(
                title="❌ Error Processing Cashback",
                description=f"An error occurred: {str(e)}",
                color=discord.Color.red(),
            )
            
            await interaction.followup.edit_message(
                message_id=self.message.id if self.message else interaction.message.id,
                embed=error_embed,
                view=None,
            )
            self.stop()
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, emoji="❌")
    async def cancel_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(
                "Only the command issuer can cancel this action.",
                ephemeral=True,
            )
            return
        
        embed = create_embed(
            title="❌ Cashback Processing Cancelled",
            description="No cashback has been paid out.",
            color=discord.Color.red(),
        )
        
        for item in self.children:
            item.disabled = True
        
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ReferralsCog(bot))
