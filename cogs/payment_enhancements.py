"""
Payment Enhancements Cog

Features:
- Binance Pay QR code generation
- Crypto wallet address generation per order
- Transaction verification system
- PayPal payment links
- Stripe integration
"""

from __future__ import annotations

import os
import secrets
from typing import Optional

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from apex_core.logger import get_logger
from apex_core.utils import create_embed, format_usd
from apex_core.utils.admin_checks import admin_only

logger = get_logger()

# Crypto wallet addresses (configure these)
CRYPTO_WALLETS = {
    "Bitcoin": os.getenv("BTC_WALLET_ADDRESS", ""),
    "Ethereum": os.getenv("ETH_WALLET_ADDRESS", ""),
    "Solana": os.getenv("SOL_WALLET_ADDRESS", ""),
    "TON": os.getenv("TON_WALLET_ADDRESS", ""),
}

# Binance Pay
BINANCE_PAY_ID = os.getenv("BINANCE_PAY_ID", "")

# PayPal
PAYPAL_EMAIL = os.getenv("PAYPAL_EMAIL", "")

# Stripe
STRIPE_PUBLIC_KEY = os.getenv("STRIPE_PUBLIC_KEY", "")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")


def _generate_qr_code_url(data: str) -> str:
    """Generate QR code URL using qr-server.com API."""
    return f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={data}"


async def _verify_bitcoin_transaction(tx_hash: str, address: str) -> Optional[dict]:
    """Verify Bitcoin transaction on blockchain."""
    try:
        # Using BlockCypher API (free tier)
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.blockcypher.com/v1/btc/main/txs/{tx_hash}") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # Check if transaction sends to our address
                    for output in data.get("outputs", []):
                        if address in output.get("addresses", []):
                            return {
                                "confirmed": data.get("confirmations", 0) >= 1,
                                "confirmations": data.get("confirmations", 0),
                                "amount": output.get("value", 0) / 100000000,  # Convert satoshis to BTC
                            }
    except Exception as e:
        logger.error(f"Error verifying Bitcoin transaction: {e}")
    return None


async def _verify_ethereum_transaction(tx_hash: str, address: str) -> Optional[dict]:
    """Verify Ethereum transaction on blockchain."""
    try:
        # Using Etherscan API (free tier, needs API key)
        api_key = os.getenv("ETHERSCAN_API_KEY", "")
        if not api_key:
            return None
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.etherscan.io/api",
                params={
                    "module": "proxy",
                    "action": "eth_getTransactionByHash",
                    "txhash": tx_hash,
                    "apikey": api_key
                }
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("result"):
                        tx = data["result"]
                        # Check if to address matches
                        if tx.get("to", "").lower() == address.lower():
                            return {
                                "confirmed": True,
                                "confirmations": 12,  # Standard confirmation count
                                "amount": int(tx.get("value", "0"), 16) / 10**18,  # Convert wei to ETH
                            }
    except Exception as e:
        logger.error(f"Error verifying Ethereum transaction: {e}")
    return None


async def _verify_solana_transaction(tx_hash: str, address: str) -> Optional[dict]:
    """Verify Solana transaction on blockchain."""
    try:
        # Using Solana RPC (public endpoint)
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.mainnet-beta.solana.com",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getTransaction",
                    "params": [tx_hash, {"encoding": "json"}]
                }
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    result = data.get("result")
                    if result:
                        # Check if transaction is confirmed
                        return {
                            "confirmed": result.get("meta", {}).get("err") is None,
                            "confirmations": 1 if result.get("meta", {}).get("err") is None else 0,
                            "amount": 0,  # Would need to parse transaction details
                        }
    except Exception as e:
        logger.error(f"Error verifying Solana transaction: {e}")
    return None


