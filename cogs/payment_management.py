"""Admin commands for managing payment methods in Discord."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from apex_core.utils import create_embed
from apex_core.utils.admin_checks import admin_only
from apex_core.logger import get_logger

logger = get_logger()

PAYMENTS_CONFIG_PATH = Path("config/payments.json")


class PaymentMethodModal(discord.ui.Modal, title="Add/Edit Payment Method"):
    """Modal for adding or editing payment methods."""
    
    def __init__(self, existing_method: Optional[dict] = None):
        super().__init__()
        self.existing_method = existing_method
        
        self.name_input = discord.ui.TextInput(
            label="Payment Method Name",
            placeholder="e.g., Binance, PayPal, Bitcoin",
            default=existing_method.get("name", "") if existing_method else "",
            required=True,
            max_length=50
        )
        self.add_item(self.name_input)
        
        self.instructions_input = discord.ui.TextInput(
            label="Instructions",
            placeholder="User-facing instructions for this payment method",
            style=discord.TextStyle.paragraph,
            default=existing_method.get("instructions", "") if existing_method else "",
            required=True,
            max_length=500
        )
        self.add_item(self.instructions_input)
        
        self.emoji_input = discord.ui.TextInput(
            label="Emoji",
            placeholder="e.g., 💳, 🟡, 💰 (optional)",
            default=existing_method.get("emoji", "") if existing_method else "",
            required=False,
            max_length=10
        )
        self.add_item(self.emoji_input)
        
        self.metadata_input = discord.ui.TextInput(
            label="Metadata (JSON)",
            placeholder='{"type": "internal", "pay_id": "123"} or {}',
            style=discord.TextStyle.paragraph,
            default=json.dumps(existing_method.get("metadata", {}), indent=2) if existing_method else "{}",
            required=False,
            max_length=1000
        )
        self.add_item(self.metadata_input)
    
    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Process payment method submission."""
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        try:
            # Parse metadata
            try:
                metadata = json.loads(self.metadata_input.value) if self.metadata_input.value.strip() else {}
            except json.JSONDecodeError:
                await interaction.followup.send(
                    "❌ Invalid JSON in metadata field. Please check your syntax.",
                    ephemeral=True
                )
                return
            
            # Load current payment methods
            if PAYMENTS_CONFIG_PATH.exists():
                with open(PAYMENTS_CONFIG_PATH, 'r') as f:
                    config = json.load(f)
            else:
                config = {"payment_methods": []}
            
            payment_method = {
                "name": self.name_input.value.strip(),
                "instructions": self.instructions_input.value.strip(),
                "emoji": self.emoji_input.value.strip() if self.emoji_input.value.strip() else None,
                "is_enabled": True,
                "metadata": metadata
            }
            
            # Update or add
            if self.existing_method:
                # Find and update existing
                for i, method in enumerate(config["payment_methods"]):
                    if method.get("name") == self.existing_method.get("name"):
                        config["payment_methods"][i] = payment_method
                        break
                action = "updated"
            else:
                # Add new
                config["payment_methods"].append(payment_method)
                action = "added"
            
            # Save to file
            PAYMENTS_CONFIG_PATH.parent.mkdir(exist_ok=True)
            with open(PAYMENTS_CONFIG_PATH, 'w') as f:
                json.dump(config, f, indent=2)
            
            # Reload bot config
            from bot import ApexCoreBot
            if isinstance(interaction.client, ApexCoreBot):
                await interaction.client.reload_config()
            
            embed = create_embed(
                title=f"✅ Payment Method {action.title()}!",
                description=(
                    f"**Name:** {payment_method['name']}\n"
                    f"**Emoji:** {payment_method.get('emoji', 'None')}\n"
                    f"**Enabled:** {payment_method.get('is_enabled', True)}\n\n"
                    f"The payment method has been {action} and the bot config has been reloaded."
                ),
                color=discord.Color.green(),
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"Payment method {action} | Name: {payment_method['name']} | Admin: {interaction.user.id}")
            
        except Exception as e:
            logger.error(f"Error managing payment method: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )


class PaymentManagementCog(commands.Cog):
    """Admin commands for managing payment methods."""
    
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
    
    @app_commands.command(name="addpayment", description="Add a new payment method (admin only)")
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    @admin_only()
    async def add_payment_method(self, interaction: discord.Interaction) -> None:
        """Add a new payment method."""
        modal = PaymentMethodModal()
        await interaction.response.send_modal(modal)
    
    @app_commands.command(name="editpayment", description="Edit an existing payment method (admin only)")
    @app_commands.guild_only()
    @admin_only()
    async def edit_payment_method(
        self, 
        interaction: discord.Interaction,
        method_name: str
    ) -> None:
        """Edit an existing payment method."""
        # Load payment methods (fast local file read; no need to defer)
        if not PAYMENTS_CONFIG_PATH.exists():
            await interaction.response.send_message(
                "❌ No payment methods found. Use `/addpayment` to create one.",
                ephemeral=True,
            )
            return

        with open(PAYMENTS_CONFIG_PATH, "r") as f:
            config = json.load(f)

        method = None
        for candidate in config.get("payment_methods", []):
            if candidate.get("name", "").lower() == method_name.lower():
                method = candidate
                break

        if not method:
            await interaction.response.send_message(
                f"❌ Payment method '{method_name}' not found.",
                ephemeral=True,
            )
            return

        modal = PaymentMethodModal(existing_method=method)
        await interaction.response.send_modal(modal)
    
    @app_commands.command(name="removepayment", description="Remove a payment method (admin only)")
    @app_commands.guild_only()
    @admin_only()
    async def remove_payment_method(
        self,
        interaction: discord.Interaction,
        method_name: str
    ) -> None:
        """Remove a payment method."""
        
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        # Load payment methods
        if not PAYMENTS_CONFIG_PATH.exists():
            await interaction.followup.send(
                "❌ No payment methods found.",
                ephemeral=True
            )
            return
        
        with open(PAYMENTS_CONFIG_PATH, 'r') as f:
            config = json.load(f)
        
        # Remove method
        original_count = len(config.get("payment_methods", []))
        config["payment_methods"] = [
            m for m in config.get("payment_methods", [])
            if m.get("name", "").lower() != method_name.lower()
        ]
        
        if len(config["payment_methods"]) == original_count:
            await interaction.followup.send(
                f"❌ Payment method '{method_name}' not found.",
                ephemeral=True
            )
            return
        
        # Save
        with open(PAYMENTS_CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=2)
        
        # Reload bot config
        from bot import ApexCoreBot
        if isinstance(interaction.client, ApexCoreBot):
            await interaction.client.reload_config()
        
        embed = create_embed(
            title="✅ Payment Method Removed",
            description=f"**{method_name}** has been removed from payment methods.",
            color=discord.Color.green(),
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        logger.info(f"Payment method removed | Name: {method_name} | Admin: {interaction.user.id}")
    
    @app_commands.command(name="listpayments", description="List all payment methods (admin only)")
    @app_commands.guild_only()
    @admin_only()
    async def list_payment_methods(self, interaction: discord.Interaction) -> None:
        """List all payment methods."""
        
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        # Load payment methods
        if not PAYMENTS_CONFIG_PATH.exists():
            await interaction.followup.send(
                "❌ No payment methods configured.",
                ephemeral=True
            )
            return
        
        with open(PAYMENTS_CONFIG_PATH, 'r') as f:
            config = json.load(f)
        
        methods = config.get("payment_methods", [])
        
        if not methods:
            await interaction.followup.send(
                "❌ No payment methods found.",
                ephemeral=True
            )
            return
        
        embed = create_embed(
            title="💳 Payment Methods",
            description=f"**Total:** {len(methods)} payment method(s)\n\n━━━━━━━━━━━━━━━━━━━━━━━━",
            color=discord.Color.blue(),
        )
        
        for i, method in enumerate(methods, 1):
            emoji = method.get("emoji", "💰")
            name = method.get("name", "Unknown")
            enabled = "✅" if method.get("is_enabled", True) else "❌"
            metadata = method.get("metadata", {})
            
            embed.add_field(
                name=f"{emoji} {name} {enabled}",
                value=(
                    f"**Instructions:** {method.get('instructions', 'N/A')[:100]}...\n"
                    f"**Metadata:** {json.dumps(metadata) if metadata else 'None'}"
                ),
                inline=False
            )
        
        embed.set_footer(text="✨ Use /editpayment or /removepayment to manage")
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="togglepayment", description="Enable/disable a payment method (admin only)")
    @app_commands.guild_only()
    @admin_only()
    async def toggle_payment_method(
        self,
        interaction: discord.Interaction,
        method_name: str
    ) -> None:
        """Toggle payment method enabled/disabled."""
        
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        # Load payment methods
        if not PAYMENTS_CONFIG_PATH.exists():
            await interaction.followup.send(
                "❌ No payment methods found.",
                ephemeral=True
            )
            return
        
        with open(PAYMENTS_CONFIG_PATH, 'r') as f:
            config = json.load(f)
        
        # Find and toggle
        found = False
        for method in config.get("payment_methods", []):
            if method.get("name", "").lower() == method_name.lower():
                method["is_enabled"] = not method.get("is_enabled", True)
                new_status = "enabled" if method["is_enabled"] else "disabled"
                found = True
                break
        
        if not found:
            await interaction.followup.send(
                f"❌ Payment method '{method_name}' not found.",
                ephemeral=True
            )
            return
        
        # Save
        with open(PAYMENTS_CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=2)
        
        # Reload bot config
        from bot import ApexCoreBot
        if isinstance(interaction.client, ApexCoreBot):
            await interaction.client.reload_config()
        
        embed = create_embed(
            title="✅ Payment Method Updated",
            description=f"**{method_name}** has been **{new_status}**.",
            color=discord.Color.green(),
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        logger.info(f"Payment method toggled | Name: {method_name} | Status: {new_status} | Admin: {interaction.user.id}")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PaymentManagementCog(bot))

