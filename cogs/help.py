"""Enhanced help command with detailed categories and pagination."""

from __future__ import annotations

from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from apex_core.logger import get_logger
from apex_core.utils import create_embed
from apex_core.utils.permissions import is_admin_from_bot

logger = get_logger()


class HelpCategoryView(discord.ui.View):
    """View for navigating help categories."""
    
    def __init__(self, cog, user: discord.User, guild: Optional[discord.Guild]):
        super().__init__(timeout=300)
        self.cog = cog
        self.user = user
        self.guild = guild
        self.current_page = 0
    
    @discord.ui.button(label="🛍️ Shopping", style=discord.ButtonStyle.primary, row=0)
    async def shopping_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("This is not your help menu.", ephemeral=True)
            return
        await interaction.response.defer()
        await self.cog._show_shopping_help(interaction)
    
    @discord.ui.button(label="💰 Wallet", style=discord.ButtonStyle.primary, row=0)
    async def wallet_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("This is not your help menu.", ephemeral=True)
            return
        await interaction.response.defer()
        await self.cog._show_wallet_help(interaction)
    
    @discord.ui.button(label="💎 Atto", style=discord.ButtonStyle.primary, row=0)
    async def atto_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("This is not your help menu.", ephemeral=True)
            return
        await interaction.response.defer()
        await self.cog._show_atto_help(interaction)
    
    @discord.ui.button(label="🤖 AI Support", style=discord.ButtonStyle.primary, row=1)
    async def ai_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("This is not your help menu.", ephemeral=True)
            return
        await interaction.response.defer()
        await self.cog._show_ai_help(interaction)
    
    @discord.ui.button(label="🎫 Support", style=discord.ButtonStyle.primary, row=1)
    async def support_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("This is not your help menu.", ephemeral=True)
            return
        await interaction.response.defer()
        await self.cog._show_support_help(interaction)
    
    @discord.ui.button(label="⭐ VIP & Rewards", style=discord.ButtonStyle.primary, row=1)
    async def vip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("This is not your help menu.", ephemeral=True)
            return
        await interaction.response.defer()
        await self.cog._show_vip_help(interaction)
    
    @discord.ui.button(label="🔒 Security", style=discord.ButtonStyle.secondary, row=2)
    async def security_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("This is not your help menu.", ephemeral=True)
            return
        await interaction.response.defer()
        await self.cog._show_security_help(interaction)
    
    @discord.ui.button(label="💳 Payments", style=discord.ButtonStyle.secondary, row=2)
    async def payments_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("This is not your help menu.", ephemeral=True)
            return
        await interaction.response.defer()
        await self.cog._show_payments_help(interaction)
    
    @discord.ui.button(label="🎁 Gifts", style=discord.ButtonStyle.secondary, row=2)
    async def gifts_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("This is not your help menu.", ephemeral=True)
            return
        await interaction.response.defer()
        await self.cog._show_gifts_help(interaction)
    
    @discord.ui.button(label="🏠 Main Menu", style=discord.ButtonStyle.success, row=3)
    async def main_menu_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("This is not your help menu.", ephemeral=True)
            return
        await interaction.response.defer()
        await self.cog._show_main_help(interaction)


