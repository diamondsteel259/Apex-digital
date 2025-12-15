"""Review system for user feedback and ratings."""

from __future__ import annotations

from typing import Literal, Optional

import discord
from discord import app_commands
from discord.ext import commands

from apex_core.logger import get_logger
from apex_core.utils import create_embed, format_usd
from apex_core.utils.error_messages import get_error_message
from apex_core.utils.permissions import is_admin_from_bot

logger = get_logger()


class ReviewsCog(commands.Cog):
    """Commands for review system."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def _is_admin(self, user: discord.User, guild: Optional[discord.Guild]) -> bool:
        """Check if user is admin."""
        return is_admin_from_bot(user, guild, self.bot)

    @app_commands.command(name="review")
    @app_commands.describe(
        order_id="Order ID to review",
        rating="Rating from 1-5 stars",
        comment="Your review comment (50-1000 characters)",
        photo="Optional photo attachment"
    )
    async def submit_review(
        self,
        interaction: discord.Interaction,
        order_id: int,
        rating: int,
        comment: str,
        photo: Optional[discord.Attachment] = None
    ) -> None:
        """Submit a review for an order."""
        await interaction.response.defer(ephemeral=True)
        
        logger.info(
            f"Review submission started | User: {interaction.user.id} | "
            f"Order: {order_id} | Rating: {rating}"
        )
        
        try:
            # Validate rating
            if not 1 <= rating <= 5:
                logger.warning(f"Invalid rating submitted | User: {interaction.user.id} | Rating: {rating}")
                await interaction.followup.send(
                    "❌ Rating must be between 1 and 5 stars.",
                    ephemeral=True
                )
                return
            
            # Validate comment length
            if len(comment) < 50:
                logger.warning(f"Review comment too short | User: {interaction.user.id} | Length: {len(comment)}")
                await interaction.followup.send(
                    "❌ Review comment must be at least 50 characters. Please provide more details.",
                    ephemeral=True
                )
                return
            
            if len(comment) > 1000:
                logger.warning(f"Review comment too long | User: {interaction.user.id} | Length: {len(comment)}")
                await interaction.followup.send(
                    "❌ Review comment must be 1000 characters or less.",
                    ephemeral=True
                )
                return
            
            # Handle photo upload if provided
            photo_url = None
            if photo:
                logger.info(f"Processing review photo | User: {interaction.user.id} | File: {photo.filename}")
                # In a real implementation, you'd upload to a CDN/storage
                # For now, we'll just store the URL if it's an image
                if photo.content_type and photo.content_type.startswith("image/"):
                    photo_url = photo.url
                    logger.info(f"Review photo URL stored | URL: {photo_url[:50]}...")
                else:
                    logger.warning(f"Invalid photo type | User: {interaction.user.id} | Type: {photo.content_type}")
                    await interaction.followup.send(
                        "⚠️ Photo attachment must be an image file. Continuing without photo...",
                        ephemeral=True
                    )
            
            # Create review
            review_id = await self.bot.db.create_review(
                user_discord_id=interaction.user.id,
                order_id=order_id,
                rating=rating,
                comment=comment,
                photo_url=photo_url
            )
            
            logger.info(f"Review created successfully | Review ID: {review_id} | User: {interaction.user.id}")
            
            # Get order details for confirmation
            order = await self.bot.db.get_order_by_id(order_id)
            product = None
            if order and order["product_id"] != 0:
                product_row = await self.bot.db.get_product(order["product_id"])
                product = dict(product_row) if product_row and not isinstance(product_row, dict) else product_row
            
            embed = create_embed(
                title="✅ Review Submitted!",
                description=(
                    f"Thank you for your review! Your feedback has been submitted and is pending approval.\n\n"
                    f"**Order:** #{order_id}\n"
                    f"**Rating:** {'⭐' * rating} ({rating}/5)\n"
                    f"**Status:** Pending Review"
                ),
                color=discord.Color.green()
            )
            
            if product:
                embed.add_field(
                    name="Product",
                    value=f"{product.get('service_name', 'N/A')} - {product.get('variant_name', 'N/A')}",
                    inline=False
                )
            
            embed.add_field(
                name="What Happens Next?",
                value=(
                    "• Your review will be reviewed by staff\n"
                    "• Upon approval, you'll receive:\n"
                    "  - @Apex Insider role\n"
                    "  - 0.5% discount on future purchases\n"
                    "• You'll be notified via DM when reviewed"
                ),
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            # Log to audit channel
            if interaction.guild:
                audit_channel_id = getattr(self.bot.config.logging_channels, "audit", None)
                if audit_channel_id:
                    channel = interaction.guild.get_channel(audit_channel_id)
                    if isinstance(channel, discord.TextChannel):
                        audit_embed = create_embed(
                            title="📝 New Review Submitted",
                            description=(
                                f"**User:** {interaction.user.mention} ({interaction.user.id})\n"
                                f"**Order:** #{order_id}\n"
                                f"**Rating:** {'⭐' * rating} ({rating}/5)\n"
                                f"**Review ID:** {review_id}"
                            ),
                            color=discord.Color.blue()
                        )
                        try:
                            await channel.send(embed=audit_embed)
                            logger.info(f"Review audit log sent | Review ID: {review_id}")
                        except Exception as e:
                            logger.error(f"Failed to send review audit log: {e}")
            
        except ValueError as e:
            logger.warning(f"Review submission failed (validation) | User: {interaction.user.id} | Error: {e}")
            await interaction.followup.send(
                f"❌ {str(e)}",
                ephemeral=True
            )
        except Exception as e:
            logger.exception(f"Failed to submit review | User: {interaction.user.id} | Error: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Failed to submit review: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="myreviews")
    @app_commands.describe(status="Filter by status (optional)")
    async def my_reviews(
        self,
        interaction: discord.Interaction,
        status: Optional[Literal["pending", "approved", "rejected"]] = None
    ) -> None:
        """View your submitted reviews."""
        await interaction.response.defer(ephemeral=True)
        
        logger.info(f"User viewing reviews | User: {interaction.user.id} | Status filter: {status}")
        
        try:
            reviews = await self.bot.db.get_reviews_by_user(
                interaction.user.id,
                status=status
            )
            
            if not reviews:
                status_text = f" with status '{status}'" if status else ""
                await interaction.followup.send(
                    f"📭 No reviews found{status_text}.",
                    ephemeral=True
                )
                return
            
            embed = create_embed(
                title="📝 Your Reviews",
                description=f"Found {len(reviews)} review(s):",
                color=discord.Color.blue()
            )
            
            for review in reviews[:10]:
                status_emoji = {
                    "pending": "⏳",
                    "approved": "✅",
                    "rejected": "❌"
                }
                
                embed.add_field(
                    name=f"{status_emoji.get(review['status'], '❓')} Review #{review['id']} - Order #{review['order_id']}",
                    value=(
                        f"**Rating:** {'⭐' * review['rating']} ({review['rating']}/5)\n"
                        f"**Status:** {review['status'].title()}\n"
                        f"**Comment:** {review['comment'][:100]}{'...' if len(review['comment']) > 100 else ''}\n"
                        f"**Date:** {review['created_at'][:10]}"
                    ),
                    inline=False
                )
            
            if len(reviews) > 10:
                embed.set_footer(text=f"Showing 10 of {len(reviews)} reviews")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.exception(f"Failed to get user reviews | User: {interaction.user.id} | Error: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Failed to load reviews: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="pendingreviews")
    async def pending_reviews(self, interaction: discord.Interaction) -> None:
        """View pending reviews for approval (admin only)."""
        if not self._is_admin(interaction.user, interaction.guild):
            logger.warning(f"Non-admin attempted pendingreviews | User: {interaction.user.id}")
            await interaction.response.send_message(
                "🚫 You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        logger.info(f"Admin viewing pending reviews | Admin: {interaction.user.id}")
        
        try:
            reviews = await self.bot.db.get_pending_reviews(limit=20)
            
            if not reviews:
                await interaction.followup.send(
                    "✅ No pending reviews!",
                    ephemeral=True
                )
                return
            
            embed = create_embed(
                title="⏳ Pending Reviews",
                description=f"Found {len(reviews)} pending review(s) awaiting approval:",
                color=discord.Color.orange()
            )
            
            for review in reviews[:10]:
                # Get order details
                order = await self.bot.db.get_order_by_id(review["order_id"])
                product_name = "Unknown Product"
                if order:
                    if order["product_id"] != 0:
                        product_row = await self.bot.db.get_product(order["product_id"])
                        product = dict(product_row) if product_row and not isinstance(product_row, dict) else product_row
                        if product:
                            product_name = product.get("variant_name") or "Unknown"
                    else:
                        product_name = "Manual Order"
                
                embed.add_field(
                    name=f"Review #{review['id']} - Order #{review['order_id']}",
                    value=(
                        f"**User:** <@{review['user_discord_id']}>\n"
                        f"**Product:** {product_name}\n"
                        f"**Rating:** {'⭐' * review['rating']} ({review['rating']}/5)\n"
                        f"**Comment:** {review['comment'][:150]}{'...' if len(review['comment']) > 150 else ''}\n"
                        f"**Submitted:** {review['created_at'][:10]}"
                    ),
                    inline=False
                )
            
            if len(reviews) > 10:
                embed.set_footer(text=f"Showing 10 of {len(reviews)} reviews. Use /approvereview or /rejectreview to process.")
            else:
                embed.set_footer(text="Use /approvereview or /rejectreview to process reviews")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.exception(f"Failed to get pending reviews | Admin: {interaction.user.id} | Error: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Failed to load pending reviews: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="approvereview")
    @app_commands.describe(
        review_id="Review ID to approve",
        award_insider="Award Apex Insider role (default: true)"
    )
    async def approve_review(
        self,
        interaction: discord.Interaction,
        review_id: int,
        award_insider: bool = True
    ) -> None:
        """Approve a review and award rewards (admin only)."""
        if not self._is_admin(interaction.user, interaction.guild):
            logger.warning(f"Non-admin attempted approvereview | User: {interaction.user.id}")
            await interaction.response.send_message(
                "🚫 You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        logger.info(
            f"Admin approving review | Admin: {interaction.user.id} | "
            f"Review: {review_id} | Award Insider: {award_insider}"
        )
        
        try:
            review = await self.bot.db.get_review(review_id)
            if not review:
                logger.warning(f"Review not found for approval | Review ID: {review_id}")
                await interaction.followup.send(
                    f"❌ Review #{review_id} not found.",
                    ephemeral=True
                )
                return
            
            if review["status"] != "pending":
                logger.warning(
                    f"Review already processed | Review ID: {review_id} | Status: {review['status']}"
                )
                await interaction.followup.send(
                    f"❌ Review #{review_id} has already been {review['status']}.",
                    ephemeral=True
                )
                return
            
            # Approve review
            success = await self.bot.db.approve_review(review_id, interaction.user.id)
            
            if not success:
                logger.error(f"Failed to approve review | Review ID: {review_id}")
                await interaction.followup.send(
                    "❌ Failed to approve review. Please try again.",
                    ephemeral=True
                )
                return
            
            logger.info(f"Review approved | Review ID: {review_id}")
            
            # Award Apex Insider role if configured
            if award_insider and interaction.guild:
                insider_role_id = getattr(self.bot.config.role_ids, "apex_insider", None)
                if insider_role_id:
                    try:
                        user = await interaction.guild.fetch_member(review["user_discord_id"])
                        role = interaction.guild.get_role(insider_role_id)
                        if user and role:
                            await user.add_roles(role, reason=f"Review #{review_id} approved")
                            logger.info(
                                f"Apex Insider role awarded | User: {user.id} | "
                                f"Review: {review_id}"
                            )
                    except Exception as e:
                        logger.error(f"Failed to award Apex Insider role: {e}")
            
            # Send notification to reviewer
            try:
                user = await self.bot.fetch_user(review["user_discord_id"])
                if user:
                    embed = create_embed(
                        title="✅ Your Review Was Approved!",
                        description=(
                            f"Thank you for your review! Your feedback has been approved.\n\n"
                            f"**Review ID:** #{review_id}\n"
                            f"**Rating:** {'⭐' * review['rating']} ({review['rating']}/5)"
                        ),
                        color=discord.Color.green()
                    )
                    
                    if award_insider:
                        embed.add_field(
                            name="🎁 Rewards",
                            value=(
                                "• @Apex Insider role has been assigned\n"
                                "• 0.5% discount applied to your account"
                            ),
                            inline=False
                        )
                    
                    await user.send(embed=embed)
                    logger.info(f"Review approval notification sent | User: {user.id}")
            except discord.Forbidden:
                logger.warning(f"Cannot send DM to user {review['user_discord_id']} - DMs disabled")
            except Exception as e:
                logger.error(f"Failed to send review approval notification: {e}")
            
            await interaction.followup.send(
                f"✅ Review #{review_id} has been approved! Rewards have been awarded.",
                ephemeral=True
            )
            
        except Exception as e:
            logger.exception(f"Failed to approve review | Admin: {interaction.user.id} | Error: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Failed to approve review: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="rejectreview")
    @app_commands.describe(
        review_id="Review ID to reject",
        reason="Reason for rejection (optional)"
    )
    async def reject_review(
        self,
        interaction: discord.Interaction,
        review_id: int,
        reason: Optional[str] = None
    ) -> None:
        """Reject a review (admin only)."""
        if not self._is_admin(interaction.user, interaction.guild):
            logger.warning(f"Non-admin attempted rejectreview | User: {interaction.user.id}")
            await interaction.response.send_message(
                "🚫 You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        logger.info(
            f"Admin rejecting review | Admin: {interaction.user.id} | "
            f"Review: {review_id} | Reason: {reason or 'None'}"
        )
        
        try:
            review = await self.bot.db.get_review(review_id)
            if not review:
                logger.warning(f"Review not found for rejection | Review ID: {review_id}")
                await interaction.followup.send(
                    f"❌ Review #{review_id} not found.",
                    ephemeral=True
                )
                return
            
            if review["status"] != "pending":
                logger.warning(
                    f"Review already processed | Review ID: {review_id} | Status: {review['status']}"
                )
                await interaction.followup.send(
                    f"❌ Review #{review_id} has already been {review['status']}.",
                    ephemeral=True
                )
                return
            
            # Reject review
            success = await self.bot.db.reject_review(review_id, interaction.user.id, reason)
            
            if not success:
                logger.error(f"Failed to reject review | Review ID: {review_id}")
                await interaction.followup.send(
                    "❌ Failed to reject review. Please try again.",
                    ephemeral=True
                )
                return
            
            logger.info(f"Review rejected | Review ID: {review_id}")
            
            # Send notification to reviewer
            try:
                user = await self.bot.fetch_user(review["user_discord_id"])
                if user:
                    embed = create_embed(
                        title="❌ Your Review Was Rejected",
                        description=(
                            f"Your review has been reviewed and unfortunately did not meet our guidelines.\n\n"
                            f"**Review ID:** #{review_id}"
                        ),
                        color=discord.Color.red()
                    )
                    
                    if reason:
                        embed.add_field(name="Reason", value=reason, inline=False)
                    else:
                        embed.add_field(
                            name="Reason",
                            value="Review did not meet our community guidelines.",
                            inline=False
                        )
                    
                    await user.send(embed=embed)
                    logger.info(f"Review rejection notification sent | User: {user.id}")
            except discord.Forbidden:
                logger.warning(f"Cannot send DM to user {review['user_discord_id']} - DMs disabled")
            except Exception as e:
                logger.error(f"Failed to send review rejection notification: {e}")
            
            await interaction.followup.send(
                f"✅ Review #{review_id} has been rejected. User has been notified.",
                ephemeral=True
            )
            
        except Exception as e:
            logger.exception(f"Failed to reject review | Admin: {interaction.user.id} | Error: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Failed to reject review: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="reviewstats")
    @app_commands.describe(product_id="Product ID to get stats for (optional)")
    async def review_stats(
        self,
        interaction: discord.Interaction,
        product_id: Optional[int] = None
    ) -> None:
        """View review statistics (admin only for product-specific stats)."""
        is_admin = self._is_admin(interaction.user, interaction.guild)
        
        if product_id and not is_admin:
            logger.warning(f"Non-admin attempted product review stats | User: {interaction.user.id}")
            await interaction.response.send_message(
                "🚫 Only admins can view product-specific review statistics.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        logger.info(
            f"Review stats requested | User: {interaction.user.id} | "
            f"Product: {product_id or 'all'}"
        )
        
        try:
            stats = await self.bot.db.get_review_stats(product_id)
            
            embed = create_embed(
                title=f"📊 Review Statistics{' - Product #' + str(product_id) if product_id else ''}",
                description=(
                    f"**Total Reviews:** {stats['total_reviews']}\n"
                    f"**Average Rating:** {stats['avg_rating']:.2f} ⭐"
                ),
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="Rating Distribution",
                value=(
                    f"⭐ 5 Stars: {stats['five_star']}\n"
                    f"⭐ 4 Stars: {stats['four_star']}\n"
                    f"⭐ 3 Stars: {stats['three_star']}\n"
                    f"⭐ 2 Stars: {stats['two_star']}\n"
                    f"⭐ 1 Star: {stats['one_star']}"
                ),
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.exception(f"Failed to get review stats | User: {interaction.user.id} | Error: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Failed to load review statistics: {str(e)}",
                ephemeral=True
            )


async def setup(bot: commands.Bot) -> None:
    """Load the ReviewsCog cog."""
    await bot.add_cog(ReviewsCog(bot))

