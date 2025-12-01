"""Reviews and feedback system with admin approval workflow and role rewards."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, Modal, TextInput, View

from apex_core.utils import create_embed

if TYPE_CHECKING:
    from bot import ApexCoreBot

logger = logging.getLogger(__name__)


class ReviewModal(Modal, title="Submit Review"):
    """Modal for submitting a product review."""

    def __init__(self, cog: "ReviewsCog", products: list[discord.app_commands.Choice[int]]):
        super().__init__()
        self.cog = cog
        self.products = products

    rating = TextInput(
        label="Rating",
        placeholder="Rate 1-5 stars (1=Poor, 5=Excellent)",
        required=True,
        style=discord.TextStyle.short,
        max_length=1,
    )

    feedback = TextInput(
        label="Feedback",
        placeholder="Share your experience (minimum 50 characters)",
        required=True,
        style=discord.TextStyle.paragraph,
        max_length=1000,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Handle review submission."""
        await interaction.response.defer(ephemeral=True)

        # Validate rating
        try:
            rating = int(self.rating.value)
            if rating < 1 or rating > 5:
                await interaction.followup.send(
                    embed=create_embed(
                        "Rating must be between 1 and 5 stars.",
                        color=discord.Color.red(),
                    ),
                    ephemeral=True,
                )
                return
        except ValueError:
            await interaction.followup.send(
                embed=create_embed(
                    "Rating must be a number between 1 and 5.",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return

        # Validate feedback length
        if len(self.feedback.value.strip()) < 50:
            await interaction.followup.send(
                embed=create_embed(
                    "Feedback must be at least 50 characters long.",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return

        # Check if user has completed purchases
        has_purchases = await self.cog.bot.db.has_completed_purchases(interaction.user.id)
        if not has_purchases:
            await interaction.followup.send(
                embed=create_embed(
                    "You must have at least one completed purchase to submit a review.",
                    color=discord.Color.orange(),
                ),
                ephemeral=True,
            )
            return

        # Check cooldown
        if not await self.cog.bot.db.check_user_review_cooldown(interaction.user.id):
            await interaction.followup.send(
                embed=create_embed(
                    "You can only submit one review every 7 days. Please wait before submitting another review.",
                    color=discord.Color.orange(),
                ),
                ephemeral=True,
            )
            return

        # Submit review
        try:
            review_id = await self.cog.bot.db.create_review(
                user_discord_id=interaction.user.id,
                product_id=None,  # General review for now
                rating=rating,
                feedback_text=self.feedback.value.strip(),
            )

            # Post to vouches channel for admin approval
            await self.cog._post_pending_review(interaction, review_id, rating, self.feedback.value.strip())

            await interaction.followup.send(
                embed=create_embed(
                    "✅ Review submitted successfully!\n\nYour review is now pending approval by staff. "
                    "You'll receive a DM once it's reviewed.",
                    color=discord.Color.green(),
                ),
                ephemeral=True,
            )

        except Exception as e:
            logger.error(f"Error submitting review: {e}")
            await interaction.followup.send(
                embed=create_embed(
                    "An error occurred while submitting your review. Please try again later.",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )


class ReviewApprovalView(View):
    """View for approving/rejecting reviews."""

    def __init__(self, cog: "ReviewsCog", review_id: int):
        super().__init__(timeout=None)  # Persistent view
        self.cog = cog
        self.review_id = review_id

    @discord.ui.button(label="✅ Approve", style=discord.ButtonStyle.green, custom_id="review_approve")
    async def approve_button(self, interaction: discord.Interaction, button: Button) -> None:
        """Approve the review."""
        # Extract review_id from the message embed footer
        if not interaction.message.embeds:
            await interaction.response.send_message(
                "Could not find review information.",
                ephemeral=True,
            )
            return

        embed = interaction.message.embeds[0]
        footer_text = embed.footer.text if embed.footer else ""
        
        # Extract review ID from footer text (format: "Review ID: 123 | User ID: 456")
        try:
            review_id_part = footer_text.split("Review ID: ")[1].split(" |")[0]
            review_id = int(review_id_part)
        except (IndexError, ValueError):
            await interaction.response.send_message(
                "Could not extract review ID from message.",
                ephemeral=True,
            )
            return

        if not self.cog._is_admin(interaction.user):
            await interaction.response.send_message(
                "You don't have permission to approve reviews.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        try:
            # Approve in database
            await self.cog.bot.db.approve_review(review_id, interaction.user.id)

            # Get review details
            review = await self.cog.bot.db.get_review_by_id(review_id)
            if not review:
                await interaction.followup.send(
                    "Review not found.",
                    ephemeral=True,
                )
                return

            # Grant Apex Insider role and discount
            await self.cog._grant_review_rewards(review["user_discord_id"])

            # Update the embed
            await self.cog._update_review_embed(interaction.message, review, "approved")

            # Send DM to user
            await self.cog._send_review_approval_dm(review["user_discord_id"])

            # Log to audit channel
            await self.cog._send_review_audit_log(
                interaction.guild,
                f"Review #{review_id} approved by {interaction.user.mention}",
                discord.Color.green(),
            )

            await interaction.followup.send("Review approved successfully!", ephemeral=True)

        except Exception as e:
            logger.error(f"Error approving review {review_id}: {e}")
            await interaction.followup.send(
                "An error occurred while approving the review.",
                ephemeral=True,
            )

    @discord.ui.button(label="❌ Reject", style=discord.ButtonStyle.red, custom_id="review_reject")
    async def reject_button(self, interaction: discord.Interaction, button: Button) -> None:
        """Reject the review."""
        # Extract review_id from the message embed footer
        if not interaction.message.embeds:
            await interaction.response.send_message(
                "Could not find review information.",
                ephemeral=True,
            )
            return

        embed = interaction.message.embeds[0]
        footer_text = embed.footer.text if embed.footer else ""
        
        # Extract review ID from footer text (format: "Review ID: 123 | User ID: 456")
        try:
            review_id_part = footer_text.split("Review ID: ")[1].split(" |")[0]
            review_id = int(review_id_part)
        except (IndexError, ValueError):
            await interaction.response.send_message(
                "Could not extract review ID from message.",
                ephemeral=True,
            )
            return

        if not self.cog._is_admin(interaction.user):
            await interaction.response.send_message(
                "You don't have permission to reject reviews.",
                ephemeral=True,
            )
            return

        # Create modal for rejection reason
        class RejectionModal(Modal, title="Reject Review"):
            reason = TextInput(
                label="Rejection Reason",
                placeholder="Please provide a reason for rejecting this review",
                required=True,
                style=discord.TextStyle.paragraph,
                max_length=500,
            )

            async def on_submit(self, modal_interaction: discord.Interaction) -> None:
                await modal_interaction.response.defer()

                try:
                    # Reject in database
                    await self.cog.bot.db.reject_review(
                        review_id, interaction.user.id, self.reason.value
                    )

                    # Get review details
                    review = await self.cog.bot.db.get_review_by_id(review_id)
                    if not review:
                        await modal_interaction.followup.send(
                            "Review not found.",
                            ephemeral=True,
                        )
                        return

                    # Update the embed
                    await self.cog._update_review_embed(modal_interaction.message, review, "rejected")

                    # Send DM to user
                    await self.cog._send_review_rejection_dm(
                        review["user_discord_id"], self.reason.value
                    )

                    # Log to audit channel
                    await self.cog._send_review_audit_log(
                        modal_interaction.guild,
                        f"Review #{review_id} rejected by {interaction.user.mention}: {self.reason.value}",
                        discord.Color.red(),
                    )

                    await modal_interaction.followup.send("Review rejected successfully!", ephemeral=True)

                except Exception as e:
                    logger.error(f"Error rejecting review {review_id}: {e}")
                    await modal_interaction.followup.send(
                        "An error occurred while rejecting the review.",
                        ephemeral=True,
                    )

        await interaction.response.send_modal(RejectionModal())


class ReviewsCog(commands.Cog):
    """Reviews and feedback system with admin approval workflow."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        """Called when the cog is loaded."""
        # Register persistent view for review approval
        self.bot.add_view(ReviewApprovalView(self, 0))

    def _is_admin(self, member: discord.Member | None) -> bool:
        """Check if user has admin role."""
        if member is None:
            return False
        admin_role_id = self.bot.config.role_ids.admin
        return any(role.id == admin_role_id for role in getattr(member, "roles", []))

    async def _get_vouches_channel(self, guild: discord.Guild) -> discord.TextChannel | None:
        """Get the vouches channel for posting reviews."""
        vouches_channel_id = getattr(self.bot.config.logging_channels, "vouches", None)
        if vouches_channel_id:
            channel = guild.get_channel(vouches_channel_id)
            if isinstance(channel, discord.TextChannel):
                return channel
        
        # Fallback to audit channel if vouches channel not configured
        audit_channel_id = self.bot.config.logging_channels.audit
        audit_channel = guild.get_channel(audit_channel_id)
        if isinstance(audit_channel, discord.TextChannel):
            return audit_channel
            
        return None

    async def _post_pending_review(
        self, interaction: discord.Interaction, review_id: int, rating: int, feedback: str
    ) -> None:
        """Post a pending review to the vouches channel."""
        if not interaction.guild:
            return

        channel = await self._get_vouches_channel(interaction.guild)
        if not channel:
            logger.error("Vouches channel not found")
            return

        # Create embed
        stars = "⭐" * rating
        embed = create_embed(
            title="⏳ Pending Review",
            description=f"**Rating:** {stars} ({rating}/5)\n\n**Feedback:**\n{feedback}",
            color=discord.Color.orange(),
        )
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url,
        )
        embed.add_field(name="Status", value="⏳ Pending Approval", inline=False)
        embed.set_footer(text=f"Review ID: {review_id} | User ID: {interaction.user.id}")

        # Create approval view
        view = ReviewApprovalView(self, review_id)

        await channel.send(embed=embed, view=view)

    async def _update_review_embed(
        self, message: discord.Message, review: dict, status: str
    ) -> None:
        """Update a review embed with new status."""
        if not message.embeds:
            return

        embed = message.embeds[0]
        stars = "⭐" * review["rating"]

        # Update title and description
        if status == "approved":
            embed.title = "✅ Approved Review"
            color = discord.Color.green()
            status_text = "✅ Approved"
        elif status == "rejected":
            embed.title = "❌ Rejected Review"
            color = discord.Color.red()
            status_text = "❌ Rejected"
        else:
            return

        embed.description = f"**Rating:** {stars} ({review['rating']}/5)\n\n**Feedback:**\n{review['feedback_text']}"
        embed.color = color

        # Update status field
        for i, field in enumerate(embed.fields):
            if field.name == "Status":
                embed.set_field_at(
                    i,
                    name="Status",
                    value=status_text,
                    inline=False,
                )
                break
        else:
            embed.add_field(name="Status", value=status_text, inline=False)

        # Add rejection reason if provided
        if status == "rejected" and review["rejected_reason"]:
            embed.add_field(
                name="Rejection Reason",
                value=review["rejected_reason"],
                inline=False,
            )

        # Remove view if no longer pending
        await message.edit(embed=embed, view=None)

    async def _grant_review_rewards(self, user_discord_id: int) -> None:
        """Grant Apex Insider role and discount to user."""
        from apex_core.utils.roles import check_and_update_roles

        guild = self.bot.guilds[0] if self.bot.guilds else None
        if not guild:
            return

        # Update user roles using the existing role system
        roles_added, roles_removed = await check_and_update_roles(
            user_discord_id, self.bot.db, guild, self.bot.config
        )

        logger.info(f"Review rewards granted for user {user_discord_id}: Added {len(roles_added)} roles")

    async def _revoke_review_rewards(self, user_discord_id: int) -> None:
        """Revoke Apex Insider role and discount from user."""
        from apex_core.utils.roles import check_and_update_roles

        guild = self.bot.guilds[0] if self.bot.guilds else None
        if not guild:
            return

        # Update user roles (this will remove Insider role if no longer eligible)
        roles_added, roles_removed = await check_and_update_roles(
            user_discord_id, self.bot.db, guild, self.bot.config
        )

        logger.info(f"Review rewards revoked for user {user_discord_id}: Removed {len(roles_removed)} roles")

    async def _send_review_approval_dm(self, user_discord_id: int) -> None:
        """Send approval DM to user."""
        user = self.bot.get_user(user_discord_id)
        if not user:
            return

        embed = create_embed(
            title="✅ Review Approved!",
            description="Your review has been approved by our staff!\n\nYou've earned:\n"
            "• @Apex Insider Role\n"
            "• 0.5% discount on all future purchases\n\n"
            "Thank you for your valuable feedback!",
            color=discord.Color.green(),
        )

        try:
            await user.send(embed=embed)
        except discord.HTTPException:
            logger.warning(f"Failed to send approval DM to user {user_discord_id}")

    async def _send_review_rejection_dm(self, user_discord_id: int, reason: str) -> None:
        """Send rejection DM to user."""
        user = self.bot.get_user(user_discord_id)
        if not user:
            return

        embed = create_embed(
            title="❌ Review Rejected",
            description=f"Your review was rejected by our staff.\n\n**Reason:** {reason}\n\n"
            "If you have any questions, please contact support.",
            color=discord.Color.red(),
        )

        try:
            await user.send(embed=embed)
        except discord.HTTPException:
            logger.warning(f"Failed to send rejection DM to user {user_discord_id}")

    async def _send_review_audit_log(
        self, guild: discord.Guild, message: str, color: discord.Color
    ) -> None:
        """Send audit log message."""
        audit_channel_id = self.bot.config.logging_channels.audit
        audit_channel = guild.get_channel(audit_channel_id)
        if isinstance(audit_channel, discord.TextChannel):
            try:
                embed = create_embed(message, color=color)
                await audit_channel.send(embed=embed)
            except discord.HTTPException as e:
                logger.warning(f"Failed to send audit log: {e}")

    @app_commands.command(name="review", description="Submit a product review")
    async def review(self, interaction: discord.Interaction) -> None:
        """Submit a product review."""
        await interaction.response.send_modal(ReviewModal(self, []))

    @app_commands.command(name="my-reviews", description="View your submitted reviews")
    async def my_reviews(self, interaction: discord.Interaction) -> None:
        """Show user's submitted reviews."""
        await interaction.response.defer()

        try:
            reviews = await self.bot.db.get_user_reviews(interaction.user.id)
            if not reviews:
                await interaction.followup.send(
                    embed=create_embed(
                        "You haven't submitted any reviews yet.",
                        color=discord.Color.blue(),
                    ),
                    ephemeral=True,
                )
                return

            # Create embed with review summary
            approved_count = sum(1 for r in reviews if r["status"] == "approved")
            pending_count = sum(1 for r in reviews if r["status"] == "pending")
            rejected_count = sum(1 for r in reviews if r["status"] == "rejected")

            embed = create_embed(
                title="Your Reviews",
                description=f"**Total:** {len(reviews)}\n"
                f"✅ Approved: {approved_count}\n"
                f"⏳ Pending: {pending_count}\n"
                f"❌ Rejected: {rejected_count}",
                color=discord.Color.blue(),
            )

            # Add recent reviews
            for review in reviews[:5]:  # Show last 5 reviews
                stars = "⭐" * review["rating"]
                status_emoji = {"approved": "✅", "pending": "⏳", "rejected": "❌"}
                status_text = f"{status_emoji[review['status']]} {review['status'].title()}"

                product_name = "General Review"
                if review["service_name"]:
                    product_name = f"{review['service_name']}"
                    if review["variant_name"]:
                        product_name += f" - {review['variant_name']}"

                embed.add_field(
                    name=f"{stars} {product_name}",
                    value=f"{review['feedback_text'][:100]}{'...' if len(review['feedback_text']) > 100 else ''}\n"
                    f"Status: {status_text}",
                    inline=False,
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error fetching user reviews: {e}")
            await interaction.followup.send(
                embed=create_embed(
                    "An error occurred while fetching your reviews.",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )

    @app_commands.command(name="reviews", description="Manage reviews (Admin only)")
    @app_commands.describe(
        action="Action to perform",
        status="Filter by status (for list action)",
        review_id="Review ID (for delete action)",
    )
    @app_commands.choices(
        action=[
            discord.app_commands.Choice(name="list", value="list"),
            discord.app_commands.Choice(name="delete", value="delete"),
        ]
    )
    @app_commands.choices(
        status=[
            discord.app_commands.Choice(name="pending", value="pending"),
            discord.app_commands.Choice(name="approved", value="approved"),
            discord.app_commands.Choice(name="rejected", value="rejected"),
        ]
    )
    async def reviews_admin(
        self,
        interaction: discord.Interaction,
        action: str,
        status: Optional[str] = None,
        review_id: Optional[str] = None,
    ) -> None:
        """Admin command to manage reviews."""
        if not self._is_admin(interaction.user):
            await interaction.response.send_message(
                "You don't have permission to use this command.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            if action == "list":
                reviews = await self.bot.db.get_all_reviews(status=status, limit=20)

                if not reviews:
                    await interaction.followup.send(
                        embed=create_embed(
                            f"No reviews found{' with status ' + status if status else ''}.",
                            color=discord.Color.blue(),
                        ),
                        ephemeral=True,
                    )
                    return

                embed = create_embed(
                    title=f"Reviews {f'({status.title()})' if status else ''}",
                    description=f"Found {len(reviews)} reviews",
                    color=discord.Color.blue(),
                )

                for review in reviews[:10]:  # Show first 10
                    stars = "⭐" * review["rating"]
                    status_emoji = {"approved": "✅", "pending": "⏳", "rejected": "❌"}
                    user = self.bot.get_user(review["user_discord_id"])

                    product_name = "General Review"
                    if review["service_name"]:
                        product_name = f"{review['service_name']}"
                        if review["variant_name"]:
                            product_name += f" - {review['variant_name']}"

                    user_text = user.mention if user else f'ID: {review["user_discord_id"]}'
                    
                    embed.add_field(
                        name=f"#{review['id']} {stars} {product_name}",
                        value=f"User: {user_text}\n"
                               f"Status: {status_emoji[review['status']]} {review['status'].title()}\n"
                               f"Feedback: {review['feedback_text'][:100]}{'...' if len(review['feedback_text']) > 100 else ''}",
                        inline=False,
                    )

                await interaction.followup.send(embed=embed, ephemeral=True)

            elif action == "delete":
                if not review_id:
                    await interaction.followup.send(
                        embed=create_embed(
                            "Review ID is required for delete action.",
                            color=discord.Color.red(),
                        ),
                        ephemeral=True,
                    )
                    return

                try:
                    review_id_int = int(review_id)
                except ValueError:
                    await interaction.followup.send(
                        embed=create_embed(
                            "Invalid review ID. Must be a number.",
                            color=discord.Color.red(),
                        ),
                        ephemeral=True,
                    )
                    return

                # Get review details before deletion
                review = await self.bot.db.get_review_by_id(review_id_int)
                if not review:
                    await interaction.followup.send(
                        embed=create_embed(
                            "Review not found.",
                            color=discord.Color.red(),
                        ),
                        ephemeral=True,
                    )
                    return

                # Check if this is user's only approved review
                if review["status"] == "approved":
                    approved_count = await self.bot.db.count_user_approved_reviews(review["user_discord_id"])
                    if approved_count <= 1:
                        # This is the user's only approved review, revoke rewards
                        await self._revoke_review_rewards(review["user_discord_id"])

                # Delete the review
                await self.bot.db.delete_review(review_id_int)

                # Send DM to user
                await self._send_review_deletion_dm(review["user_discord_id"])

                # Log to audit channel
                await self._send_review_audit_log(
                    interaction.guild,
                    f"Review #{review_id_int} deleted by {interaction.user.mention}",
                    discord.Color.orange(),
                )

                await interaction.followup.send(
                    embed=create_embed(
                        f"Review #{review_id_int} deleted successfully.",
                        color=discord.Color.green(),
                    ),
                    ephemeral=True,
                )

        except Exception as e:
            logger.error(f"Error in reviews admin command: {e}")
            await interaction.followup.send(
                embed=create_embed(
                    "An error occurred while processing your request.",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )

    async def _send_review_deletion_dm(self, user_discord_id: int) -> None:
        """Send deletion DM to user."""
        user = self.bot.get_user(user_discord_id)
        if not user:
            return

        embed = create_embed(
            title="🗑️ Review Deleted",
            description="Your review has been deleted by our staff.\n\n"
            "If this was your only approved review, your @Apex Insider role and 0.5% discount have been removed.\n\n"
            "If you have any questions, please contact support.",
            color=discord.Color.orange(),
        )

        try:
            await user.send(embed=embed)
        except discord.HTTPException:
            logger.warning(f"Failed to send deletion DM to user {user_discord_id}")


async def setup(bot: commands.Bot) -> None:
    """Add the reviews cog to the bot."""
    await bot.add_cog(ReviewsCog(bot))