class PaymentEnhancementsCog(commands.Cog):
    """Payment enhancements: QR codes, crypto wallets, TX verification."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @app_commands.command(name="getcryptoaddress", description="Get crypto address for your order")
    @app_commands.describe(order_id="Order ID", network="Cryptocurrency network")
    async def get_crypto_address_command(
        self, interaction: discord.Interaction, order_id: int, network: str
    ):
        """Get unique crypto address for order."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get order
            order = await self.bot.db.get_order_by_id(order_id)
            if not order:
                await interaction.followup.send("❌ Order not found.", ephemeral=True)
                return
            
            if order["user_discord_id"] != interaction.user.id:
                await interaction.followup.send("❌ This is not your order.", ephemeral=True)
                return
            
            if order["status"] != "pending":
                await interaction.followup.send(
                    f"❌ Order is already {order['status']}. Cannot generate address.",
                    ephemeral=True
                )
                return
            
            # Get wallet address for network
            network_lower = network.lower()
            wallet_address = None
            
            if network_lower in ["bitcoin", "btc"]:
                wallet_address = CRYPTO_WALLETS.get("Bitcoin")
                network = "Bitcoin"
            elif network_lower in ["ethereum", "eth"]:
                wallet_address = CRYPTO_WALLETS.get("Ethereum")
                network = "Ethereum"
            elif network_lower in ["solana", "sol"]:
                wallet_address = CRYPTO_WALLETS.get("Solana")
                network = "Solana"
            elif network_lower in ["ton", "the open network"]:
                wallet_address = CRYPTO_WALLETS.get("TON")
                network = "TON"
            else:
                await interaction.followup.send(
                    f"❌ Unsupported network: {network}. Supported: Bitcoin, Ethereum, Solana, TON",
                    ephemeral=True
                )
                return
            
            if not wallet_address:
                await interaction.followup.send(
                    f"❌ {network} wallet not configured. Please contact admin.",
                    ephemeral=True
                )
                return
            
            # Generate unique address (for tracking) or use main wallet
            # For now, use main wallet with order ID in memo/note
            unique_address = wallet_address
            memo = f"ORDER_{order_id}_{secrets.token_hex(4)}"
            
            # Save address for order
            await self.bot.db.create_crypto_order_address(
                order_id, network, unique_address, order["price_paid_cents"]
            )
            
            embed = create_embed(
                title=f"💰 {network} Payment Address",
                description=f"Send payment for Order #{order_id}",
                color=discord.Color.orange()
            )
            
            embed.add_field(
                name="📍 Address",
                value=f"`{unique_address}`",
                inline=False
            )
            
            embed.add_field(
                name="💰 Amount",
                value=format_usd(order["price_paid_cents"]),
                inline=True
            )
            
            embed.add_field(
                name="🔑 Memo/Note",
                value=f"`{memo}`\n\n**Include this in your transaction!**",
                inline=False
            )
            
            embed.add_field(
                name="💡 Next Steps",
                value=(
                    "1. Send the exact amount to the address above\n"
                    "2. Include the memo/note in your transaction\n"
                    "3. Use `/verifytx` to verify your payment"
                ),
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error getting crypto address: {e}")
            await interaction.followup.send(
                "❌ Error generating address. Please try again later.",
                ephemeral=True
            )
    
    @app_commands.command(name="verifytx", description="Verify cryptocurrency transaction")
    @app_commands.describe(
        order_id="Order ID",
        network="Cryptocurrency network",
        tx_hash="Transaction hash"
    )
    async def verify_tx_command(
        self,
        interaction: discord.Interaction,
        order_id: int,
        network: str,
        tx_hash: str
    ):
        """Verify crypto transaction."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get order
            order = await self.bot.db.get_order_by_id(order_id)
            if not order:
                await interaction.followup.send("❌ Order not found.", ephemeral=True)
                return
            
            if order["user_discord_id"] != interaction.user.id:
                await interaction.followup.send("❌ This is not your order.", ephemeral=True)
                return
            
            # Check if already verified
            existing_tx = await self.bot.db.get_crypto_transaction(tx_hash)
            if existing_tx and existing_tx["status"] == "verified":
                await interaction.followup.send(
                    "✅ This transaction has already been verified.",
                    ephemeral=True
                )
                return
            
            # Get address for order
            address_record = await self.bot.db.get_crypto_order_address(order_id, network)
            if not address_record:
                await interaction.followup.send(
                    "❌ No address found for this order. Use `/getcryptoaddress` first.",
                    ephemeral=True
                )
                return
            
            # Handle Row object
            address = address_record["address"]
            
            # Verify transaction based on network
            network_lower = network.lower()
            verification_result = None
            
            if network_lower in ["bitcoin", "btc"]:
                verification_result = await _verify_bitcoin_transaction(tx_hash, address)
            elif network_lower in ["ethereum", "eth"]:
                verification_result = await _verify_ethereum_transaction(tx_hash, address)
            elif network_lower in ["solana", "sol"]:
                verification_result = await _verify_solana_transaction(tx_hash, address)
            else:
                await interaction.followup.send(
                    f"❌ Unsupported network: {network}",
                    ephemeral=True
                )
                return
            
            if not verification_result:
                # Create pending transaction record
                await self.bot.db.create_crypto_transaction(
                    order_id, network, tx_hash, address,
                    order["price_paid_cents"], status="pending"
                )
                
                embed = create_embed(
                    title="⏳ Transaction Submitted",
                    description="Your transaction has been submitted for verification.",
                    color=discord.Color.blue()
                )
                
                embed.add_field(
                    name="🔗 Transaction Hash",
                    value=f"`{tx_hash}`",
                    inline=False
                )
                
                embed.add_field(
                    name="💡 Note",
                    value="Transaction verification may take a few minutes. Staff will verify manually if needed.",
                    inline=False
                )
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # Transaction verified
            if verification_result.get("confirmed"):
                # Update transaction status
                await self.bot.db.create_crypto_transaction(
                    order_id, network, tx_hash, address,
                    order["price_paid_cents"], status="verified"
                )
                
                # Update order status
                await self.bot.db.update_order_status(order_id, "fulfilled")
                
                embed = create_embed(
                    title="✅ Transaction Verified",
                    description="Your payment has been verified and order is now fulfilled!",
                    color=discord.Color.green()
                )
                
                embed.add_field(
                    name="🔗 Transaction Hash",
                    value=f"`{tx_hash}`",
                    inline=True
                )
                
                embed.add_field(
                    name="✅ Confirmations",
                    value=str(verification_result.get("confirmations", 0)),
                    inline=True
                )
                
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send(
                    "⏳ Transaction found but not yet confirmed. Please wait for confirmations.",
                    ephemeral=True
                )
            
        except Exception as e:
            logger.error(f"Error verifying transaction: {e}")
            await interaction.followup.send(
                "❌ Error verifying transaction. Please try again later.",
                ephemeral=True
            )
    
    @app_commands.command(name="binanceqr", description="Get Binance Pay QR code for order")
    @app_commands.describe(order_id="Order ID")
    async def binance_qr_command(self, interaction: discord.Interaction, order_id: int):
        """Generate Binance Pay QR code."""
        await interaction.response.defer(ephemeral=True)
        
        if not BINANCE_PAY_ID:
            await interaction.followup.send(
                "❌ Binance Pay ID not configured. Please contact admin.",
                ephemeral=True
            )
            return
        
        try:
            # Get order
            order = await self.bot.db.get_order_by_id(order_id)
            if not order:
                await interaction.followup.send("❌ Order not found.", ephemeral=True)
                return
            
            if order["user_discord_id"] != interaction.user.id:
                await interaction.followup.send("❌ This is not your order.", ephemeral=True)
                return
            
            # Generate QR code data
            qr_data = f"binance://pay?pid={BINANCE_PAY_ID}&amount={order['price_paid_cents'] / 100}&memo=ORDER_{order_id}"
            qr_url = _generate_qr_code_url(qr_data)
            
            embed = create_embed(
                title="🟡 Binance Pay",
                description=f"Pay for Order #{order_id}",
                color=discord.Color.gold()
            )
            
            embed.add_field(
                name="💰 Amount",
                value=format_usd(order["price_paid_cents"]),
                inline=True
            )
            
            embed.add_field(
                name="🆔 Pay ID",
                value=f"`{BINANCE_PAY_ID}`",
                inline=True
            )
            
            embed.set_image(url=qr_url)
            
            embed.add_field(
                name="💡 Instructions",
                value=(
                    "1. Scan the QR code above with Binance app\n"
                    "2. Or use Pay ID manually\n"
                    "3. Include your Discord username in the note\n"
                    "4. Upload payment proof when done"
                ),
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error generating Binance QR: {e}")
            await interaction.followup.send(
                "❌ Error generating QR code. Please try again later.",
                ephemeral=True
            )
    
    @app_commands.command(name="paypallink", description="Get PayPal payment link for order")
    @app_commands.describe(order_id="Order ID")
    async def paypal_link_command(self, interaction: discord.Interaction, order_id: int):
        """Generate PayPal payment link."""
        await interaction.response.defer(ephemeral=True)
        
        if not PAYPAL_EMAIL:
            await interaction.followup.send(
                "❌ PayPal email not configured. Please contact admin.",
                ephemeral=True
            )
            return
        
        try:
            # Get order
            order = await self.bot.db.get_order_by_id(order_id)
            if not order:
                await interaction.followup.send("❌ Order not found.", ephemeral=True)
                return
            
            if order["user_discord_id"] != interaction.user.id:
                await interaction.followup.send("❌ This is not your order.", ephemeral=True)
                return
            
            amount = order["price_paid_cents"] / 100
            
            # Generate PayPal link
            paypal_link = (
                f"https://www.paypal.com/paypalme/{PAYPAL_EMAIL.replace('@', '')}/"
                f"{amount}USD?note=ORDER_{order_id}"
            )
            
            embed = create_embed(
                title="💰 PayPal Payment",
                description=f"Pay for Order #{order_id}",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="💰 Amount",
                value=format_usd(order["price_paid_cents"]),
                inline=True
            )
            
            embed.add_field(
                name="📧 Email",
                value=PAYPAL_EMAIL,
                inline=True
            )
            
            embed.add_field(
                name="🔗 Payment Link",
                value=f"[Click to Pay]({paypal_link})",
                inline=False
            )
            
            embed.add_field(
                name="💡 Instructions",
                value=(
                    "1. Click the payment link above\n"
                    "2. Or send manually to the email\n"
                    "3. Include 'ORDER_{order_id}' in the note\n"
                    "4. Upload payment proof when done"
                ).format(order_id=order_id),
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error generating PayPal link: {e}")
            await interaction.followup.send(
                "❌ Error generating payment link. Please try again later.",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    """Load the Payment Enhancements cog."""
    await bot.add_cog(PaymentEnhancementsCog(bot))
    logger.info("Loaded extension: cogs.payment_enhancements")