class EnhancedHelpCog(commands.Cog):
    """Enhanced help command with detailed categories and pagination."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def _is_admin(self, user: discord.User, guild: Optional[discord.Guild]) -> bool:
        """Check if user is admin."""
        return is_admin_from_bot(user, guild, self.bot)

    @app_commands.command(name="help")
    @app_commands.describe(
        command="Specific command to get help for",
        category="Command category to browse (shopping, wallet, atto, ai, support, vip, security, payments, gifts)"
    )
    async def help(
        self,
        interaction: discord.Interaction,
        command: Optional[str] = None,
        category: Optional[str] = None
    ) -> None:
        """Get comprehensive help with bot commands and features."""
        logger.info(f"Help command used | User: {interaction.user.id} | Command: {command} | Category: {category}")
        
        if command:
            await self._show_command_help(interaction, command)
        elif category:
            await self._show_category_help(interaction, category)
        else:
            await self._show_main_help(interaction)

    async def _show_main_help(self, interaction: discord.Interaction) -> None:
        """Show main help page with category navigation."""
        is_admin = self._is_admin(interaction.user, interaction.guild)
        
        embed = create_embed(
            title="📚 Apex Core - Complete Help Guide",
            description=(
                "**Welcome to Apex Core!** 🎉\n\n"
                "This is your comprehensive guide to all bot features and commands.\n"
                "Click the buttons below to explore different categories, or use `/help category:<name>` for specific sections.\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="🛍️ Shopping & Products",
            value=(
                "Browse products, make purchases, manage orders, and more.\n"
                "**Commands:** `/buy`, `/orders`, `/wishlist`, `/addwishlist`, `/searchtag`, `/faq`\n"
                "**Features:** Product catalog, order tracking, wishlist, product search"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💰 Wallet System",
            value=(
                "Manage your wallet balance, deposits, and transactions.\n"
                "**Commands:** `/balance`, `/deposit`, `/transactions`, `/tip`, `/airdrop`\n"
                "**Features:** Internal wallet, instant payments, tips, airdrops"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💎 Atto Integration",
            value=(
                "Instant withdrawal cryptocurrency with amazing bonuses!\n"
                "**Commands:** `/attodeposit`, `/attobalance`, `/attoswap`, `/attopay`, `/attowithdraw`, `/attoprice`\n"
                "**Benefits:** 10% deposit cashback, 2.5% payment discount/cashback, instant withdrawals"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🤖 AI Support System",
            value=(
                "Get AI-powered assistance with questions and product info.\n"
                "**Commands:** `/ai`, `/aiusage`, `/aisubscribe`\n"
                "**Tiers:** Free (10 questions), Premium (50), Ultra (100 + images)"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🎫 Support & Tickets",
            value=(
                "Get help, open tickets, request refunds.\n"
                "**Commands:** `/ticket`, `/submitrefund`\n"
                "**Features:** Support tickets, refund requests, ticket auto-close (48h warning, 49h close)"
            ),
            inline=False
        )
        
        embed.add_field(
            name="⭐ VIP & Rewards",
            value=(
                "Earn VIP tiers, referral rewards, and exclusive benefits.\n"
                "**Commands:** `/profile`, `/invites`, `/setref`\n"
                "**Features:** Automatic VIP tiers, referral cashback, lifetime spending tracking"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💳 Payment Methods",
            value=(
                "Multiple payment options for your convenience.\n"
                "**Commands:** `/getcryptoaddress`, `/verifytx`, `/binanceqr`, `/paypallink`\n"
                "**Methods:** Wallet, Atto, Crypto (BTC/ETH/SOL/TON), Binance Pay, PayPal, Tipbots"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🔒 Security",
            value=(
                "Protect your account with PIN security.\n"
                "**Commands:** `/setpin`, `/verifypin`\n"
                "**Features:** 4-6 digit PIN protection for sensitive operations"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🎁 Gifts & Promo Codes",
            value=(
                "Send gifts and use promo codes for discounts.\n"
                "**Commands:** `/sendgift`, `/claimgift`, `/mygifts`, `/redeem`\n"
                "**Features:** Gift products/wallet, promo code redemption, review system"
            ),
            inline=False
        )
        
        if is_admin:
            embed.add_field(
                name="🔧 Admin Commands",
                value=(
                    "Administrative commands for managing the bot.\n"
                    "Use `/help category:admin` to view all admin commands.\n"
                    "**Includes:** Product management, user management, announcements, backups, and more"
                ),
                inline=False
            )
        
        embed.set_footer(text="Click buttons below to explore categories • Use /help <command> for specific command details")
        
        view = HelpCategoryView(self, interaction.user, interaction.guild)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    async def _show_shopping_help(self, interaction: discord.Interaction) -> None:
        """Show detailed shopping help."""
        embed = create_embed(
            title="🛍️ Shopping & Products - Complete Guide",
            description=(
                "**Browse, purchase, and manage products with ease!**\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="📦 Browse Products",
            value=(
                "**`/buy`** - Browse the complete product catalog\n"
                "• Navigate by category and sub-category\n"
                "• Filter products by quantity/amount\n"
                "• View product details, prices, stock, and reviews\n"
                "• Select products to purchase\n\n"
                "**How it works:**\n"
                "1. Use `/buy` to open the storefront\n"
                "2. Select a category (e.g., Instagram, YouTube)\n"
                "3. Choose a sub-category (e.g., Followers, Likes)\n"
                "4. Browse products and select one to purchase\n"
                "5. Open a ticket to complete your order"
            ),
            inline=False
        )
        
        embed.add_field(
            name="📋 Order Management",
            value=(
                "**`/orders`** - View your complete order history\n"
                "• See all past and current orders\n"
                "• Check order status (pending, fulfilled, refunded)\n"
                "• View order details, prices, and dates\n"
                "• Track warranty expiration dates\n\n"
                "**Order Status:**\n"
                "• ⏳ **Pending** - Awaiting payment/fulfillment\n"
                "• ✅ **Fulfilled** - Order completed\n"
                "• 🔄 **Refill** - Refill requested\n"
                "• ❌ **Refunded** - Order refunded"
            ),
            inline=False
        )
        
        embed.add_field(
            name="⭐ Wishlist",
            value=(
                "**`/wishlist`** - View your saved products\n"
                "**`/addwishlist <product_id>`** - Add product to wishlist\n"
                "**`/removewishlist <product_id>`** - Remove from wishlist\n\n"
                "Save products you're interested in for quick access later!"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🔍 Product Search",
            value=(
                "**`/searchtag <tag>`** - Search products by tag\n"
                "**`/producttags <product_id>`** - View tags for a product\n\n"
                "Find products quickly using tags like 'popular', 'trending', 'new', etc."
            ),
            inline=False
        )
        
        embed.add_field(
            name="❓ FAQ",
            value=(
                "**`/faq`** - Browse frequently asked questions\n\n"
                "Get answers to common questions about products, payments, refunds, and more."
            ),
            inline=False
        )
        
        embed.add_field(
            name="💡 Tips",
            value=(
                "• Use filters to find specific product quantities\n"
                "• Check product reviews before purchasing\n"
                "• Add products to wishlist for later\n"
                "• VIP tiers get automatic discounts\n"
                "• Use promo codes for additional savings"
            ),
            inline=False
        )
        
        view = HelpCategoryView(self, interaction.user, interaction.guild)
        await interaction.edit_original_response(embed=embed, view=view)
    
    async def _show_wallet_help(self, interaction: discord.Interaction) -> None:
        """Show detailed wallet help."""
        embed = create_embed(
            title="💰 Wallet System - Complete Guide",
            description=(
                "**Manage your funds, deposits, and transactions!**\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=discord.Color.gold()
        )
        
        embed.add_field(
            name="💵 Check Balance",
            value=(
                "**`/balance`** - View your wallet balance and stats\n"
                "• Current wallet balance\n"
                "• Total lifetime spending\n"
                "• VIP tier and discount percentage\n"
                "• Referral earnings"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💳 Add Funds",
            value=(
                "**`/deposit`** - Open a deposit ticket\n"
                "• Get payment instructions\n"
                "• Multiple payment methods available\n"
                "• Staff will verify and credit your account\n"
                "• Funds available immediately after verification"
            ),
            inline=False
        )
        
        embed.add_field(
            name="📊 Transaction History",
            value=(
                "**`/transactions`** - View all wallet transactions\n"
                "• See all deposits, withdrawals, purchases\n"
                "• Filter by transaction type\n"
                "• View transaction dates and amounts\n"
                "• Complete transaction ledger"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💸 Tips & Airdrops",
            value=(
                "**`/tip @user <amount> [message]`** - Tip another user\n"
                "• Send funds directly to other users\n"
                "• Include optional message\n"
                "• Instant transfer\n\n"
                "**`/airdrop <amount> <max_claims> [expires_hours] [message]`** - Create airdrop\n"
                "• Create claimable airdrop\n"
                "• Set maximum claims\n"
                "• Optional expiration time\n"
                "• Users claim with `/claimairdrop <code>`"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💡 Wallet Features",
            value=(
                "• **Instant Payments** - Pay for orders instantly with wallet balance\n"
                "• **Secure Storage** - Funds stored safely in database\n"
                "• **Transaction Tracking** - Complete history of all transactions\n"
                "• **VIP Benefits** - Higher tiers get better discounts\n"
                "• **Referral Earnings** - Earn cashback from referrals"
            ),
            inline=False
        )
        
        view = HelpCategoryView(self, interaction.user, interaction.guild)
        await interaction.edit_original_response(embed=embed, view=view)
    
    async def _show_atto_help(self, interaction: discord.Interaction) -> None:
        """Show detailed Atto help."""
        embed = create_embed(
            title="💎 Atto Integration - Complete Guide",
            description=(
                "**Instant withdrawal cryptocurrency with amazing bonuses!**\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=discord.Color.purple()
        )
        
        embed.add_field(
            name="🎁 10% Deposit Cashback",
            value=(
                "**`/attodeposit`** - Get your deposit address\n"
                "• Receive unique deposit address with memo\n"
                "• **Get 10% cashback on ALL deposits!**\n"
                "• Automatic credit to your Atto balance\n"
                "• Instant confirmation (usually < 1 second)\n\n"
                "**How it works:**\n"
                "1. Use `/attodeposit` to get your address\n"
                "2. Send Atto to the address with your memo\n"
                "3. Receive 10% bonus automatically!\n"
                "4. Funds available immediately"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💰 2.5% Payment Bonus",
            value=(
                "**`/attopay <order_id>`** - Pay with Atto\n"
                "• Choose between discount or cashback\n"
                "• **Option 1:** Apply 2.5% discount (pay less)\n"
                "• **Option 2:** Get 2.5% cashback (get money back)\n"
                "• Your choice on every payment!\n\n"
                "**Example:**\n"
                "Order: $100\n"
                "• Discount: Pay $97.50 (save $2.50)\n"
                "• Cashback: Pay $100, get $2.50 back"
            ),
            inline=False
        )
        
        embed.add_field(
            name="⚡ Instant Withdrawal",
            value=(
                "**`/attowithdraw <address> <amount>`** - Withdraw Atto\n"
                "• Withdraw to any Atto address\n"
                "• **Instant withdrawal** - no waiting!\n"
                "• Unlike wallet balance which requires request\n"
                "• Perfect for quick access to funds"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💱 Swap Wallet to Atto",
            value=(
                "**`/attoswap <amount>`** - Convert wallet to Atto\n"
                "• Swap USD wallet balance to Atto\n"
                "• Get current market rate\n"
                "• Instant conversion\n"
                "• Enables instant withdrawal"
            ),
            inline=False
        )
        
        embed.add_field(
            name="📊 Balance & Price",
            value=(
                "**`/attobalance`** - Check your Atto balance\n"
                "• View current balance in USD\n"
                "• See total deposited/withdrawn\n"
                "• Real-time balance updates\n\n"
                "**`/attoprice`** - Check current Atto price\n"
                "• Get live price from XT.com exchange\n"
                "• Price updates in real-time"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💡 Why Use Atto?",
            value=(
                "✅ **10% deposit bonus** - Best in the market!\n"
                "✅ **2.5% payment bonus** - Choose discount or cashback\n"
                "✅ **Instant withdrawals** - No waiting periods\n"
                "✅ **Feeless transactions** - No fees!\n"
                "✅ **Fast confirmations** - Usually < 1 second\n"
                "✅ **Secure** - Blockchain-based security"
            ),
            inline=False
        )
        
        view = HelpCategoryView(self, interaction.user, interaction.guild)
        await interaction.edit_original_response(embed=embed, view=view)
    
    async def _show_ai_help(self, interaction: discord.Interaction) -> None:
        """Show detailed AI help."""
        embed = create_embed(
            title="🤖 AI Support System - Complete Guide",
            description=(
                "**Get AI-powered assistance with questions and product info!**\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="🆓 Free Tier",
            value=(
                "**Model:** Gemini 2.5 Flash-Lite\n"
                "**Questions:** 10 general + 20 product questions per day\n"
                "**Features:**\n"
                "• General knowledge questions\n"
                "• Product information queries\n"
                "• Basic assistance\n"
                "**Cost:** $0 - Completely free!"
            ),
            inline=False
        )
        
        embed.add_field(
            name="⚡ Premium Tier",
            value=(
                "**Model:** Groq Llama 3.1 8B (Blazing Fast)\n"
                "**Questions:** 50 general + 100 product questions per day\n"
                "**Features:**\n"
                "• All free tier features\n"
                "• Faster responses\n"
                "• Enhanced context (order history, balance, VIP tier)\n"
                "• Better product recommendations\n"
                "**Price:** $5-8/month"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💎 Ultra Tier",
            value=(
                "**Model:** Gemini 2.5 Flash (with Image Support)\n"
                "**Questions:** 100 general + 200 product questions per day\n"
                "**Features:**\n"
                "• All premium features\n"
                "• **Image generation and analysis**\n"
                "• 50 images per month\n"
                "• Advanced context injection\n"
                "• Priority support\n"
                "**Price:** $10-15/month"
            ),
            inline=False
        )
        
        embed.add_field(
            name="📝 Commands",
            value=(
                "**`/ai <question>`** - Ask AI assistant\n"
                "• Ask any question\n"
                "• Get product recommendations\n"
                "• General knowledge queries\n"
                "• Image analysis (Ultra tier)\n\n"
                "**`/aiusage`** - Check your AI usage\n"
                "• See questions used today\n"
                "• Check remaining questions\n"
                "• View usage statistics\n\n"
                "**`/aisubscribe <tier>`** - Subscribe to Premium/Ultra\n"
                "• Upgrade your AI tier\n"
                "• Get more questions\n"
                "• Unlock advanced features"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💡 Usage Tips",
            value=(
                "• General questions count toward general cap\n"
                "• Product questions have double cap (e.g., 10 general = 20 product)\n"
                "• Usage resets daily at midnight UTC\n"
                "• Premium/Ultra get enhanced context about your account\n"
                "• Ultra tier can analyze images you upload"
            ),
            inline=False
        )
        
        view = HelpCategoryView(self, interaction.user, interaction.guild)
        await interaction.edit_original_response(embed=embed, view=view)
    
    async def _show_support_help(self, interaction: discord.Interaction) -> None:
        """Show detailed support help."""
        embed = create_embed(
            title="🎫 Support & Tickets - Complete Guide",
            description=(
                "**Get help, open tickets, and request refunds!**\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=discord.Color.orange()
        )
        
        embed.add_field(
            name="🎫 Opening Tickets",
            value=(
                "**`/ticket`** - Open a support ticket\n"
                "• General support tickets\n"
                "• Refund support tickets\n"
                "• Order-related tickets\n\n"
                "**How it works:**\n"
                "1. Click ticket button in support channel\n"
                "2. Fill out ticket form\n"
                "3. Private ticket channel created\n"
                "4. Staff will assist you\n"
                "5. Ticket auto-closes after 48h inactivity"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💰 Refund Requests",
            value=(
                "**`/submitrefund <order_id> [reason]`** - Request refund\n"
                "• Submit refund request for an order\n"
                "• Provide reason for refund\n"
                "• Staff will review and process\n"
                "• Refund policy: 3 days from completion, 10% handling fee"
            ),
            inline=False
        )
        
        embed.add_field(
            name="⏰ Ticket Auto-Close",
            value=(
                "**Inactivity System:**\n"
                "• **48 hours** - Warning message sent\n"
                "• **49 hours** - Ticket automatically closed\n"
                "• Transcript sent to you via DM\n"
                "• Ticket archived for staff records\n\n"
                "**To keep ticket open:**\n"
                "Simply send any message in the ticket channel!"
            ),
            inline=False
        )
        
        embed.add_field(
            name="📜 Ticket Transcripts",
            value=(
                "When tickets are closed:\n"
                "• Full conversation transcript generated\n"
                "• Sent to you via DM\n"
                "• Archived in staff channels\n"
                "• Available for reference"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💡 Support Tips",
            value=(
                "• Be clear and detailed in your ticket\n"
                "• Include order IDs when relevant\n"
                "• Respond to staff questions promptly\n"
                "• Check operating hours for response times\n"
                "• Keep tickets active by responding"
            ),
            inline=False
        )
        
        view = HelpCategoryView(self, interaction.user, interaction.guild)
        await interaction.edit_original_response(embed=embed, view=view)
    
    async def _show_vip_help(self, interaction: discord.Interaction) -> None:
        """Show detailed VIP help."""
        embed = create_embed(
            title="⭐ VIP & Rewards - Complete Guide",
            description=(
                "**Earn VIP tiers, referral rewards, and exclusive benefits!**\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=discord.Color.gold()
        )
        
        embed.add_field(
            name="👑 VIP Tiers",
            value=(
                "**Automatic Assignment Based on Lifetime Spending:**\n\n"
                "• **⭐ Apex Insider** - Entry tier\n"
                "• **💜 Apex VIP** - $100+ spent\n"
                "• **💎 Apex Elite** - $500+ spent\n"
                "• **👑 Apex Legend** - $1,000+ spent\n"
                "• **🌟 Apex Sovereign** - $2,500+ spent\n"
                "• **✨ Apex Zenith** - $5,000+ spent\n\n"
                "**Benefits:**\n"
                "• Automatic discounts (increases with tier)\n"
                "• VIP Lounge channel access\n"
                "• Priority support\n"
                "• Exclusive perks"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💰 Referral System",
            value=(
                "**`/invites`** - Check your referral earnings\n"
                "• See total referrals\n"
                "• View cashback earned\n"
                "• Track referral activity\n\n"
                "**`/setref <referrer>`** - Set your referrer\n"
                "• Link your account to a referrer\n"
                "• Start earning from their purchases\n"
                "• One-time setup"
            ),
            inline=False
        )
        
        embed.add_field(
            name="📊 Profile",
            value=(
                "**`/profile`** - View your complete profile\n"
                "• Wallet balance\n"
                "• Total lifetime spending\n"
                "• Current VIP tier\n"
                "• Discount percentage\n"
                "• Referral statistics\n"
                "• Account creation date"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💡 How to Earn VIP",
            value=(
                "• **Spend money** - Every purchase counts toward lifetime spending\n"
                "• **Automatic promotion** - Tiers assigned automatically\n"
                "• **Permanent** - Once earned, tier is yours\n"
                "• **Stacking** - Higher tiers include lower tier benefits"
            ),
            inline=False
        )
        
        view = HelpCategoryView(self, interaction.user, interaction.guild)
        await interaction.edit_original_response(embed=embed, view=view)
    
    async def _show_security_help(self, interaction: discord.Interaction) -> None:
        """Show detailed security help."""
        embed = create_embed(
            title="🔒 Security - Complete Guide",
            description=(
                "**Protect your account with PIN security!**\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=discord.Color.red()
        )
        
        embed.add_field(
            name="🔐 PIN Security",
            value=(
                "**`/setpin`** - Set or change your PIN\n"
                "• Choose 4-6 digit PIN\n"
                "• Required for sensitive operations\n"
                "• Securely hashed and stored\n\n"
                "**`/verifypin`** - Verify your PIN\n"
                "• Required for certain operations\n"
                "• Protects your funds\n"
                "• Prevents unauthorized access"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🛡️ What's Protected",
            value=(
                "PIN protection applies to:\n"
                "• Large withdrawals\n"
                "• Account changes\n"
                "• Sensitive operations\n"
                "• Fund transfers"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🔑 PIN Recovery",
            value=(
                "**If you forget your PIN:**\n"
                "• Contact staff for PIN reset\n"
                "• Admin can reset your PIN\n"
                "• Identity verification required\n"
                "• Use `/resetpin` (admin only)"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💡 Security Tips",
            value=(
                "• Use a unique PIN (not your Discord PIN)\n"
                "• Don't share your PIN with anyone\n"
                "• Change PIN regularly\n"
                "• Contact staff if you suspect unauthorized access"
            ),
            inline=False
        )
        
        view = HelpCategoryView(self, interaction.user, interaction.guild)
        await interaction.edit_original_response(embed=embed, view=view)
    
    async def _show_payments_help(self, interaction: discord.Interaction) -> None:
        """Show detailed payments help."""
        embed = create_embed(
            title="💳 Payment Methods - Complete Guide",
            description=(
                "**Multiple payment options for your convenience!**\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="💳 Internal Wallet",
            value=(
                "**Instant payments from your wallet balance**\n"
                "• Fastest payment method\n"
                "• No external processing\n"
                "• Use `/deposit` to add funds\n"
                "• Available immediately after deposit"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💎 Atto Cryptocurrency",
            value=(
                "**Best bonuses available!**\n"
                "• 10% deposit cashback\n"
                "• 2.5% payment discount/cashback\n"
                "• Instant withdrawals\n"
                "• Use `/attodeposit` to get started"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🪙 Cryptocurrency (BTC, ETH, SOL, TON)",
            value=(
                "**`/getcryptoaddress <order_id> <network>`** - Get crypto address\n"
                "• Generate unique address for your order\n"
                "• Support for Bitcoin, Ethereum, Solana, TON\n"
                "• Include memo/note in transaction\n\n"
                "**`/verifytx <order_id> <network> <tx_hash>`** - Verify transaction\n"
                "• Submit transaction hash\n"
                "• Automatic blockchain verification\n"
                "• Order fulfilled automatically"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🟡 Binance Pay",
            value=(
                "**`/binanceqr <order_id>`** - Get QR code\n"
                "• Scan QR code with Binance app\n"
                "• Or use Pay ID manually\n"
                "• Include Discord username in note\n"
                "• Upload payment proof when done"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💰 PayPal",
            value=(
                "**`/paypallink <order_id>`** - Get payment link\n"
                "• Click link to pay\n"
                "• Or send manually to email\n"
                "• Include order ID in note\n"
                "• Upload payment proof when done"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🤖 Tipbots (Tip.cc, CryptoJar, Gemma)",
            value=(
                "**Automated payment verification!**\n"
                "• Send tip to bot in ticket channel\n"
                "• Automatic payment detection\n"
                "• Order fulfilled automatically\n"
                "• No manual verification needed"
            ),
            inline=False
        )
        
        view = HelpCategoryView(self, interaction.user, interaction.guild)
        await interaction.edit_original_response(embed=embed, view=view)
    
    async def _show_gifts_help(self, interaction: discord.Interaction) -> None:
        """Show detailed gifts help."""
        embed = create_embed(
            title="🎁 Gifts & Promo Codes - Complete Guide",
            description=(
                "**Send gifts and use promo codes for discounts!**\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=discord.Color.pink()
        )
        
        embed.add_field(
            name="🎁 Sending Gifts",
            value=(
                "**`/sendgift @user <product_id> [message]`** - Send gift\n"
                "• Gift a product to another user\n"
                "• Include optional message\n"
                "• Recipient notified via DM\n\n"
                "**`/mygifts`** - View your gifts\n"
                "• See gifts sent and received\n"
                "• View gift status\n"
                "• Track gift history"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🎟️ Claiming Gifts",
            value=(
                "**`/claimgift <code>`** - Claim a gift\n"
                "• Use gift code to claim\n"
                "• Receive product or wallet funds\n"
                "• One-time use codes"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🎫 Promo Codes",
            value=(
                "**`/redeem <code>`** - Apply promo code\n"
                "• Use during purchase flow\n"
                "• Get discounts on products\n"
                "• Stack with VIP discounts\n"
                "• Limited-time offers available"
            ),
            inline=False
        )
        
        embed.add_field(
            name="⭐ Reviews",
            value=(
                "**`/review <order_id> <rating> [comment]`** - Submit review\n"
                "• Rate products 1-5 stars\n"
                "• Add optional comment\n"
                "• Help other users decide\n\n"
                "**`/myreviews`** - View your reviews\n"
                "• See all reviews you've submitted\n"
                "• Edit or update reviews"
            ),
            inline=False
        )
        
        view = HelpCategoryView(self, interaction.user, interaction.guild)
        await interaction.edit_original_response(embed=embed, view=view)

    async def _show_category_help(self, interaction: discord.Interaction, category: str) -> None:
        """Show help for specific category."""
        category_lower = category.lower()
        
        if category_lower in ["shopping", "products"]:
            await self._show_shopping_help(interaction)
        elif category_lower in ["wallet", "balance"]:
            await self._show_wallet_help(interaction)
        elif category_lower == "atto":
            await self._show_atto_help(interaction)
        elif category_lower in ["ai", "ai support"]:
            await self._show_ai_help(interaction)
        elif category_lower in ["support", "ticket", "tickets"]:
            await self._show_support_help(interaction)
        elif category_lower in ["vip", "rewards", "referral"]:
            await self._show_vip_help(interaction)
        elif category_lower in ["security", "pin"]:
            await self._show_security_help(interaction)
        elif category_lower in ["payment", "payments"]:
            await self._show_payments_help(interaction)
        elif category_lower in ["gift", "gifts", "promo"]:
            await self._show_gifts_help(interaction)
        elif category_lower == "admin":
            if not self._is_admin(interaction.user, interaction.guild):
                await interaction.response.send_message(
                    "🚫 You don't have permission to view admin commands.",
                    ephemeral=True
                )
                return
            
            embed = create_embed(
                title="🔧 Admin Commands",
                description="Administrative commands for managing the bot:",
                color=discord.Color.red()
            )
            
            embed.add_field(
                name="📦 Product Management",
                value=(
                    "`/setstock` - Manage product inventory\n"
                    "`/addstock` - Add stock to product\n"
                    "`/checkstock` - Check stock levels\n"
                    "`/stockalert` - View low stock products\n"
                    "`/addtag` - Add tag to product\n"
                    "`/removetag` - Remove tag from product"
                ),
                inline=False
            )
            
            embed.add_field(
                name="🎟️ Promo Codes",
                value=(
                    "`/createcode` - Create promo code\n"
                    "`/listcodes` - List all codes\n"
                    "`/codeinfo` - View code details\n"
                    "`/deactivatecode` - Deactivate code\n"
                    "`/deletecode` - Delete code"
                ),
                inline=False
            )
            
            embed.add_field(
                name="👥 User Management",
                value=(
                    "`/addbalance` - Add wallet balance\n"
                    "`/balance <member>` - Check member balance\n"
                    "`/orders <member>` - View member orders\n"
                    "`/resetpin` - Reset user PIN"
                ),
                inline=False
            )
            
            embed.add_field(
                name="📦 Order Management",
                value=(
                    "`/updateorderstatus` - Update order status\n"
                    "`/bulkupdateorders` - Bulk update orders"
                ),
                inline=False
            )
            
            embed.add_field(
                name="🎁 Gifts",
                value=(
                    "`/giftproduct` - Gift product to user\n"
                    "`/giftwallet` - Gift wallet balance\n"
                    "`/giftcode` - Generate gift code"
                ),
                inline=False
            )
            
            embed.add_field(
                name="📢 Announcements",
                value=(
                    "`/announce` - Send announcement\n"
                    "`/announcements` - View announcement history\n"
                    "`/testannouncement` - Test announcement"
                ),
                inline=False
            )
            
            embed.add_field(
                name="⭐ Reviews",
                value=(
                    "`/pendingreviews` - View pending reviews\n"
                    "`/approvereview` - Approve review\n"
                    "`/rejectreview` - Reject review\n"
                    "`/reviewstats` - View review statistics"
                ),
                inline=False
            )
            
            embed.add_field(
                name="💳 Payment Management",
                value=(
                    "`/addpayment` - Add payment method\n"
                    "`/editpayment` - Edit payment method\n"
                    "`/removepayment` - Remove payment method\n"
                    "`/listpayments` - List all payment methods\n"
                    "`/togglepayment` - Enable/disable payment method\n"
                    "`/attosetup` - Set Atto main wallet address"
                ),
                inline=False
            )
            
            embed.add_field(
                name="🤖 AI Management",
                value=(
                    "`/aiadmin` - View AI usage statistics"
                ),
                inline=False
            )
            
            embed.add_field(
                name="🔗 Supplier Management",
                value=(
                    "`/importsupplier` - Import products from supplier\n"
                    "`/listsuppliers` - List configured suppliers"
                ),
                inline=False
            )
            
            embed.add_field(
                name="💾 Database",
                value=(
                    "`/backup` - Create database backup\n"
                    "`/listbackups` - List backups\n"
                    "`/exportdata` - Export data to CSV"
                ),
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(
                f"❌ Category '{category}' not found. Use `/help` to see available categories.",
                ephemeral=True
            )

    async def _show_command_help(self, interaction: discord.Interaction, command: str) -> None:
        """Show detailed help for specific command."""
        command_lower = command.lower()
        
        command_details = {
            "buy": {
                "title": "🛍️ /buy - Browse Products",
                "description": "Browse and purchase products from the storefront.",
                "usage": "`/buy`",
                "details": (
                    "Opens an interactive product catalog where you can:\n"
                    "• Browse by category and sub-category\n"
                    "• Filter products by quantity/amount\n"
                    "• View product details, prices, stock, and reviews\n"
                    "• Select products to purchase\n"
                    "• Open order tickets"
                )
            },
            "balance": {
                "title": "💰 /balance - Check Wallet Balance",
                "description": "View your wallet balance and account statistics.",
                "usage": "`/balance` or `/balance @member` (admin)",
                "details": (
                    "Shows:\n"
                    "• Current wallet balance\n"
                    "• Total lifetime spending\n"
                    "• Current VIP tier\n"
                    "• Discount percentage\n"
                    "• Referral earnings"
                )
            },
            "deposit": {
                "title": "💳 /deposit - Add Funds",
                "description": "Open a deposit ticket to add funds to your wallet.",
                "usage": "`/deposit`",
                "details": (
                    "Creates a deposit ticket where you can:\n"
                    "• Get payment instructions\n"
                    "• Choose payment method\n"
                    "• Upload payment proof\n"
                    "• Staff will verify and credit your account"
                )
            },
            "orders": {
                "title": "📦 /orders - Order History",
                "description": "View your complete order history.",
                "usage": "`/orders` or `/orders @member` (admin)",
                "details": (
                    "Shows:\n"
                    "• All past and current orders\n"
                    "• Order status (pending, fulfilled, refunded)\n"
                    "• Order details, prices, and dates\n"
                    "• Warranty expiration dates"
                )
            },
            "ticket": {
                "title": "🎫 /ticket - Support Tickets",
                "description": "Open a support ticket for assistance.",
                "usage": "`/ticket support` or `/ticket refund`",
                "details": (
                    "Creates a private ticket channel where you can:\n"
                    "• Get help from staff\n"
                    "• Request refunds\n"
                    "• Ask questions\n"
                    "• Tickets auto-close after 48h inactivity"
                )
            },
            "atto": {
                "title": "💎 Atto Commands",
                "description": "Atto cryptocurrency integration commands.",
                "usage": "Multiple commands available",
                "details": (
                    "**Available commands:**\n"
                    "• `/attodeposit` - Get deposit address (10% cashback!)\n"
                    "• `/attobalance` - Check balance\n"
                    "• `/attoswap` - Swap wallet to Atto\n"
                    "• `/attopay` - Pay with Atto (2.5% bonus)\n"
                    "• `/attowithdraw` - Withdraw Atto\n"
                    "• `/attoprice` - Check price"
                )
            },
            "ai": {
                "title": "🤖 /ai - AI Assistant",
                "description": "Ask questions to the AI assistant.",
                "usage": "`/ai <question>`",
                "details": (
                    "Get AI-powered assistance with:\n"
                    "• General knowledge questions\n"
                    "• Product recommendations\n"
                    "• Account information (premium tiers)\n"
                    "• Image analysis (Ultra tier)\n\n"
                    "**Tiers:** Free (10 questions), Premium (50), Ultra (100 + images)"
                )
            },
        }
        
        if command_lower in command_details:
            details = command_details[command_lower]
            embed = create_embed(
                title=details["title"],
                description=details["description"],
                color=discord.Color.blue()
            )
            embed.add_field(name="Usage", value=details["usage"], inline=False)
            embed.add_field(name="Details", value=details["details"], inline=False)
        else:
            embed = create_embed(
                title=f"Command: /{command}",
                description=f"Use `/help` to see all available commands and categories.",
                color=discord.Color.blue()
            )
        
        embed.set_footer(text="Use /help to see all commands")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    """Load the EnhancedHelpCog cog."""
    await bot.add_cog(EnhancedHelpCog(bot))
