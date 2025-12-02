from __future__ import annotations

import asyncio
import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from apex_core.utils import create_embed, format_usd

logger = logging.getLogger(__name__)


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


class ChannelInputModal(discord.ui.Modal, title="Channel Selection"):
    """Modal for users to input the channel destination."""
    
    channel_input = discord.ui.TextInput(
        label="Channel name or #mention",
        placeholder="e.g., products or #products",
        required=True,
        max_length=100,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        cog: SetupCog = interaction.client.get_cog("SetupCog")  # type: ignore
        if not cog:
            await interaction.followup.send("Setup cog not loaded.", ephemeral=True)
            return

        await cog._process_channel_input(interaction, self.channel_input.value)


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
        self.user_states: dict[int, dict] = {}

    def _is_admin(self, member: discord.Member | None) -> bool:
        if member is None:
            return False
        admin_role_id = self.bot.config.role_ids.admin
        return any(role.id == admin_role_id for role in getattr(member, "roles", []))

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

    async def _deploy_panel(
        self,
        panel_type: str,
        channel: discord.TextChannel,
        guild: discord.Guild,
        user_id: int,
    ) -> bool:
        """Deploy a panel to a channel."""
        try:
            if panel_type == "products":
                embed, view = await self._create_product_panel()
                title = "Apex Core: Products"
            elif panel_type == "support":
                embed, view = await self._create_support_panel()
                title = "Support Options"
            elif panel_type == "help":
                embed, view = await self._create_help_panel()
                title = "How to Use Apex Core"
            elif panel_type == "reviews":
                embed, view = await self._create_reviews_panel()
                title = "Share Your Experience"
            else:
                return False

            message = await channel.send(embed=embed, view=view)

            existing = await self.bot.db.get_panel_by_type_and_channel(
                panel_type, channel.id, guild.id
            )

            if existing:
                await self.bot.db.update_panel(existing["id"], message.id)
            else:
                await self.bot.db.deploy_panel(
                    panel_type=panel_type,
                    message_id=message.id,
                    channel_id=channel.id,
                    guild_id=guild.id,
                    title=title,
                    description=embed.description or "",
                    created_by_staff_id=user_id,
                )

            await self._log_audit(
                guild,
                f"Panel Deployed",
                f"**Type:** {panel_type}\n**Channel:** {channel.mention}\n**Message:** {message.id}",
            )

            return True

        except Exception as e:
            logger.error(f"Failed to deploy panel: {e}")
            return False

    async def _handle_setup_selection(
        self, interaction: discord.Interaction, selection: str
    ) -> None:
        """Handle the initial setup menu selection."""
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command must be used in a server.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        if selection == "all":
            panel_types = ["products", "support", "help", "reviews"]
        else:
            panel_types = [selection]

        self.user_states[interaction.user.id] = {
            "panel_types": panel_types,
            "guild_id": interaction.guild.id,
            "current_index": 0,
        }

        await self._prompt_for_channel(interaction, 0, panel_types)

    async def _prompt_for_channel(
        self,
        interaction: discord.Interaction,
        index: int,
        panel_types: list[str],
    ) -> None:
        """Prompt user for channel destination."""
        if index >= len(panel_types):
            await interaction.followup.send(
                "✅ All panels deployed successfully!", ephemeral=True
            )
            if interaction.user.id in self.user_states:
                del self.user_states[interaction.user.id]
            return

        panel_type = panel_types[index]
        emoji = self._get_panel_emoji(panel_type)

        await interaction.followup.send(
            f"{emoji} Where should I deploy the **{panel_type.title()} Panel**?\n"
            f"(Type channel name or #mention)",
            ephemeral=True,
        )

        self.user_states[interaction.user.id]["current_index"] = index
        self.user_states[interaction.user.id]["awaiting_channel"] = True

    async def _process_channel_input(
        self, interaction: discord.Interaction, channel_input: str
    ) -> None:
        """Process channel input and deploy panel."""
        if interaction.guild is None:
            await interaction.followup.send(
                "This command must be used in a server.", ephemeral=True
            )
            return

        channel = None

        if channel_input.startswith("#"):
            channel_input = channel_input[1:]

        for ch in interaction.guild.text_channels:
            if ch.name.lower() == channel_input.lower() or str(ch.id) == channel_input:
                channel = ch
                break

        if not channel:
            await interaction.followup.send(
                f"❌ Channel `{channel_input}` not found. Please try again.",
                ephemeral=True,
            )
            return

        if not channel.permissions_for(interaction.guild.me).send_messages:
            await interaction.followup.send(
                f"❌ I don't have permission to send messages in {channel.mention}.",
                ephemeral=True,
            )
            return

        state = self.user_states.get(interaction.user.id)
        if not state:
            await interaction.followup.send(
                "Session expired. Please start over with `/setup`.",
                ephemeral=True,
            )
            return

        current_index = state.get("current_index", 0)
        panel_types = state.get("panel_types", [])

        if current_index >= len(panel_types):
            await interaction.followup.send(
                "Setup complete!", ephemeral=True
            )
            return

        panel_type = panel_types[current_index]

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

        emoji = self._get_panel_emoji(panel_type)
        await interaction.followup.send(
            f"{emoji} ✅ Deployed to {channel.mention}",
            ephemeral=True,
        )

        await asyncio.sleep(1)

        state["current_index"] = current_index + 1
        await self._prompt_for_channel(interaction, current_index + 1, panel_types)

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


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SetupCog(bot))
