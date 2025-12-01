from __future__ import annotations

import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from apex_core.utils import create_embed, format_usd

logger = logging.getLogger(__name__)


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


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ReferralsCog(bot))
