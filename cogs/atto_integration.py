"""
Atto Cryptocurrency Integration Cog (Main Wallet System)

Features:
- Main wallet for all deposits
- 10% deposit cashback
- 2.5% payment discount/cashback (user choice)
- Deposit monitoring
- Instant withdrawals
"""

from __future__ import annotations

import os
import re
import asyncio
from decimal import Decimal, ROUND_DOWN
from typing import Optional, List
from collections import deque
import time

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks

from apex_core.logger import get_logger
from apex_core.utils import create_embed, format_usd
from apex_core.utils.admin_checks import admin_only

logger = get_logger()

# Atto API endpoints - Support multiple nodes (comma-separated)
ATTO_NODE_APIS_STR = os.getenv("ATTO_NODE_API", "http://localhost:8080")
ATTO_MAIN_WALLET = os.getenv("ATTO_MAIN_WALLET_ADDRESS", "")
ATTO_DEPOSIT_CHECK_INTERVAL = int(os.getenv("ATTO_DEPOSIT_CHECK_INTERVAL", "30"))
XT_API_BASE = "https://api.xt.com/api/v1"

# Cashback rates
DEPOSIT_CASHBACK_PERCENT = 10.0  # 10% on deposits
PAYMENT_DISCOUNT_PERCENT = 2.5  # 2.5% discount or cashback on payments


class AttoNodeManager:
    """Manages multiple Atto node connections with automatic failover."""
    
    def __init__(self, node_urls: str):
        """Initialize with comma-separated node URLs."""
        # Parse node URLs
        urls = [url.strip() for url in node_urls.split(",") if url.strip()]
        if not urls:
            urls = ["http://localhost:8080"]
        
        self.nodes: List[str] = urls
        self.node_queue = deque(urls)  # Round-robin queue
        self.node_health: dict[str, tuple[bool, float]] = {}  # {url: (is_healthy, last_check_time)}
        self.health_check_interval = 60  # Check health every 60 seconds
        self.timeout = aiohttp.ClientTimeout(total=10)  # 10 second timeout per request
        
        logger.info(f"Atto Node Manager initialized with {len(self.nodes)} node(s): {', '.join(self.nodes)}")
    
    async def _check_node_health(self, node_url: str) -> bool:
        """Check if a node is healthy by making a simple request."""
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                # Try to get node info (health check endpoint)
                async with session.get(f"{node_url}/health", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    is_healthy = resp.status == 200
                    self.node_health[node_url] = (is_healthy, time.time())
                    return is_healthy
        except Exception as e:
            logger.debug(f"Node health check failed for {node_url}: {e}")
            self.node_health[node_url] = (False, time.time())
            return False
    
    async def _get_healthy_node(self) -> Optional[str]:
        """Get a healthy node, checking health if needed."""
        # Check health of nodes if needed
        current_time = time.time()
        for node_url in self.nodes:
            if node_url not in self.node_health:
                # First time checking this node
                await self._check_node_health(node_url)
            else:
                is_healthy, last_check = self.node_health[node_url]
                # Re-check if unhealthy or stale
                if not is_healthy or (current_time - last_check) > self.health_check_interval:
                    await self._check_node_health(node_url)
        
        # Try to find a healthy node
        for node_url in self.nodes:
            if self.node_health.get(node_url, (False, 0))[0]:
                return node_url
        
        # If no healthy node found, try the first one anyway (might be temporary issue)
        # Only log if we have nodes configured (avoid spam when Atto not set up)
        if self.nodes and self.nodes[0] != "http://localhost:8080":
            logger.warning("No healthy nodes found, using first node anyway")
        return self.nodes[0] if self.nodes else None
    
    async def request(
        self, 
        method: str, 
        endpoint: str, 
        params: Optional[dict] = None,
        json_data: Optional[dict] = None
    ) -> Optional[dict]:
        """
        Make a request to an Atto node with automatic failover.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (e.g., "/account/history")
            params: Query parameters
            json_data: JSON body for POST requests
            
        Returns:
            JSON data if successful, None if all nodes failed
        """
        # Try each node in order until one succeeds
        attempted_nodes = []
        
        for _ in range(len(self.nodes)):
            node_url = await self._get_healthy_node()
            if not node_url:
                break
            
            if node_url in attempted_nodes:
                # Already tried this node, move to next
                self.node_queue.rotate(1)
                continue
            
            attempted_nodes.append(node_url)
            
            try:
                async with aiohttp.ClientSession(timeout=self.timeout) as session:
                    url = f"{node_url}{endpoint}"
                    
                    if method.upper() == "GET":
                        async with session.get(url, params=params) as resp:
                            if resp.status == 200:
                                logger.debug(f"Request successful to node: {node_url}")
                                data = await resp.json()
                                return data
                            elif resp.status >= 500:
                                # Server error, try next node
                                # Only log if not localhost (avoid spam when Atto not configured)
                                if "localhost" not in node_url:
                                    logger.warning(f"Node {node_url} returned {resp.status}, trying next node")
                                self.node_health[node_url] = (False, time.time())
                                continue
                            else:
                                # Client error (4xx), don't retry
                                error_data = await resp.json() if resp.content_type == 'application/json' else {}
                                logger.warning(f"Node {node_url} returned {resp.status}: {error_data}")
                                return None
                    
                    elif method.upper() == "POST":
                        async with session.post(url, params=params, json=json_data) as resp:
                            if resp.status == 200:
                                logger.debug(f"Request successful to node: {node_url}")
                                data = await resp.json()
                                return data
                            elif resp.status >= 500:
                                # Server error, try next node
                                # Only log if not localhost (avoid spam when Atto not configured)
                                if "localhost" not in node_url:
                                    logger.warning(f"Node {node_url} returned {resp.status}, trying next node")
                                self.node_health[node_url] = (False, time.time())
                                continue
                            else:
                                # Client error (4xx), don't retry
                                error_data = await resp.json() if resp.content_type == 'application/json' else {}
                                logger.warning(f"Node {node_url} returned {resp.status}: {error_data}")
                                return None
                    
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                # Only log if not localhost (avoid spam when Atto not configured)
                if "localhost" not in node_url:
                    logger.warning(f"Request to {node_url} failed: {e}, trying next node")
                self.node_health[node_url] = (False, time.time())
                continue
        
        # Only log error if not localhost (avoid spam when Atto not configured)
        if not any("localhost" in node for node in self.nodes):
            logger.error(f"All {len(self.nodes)} node(s) failed for {method} {endpoint}")
        return None


# Initialize node manager
_node_manager = AttoNodeManager(ATTO_NODE_APIS_STR)


async def _get_atto_price_usd() -> Optional[float]:
    """Get Atto price in USD from XT.com API."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{XT_API_BASE}/ticker/price", params={"symbol": "ATTO_USDT"}) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if "data" in data and "price" in data["data"]:
                        return float(data["data"]["price"])
        return None
    except Exception as e:
        logger.error(f"Error fetching Atto price: {e}")
        return None


async def _get_atto_transactions(address: str, since_hash: Optional[str] = None) -> list[dict]:
    """Get recent transactions for an address from Atto Node API."""
    try:
        params = {"address": address}
        if since_hash:
            params["since"] = since_hash
        
        data = await _node_manager.request("GET", "/account/history", params=params)
        if data:
            return data.get("history", [])
        return []
    except Exception as e:
        logger.error(f"Error fetching Atto transactions: {e}")
        return []


async def _send_atto_transaction(from_address: str, to_address: str, amount_raw: str) -> Optional[str]:
    """Send Atto transaction via Node API."""
    try:
        data = await _node_manager.request(
            "POST",
            f"/accounts/{from_address}/send",
            json_data={
                "destination": to_address,
                "amount": amount_raw
            }
        )
        if data:
            return data.get("hash")
        return None
    except Exception as e:
        logger.error(f"Error sending Atto transaction: {e}")
        return None


def _atto_to_usd(atto_raw: str, price_usd: float) -> int:
    """Convert Atto raw amount to USD cents."""
    try:
        atto_amount = Decimal(atto_raw) / Decimal(10**30)
        usd_amount = float(atto_amount) * price_usd
        return int(usd_amount * 100)
    except Exception as e:
        logger.error(f"Error converting Atto to USD: {e}")
        return 0


def _usd_to_atto(usd_cents: int, price_usd: float) -> str:
    """Convert USD cents to Atto raw units."""
    try:
        usd_amount = usd_cents / 100.0
        atto_amount = usd_amount / price_usd
        raw_units = int(atto_amount * (10**30))
        return str(raw_units)
    except Exception as e:
        logger.error(f"Error converting USD to Atto: {e}")
        return "0"


def _parse_memo(memo: str) -> Optional[int]:
    """Parse user ID from deposit memo (format: USER_123456789)."""
    try:
        if memo.startswith("USER_"):
            user_id = int(memo.replace("USER_", ""))
            return user_id
    except (ValueError, AttributeError):
        pass
    return None


class AttoPaymentChoiceView(discord.ui.View):
    """View for user to choose discount or cashback on Atto payment."""
    
    def __init__(self, cog, order_id: int, order_price_cents: int):
        super().__init__(timeout=300)
        self.cog = cog
        self.order_id = order_id
        self.order_price_cents = order_price_cents
    
    @discord.ui.button(label="Apply 2.5% Discount", style=discord.ButtonStyle.success, emoji="💰")
    async def discount_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await self.cog._process_atto_payment(interaction, self.order_id, self.order_price_cents, "discount")
    
    @discord.ui.button(label="Get 2.5% Cashback", style=discord.ButtonStyle.primary, emoji="🎁")
    async def cashback_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await self.cog._process_atto_payment(interaction, self.order_id, self.order_price_cents, "cashback")


class AttoIntegrationCog(commands.Cog):
    """Atto cryptocurrency integration with main wallet system."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.last_processed_hash: Optional[str] = None
    
    async def cog_load(self) -> None:
        """Start deposit monitoring task."""
        if ATTO_MAIN_WALLET:
            self.deposit_monitor_task.start()
            logger.info("Atto deposit monitoring started")
        else:
            logger.warning("ATTO_MAIN_WALLET_ADDRESS not set - deposit monitoring disabled")
    
    async def cog_unload(self) -> None:
        """Stop deposit monitoring task."""
        self.deposit_monitor_task.cancel()
        logger.info("Atto deposit monitoring stopped")
    
    @tasks.loop(seconds=ATTO_DEPOSIT_CHECK_INTERVAL)
    async def deposit_monitor_task(self):
        """Monitor main wallet for new deposits."""
        if not ATTO_MAIN_WALLET:
            return
        
        try:
            # Get main wallet address from database
            main_address = await self.bot.db.get_main_wallet_address()
            if not main_address:
                main_address = ATTO_MAIN_WALLET
                await self.bot.db.set_main_wallet_address(main_address)
            
            # Get recent transactions (silently fail if no nodes available)
            try:
                transactions = await _get_atto_transactions(main_address, self.last_processed_hash)
            except Exception as e:
                # Only log error once per 5 minutes to avoid spam (Atto not configured yet)
                if not hasattr(self, '_last_atto_error_log') or (time.time() - self._last_atto_error_log) > 300:
                    logger.debug(f"Atto node unavailable (expected if no nodes configured): {type(e).__name__}")
                    self._last_atto_error_log = time.time()
                return
            
            for tx in transactions:
                if tx.get("type") == "receive" and tx.get("memo"):
                    memo = tx.get("memo", "")
                    user_id = _parse_memo(memo)
                    
                    if user_id:
                        amount_raw = tx.get("amount", "0")
                        tx_hash = tx.get("hash", "")
                        
                        # Check if already processed
                        cursor = await self.bot.db._connection.execute(
                            "SELECT id FROM atto_transactions WHERE transaction_hash = ?",
                            (tx_hash,)
                        )
                        if await cursor.fetchone():
                            continue
                        
                        # Calculate cashback (10%)
                        cashback_raw = str(
                            int(
                                (
                                    Decimal(amount_raw)
                                    * Decimal(str(DEPOSIT_CASHBACK_PERCENT))
                                    / Decimal("100")
                                ).to_integral_value(rounding=ROUND_DOWN)
                            )
                        )
                        
                        # Add balance + cashback
                        await self.bot.db.add_atto_balance(user_id, amount_raw, cashback_raw)
                        
                        # Log transaction
                        price_usd = await _get_atto_price_usd()
                        amount_usd_cents = _atto_to_usd(amount_raw, price_usd) if price_usd else 0
                        
                        await self.bot.db.log_atto_transaction(
                            user_id, "deposit", amount_raw, amount_usd_cents,
                            to_address=main_address, transaction_hash=tx_hash, memo=memo,
                            cashback_raw=cashback_raw, status="completed"
                        )
                        
                        # Notify user
                        try:
                            user = await self.bot.fetch_user(user_id)
                            if user:
                                embed = create_embed(
                                    title="✅ Atto Deposit Received",
                                    description=f"Your deposit of {format_usd(amount_usd_cents)} has been credited!",
                                    color=discord.Color.green()
                                )
                                embed.add_field(
                                    name="🎁 Bonus",
                                    value=f"Received {format_usd(_atto_to_usd(cashback_raw, price_usd) if price_usd else 0)} cashback (10%)!",
                                    inline=False
                                )
                                await user.send(embed=embed)
                        except Exception as e:
                            logger.error(f"Failed to notify user {user_id} of deposit: {e}")
                        
                        logger.info(f"Processed Atto deposit: User {user_id}, Amount {amount_raw}, Cashback {cashback_raw}")
                        
                        if tx_hash:
                            self.last_processed_hash = tx_hash
            
        except Exception as e:
            logger.error(f"Error in deposit monitoring: {e}", exc_info=True)
    
    @deposit_monitor_task.before_loop
    async def before_deposit_monitor(self):
        await self.bot.wait_until_ready()
    
    @app_commands.command(name="attodeposit", description="Get deposit address and instructions")
    async def atto_deposit_command(self, interaction: discord.Interaction):
        """Show deposit address and memo for user."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get or create balance record
            balance_row = await self.bot.db.get_atto_balance(interaction.user.id)
            balance = dict(balance_row) if balance_row and not isinstance(balance_row, dict) else balance_row
            if not balance:
                memo = f"USER_{interaction.user.id}"
                await self.bot.db.create_atto_balance(interaction.user.id, memo)
            else:
                memo = balance.get("deposit_memo") or f"USER_{interaction.user.id}"
            
            # Get main wallet address
            main_address = await self.bot.db.get_main_wallet_address()
            if not main_address:
                main_address = ATTO_MAIN_WALLET
                if not main_address:
                    await interaction.followup.send(
                        "❌ Main wallet address not configured. Please contact admin.",
                        ephemeral=True
                    )
                    return
                await self.bot.db.set_main_wallet_address(main_address)
            
            embed = create_embed(
                title="💰 Deposit Atto",
                description="Send Atto to the address below to add funds to your balance.",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="📍 Deposit Address",
                value=f"`{main_address}`",
                inline=False
            )
            
            embed.add_field(
                name="🔑 Memo (REQUIRED)",
                value=f"`{memo}`\n\n**⚠️ IMPORTANT:** Include this memo in your transaction!",
                inline=False
            )
            
            embed.add_field(
                name="🎁 Deposit Bonus",
                value=f"Get **{DEPOSIT_CASHBACK_PERCENT}% cashback** on all deposits!",
                inline=False
            )
            
            embed.add_field(
                name="💡 How to Deposit",
                value=(
                    "1. Send Atto to the address above\n"
                    "2. **Include the memo** in your transaction\n"
                    "3. Wait for confirmation (usually < 1 second)\n"
                    "4. Receive 10% cashback automatically!"
                ),
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in atto deposit command: {e}")
            await interaction.followup.send(
                "❌ Error getting deposit info. Please try again later.",
                ephemeral=True
            )
    
    @app_commands.command(name="attobalance", description="Check your Atto balance")
    async def atto_balance_command(self, interaction: discord.Interaction):
        """Check user's Atto balance."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            balance_row = await self.bot.db.get_atto_balance(interaction.user.id)
            balance = dict(balance_row) if balance_row and not isinstance(balance_row, dict) else balance_row
            
            if not balance:
                balance_raw = "0"
                total_deposited = "0"
                total_withdrawn = "0"
            else:
                balance_raw = balance.get("balance_raw") or "0"
                total_deposited = balance.get("total_deposited_raw") or "0"
                total_withdrawn = balance.get("total_withdrawn_raw") or "0"
            
            # Get price and convert
            price_usd = await _get_atto_price_usd()
            if price_usd:
                balance_usd_cents = _atto_to_usd(balance_raw, price_usd)
                balance_usd = format_usd(balance_usd_cents)
                deposited_usd = format_usd(_atto_to_usd(total_deposited, price_usd))
                withdrawn_usd = format_usd(_atto_to_usd(total_withdrawn, price_usd))
            else:
                balance_usd = "Price unavailable"
                deposited_usd = "N/A"
                withdrawn_usd = "N/A"
            
            embed = create_embed(
                title="💰 Your Atto Balance",
                description=f"**Balance:** {balance_usd}",
                color=discord.Color.green()
            )
            
            embed.add_field(name="💵 Total Deposited", value=deposited_usd, inline=True)
            embed.add_field(name="💸 Total Withdrawn", value=withdrawn_usd, inline=True)
            
            embed.add_field(
                name="💡 Quick Actions",
                value=(
                    "`/attodeposit` - Get deposit address\n"
                    "`/attoswap` - Swap wallet to Atto\n"
                    "`/attopay` - Pay with Atto (2.5% discount/cashback)\n"
                    "`/attowithdraw` - Withdraw Atto"
                ),
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error checking Atto balance: {e}")
            await interaction.followup.send(
                "❌ Error checking Atto balance. Please try again later.",
                ephemeral=True
            )
    
    @app_commands.command(name="attoswap", description="Swap wallet balance to Atto (instant withdrawal)")
    @app_commands.describe(amount="Amount in USD to swap to Atto")
    async def atto_swap_command(self, interaction: discord.Interaction, amount: float):
        """Swap wallet balance to Atto."""
        await interaction.response.defer(ephemeral=True)
        
        if amount <= 0:
            await interaction.followup.send("❌ Amount must be greater than 0.", ephemeral=True)
            return
        
        amount_cents = int(amount * 100)
        
        try:
            # Check user balance
            user = await self.bot.db.get_user(interaction.user.id)
            if not user:
                await interaction.followup.send("❌ User not found.", ephemeral=True)
                return
            
            balance_cents = user.get("wallet_balance_cents", 0)
            if balance_cents < amount_cents:
                await interaction.followup.send(
                    f"❌ Insufficient balance. You have {format_usd(balance_cents)}.",
                    ephemeral=True
                )
                return
            
            # Get Atto price
            price_usd = await _get_atto_price_usd()
            if not price_usd:
                await interaction.followup.send(
                    "❌ Unable to fetch Atto price. Please try again later.",
                    ephemeral=True
                )
                return
            
            # Calculate Atto amount
            atto_raw = _usd_to_atto(amount_cents, price_usd)
            
            # Deduct from wallet
            await self.bot.db.add_wallet_balance(interaction.user.id, -amount_cents, "atto_swap")
            
            # Add to Atto balance
            await self.bot.db.add_atto_balance(interaction.user.id, atto_raw, "0")
            
            # Log swap
            await self.bot.db.log_atto_swap(
                interaction.user.id, "USD", "ATTO", amount_cents, atto_raw, price_usd
            )
            
            embed = create_embed(
                title="✅ Swap Complete",
                description=f"Swapped {format_usd(amount_cents)} to Atto",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="💰 Atto Received",
                value=f"{format_usd(_atto_to_usd(atto_raw, price_usd))}",
                inline=True
            )
            
            embed.add_field(
                name="💵 Exchange Rate",
                value=f"${price_usd:.6f} per Atto",
                inline=True
            )
            
            embed.add_field(
                name="💡 Note",
                value="Atto balance can be withdrawn instantly! Use `/attowithdraw` to withdraw.",
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error swapping to Atto: {e}")
            await interaction.followup.send(
                "❌ Error processing swap. Please try again later.",
                ephemeral=True
            )
    
    @app_commands.command(name="attopay", description="Pay for order with Atto (2.5% discount or cashback)")
    @app_commands.describe(order_id="Order ID to pay for")
    async def atto_pay_command(self, interaction: discord.Interaction, order_id: int):
        """Pay for order with Atto - user chooses discount or cashback."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get order
            order_row = await self.bot.db.get_order_by_id(order_id)
            order = dict(order_row) if order_row and not isinstance(order_row, dict) else order_row
            if not order:
                await interaction.followup.send("❌ Order not found.", ephemeral=True)
                return
            
            if order["user_discord_id"] != interaction.user.id:
                await interaction.followup.send("❌ This is not your order.", ephemeral=True)
                return
            
            if order["status"] != "pending":
                await interaction.followup.send(
                    f"❌ Order is already {order['status']}. Cannot pay.",
                    ephemeral=True
                )
                return
            
            order_price_cents = int(order.get("price_paid_cents") or 0)
            
            # Show choice view
            embed = create_embed(
                title="💎 Pay with Atto",
                description=f"Order #{order_id}: {format_usd(order_price_cents)}",
                color=discord.Color.gold()
            )
            
            embed.add_field(
                name="💰 Option 1: Apply 2.5% Discount",
                value=f"Pay: {format_usd(int(order_price_cents * 0.975))} (Save {format_usd(int(order_price_cents * 0.025))})",
                inline=False
            )
            
            embed.add_field(
                name="🎁 Option 2: Get 2.5% Cashback",
                value=f"Pay: {format_usd(order_price_cents)} (Get {format_usd(int(order_price_cents * 0.025))} back)",
                inline=False
            )
            
            view = AttoPaymentChoiceView(self, order_id, order_price_cents)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in atto pay command: {e}")
            await interaction.followup.send(
                "❌ Error processing payment. Please try again later.",
                ephemeral=True
            )
    
    async def _process_atto_payment(
        self, interaction: discord.Interaction, order_id: int, 
        order_price_cents: int, choice: str
    ):
        """Process Atto payment with user's choice."""
        try:
            # Get order
            order_row = await self.bot.db.get_order_by_id(order_id)
            order = dict(order_row) if order_row and not isinstance(order_row, dict) else order_row
            if not order or order["user_discord_id"] != interaction.user.id:
                await interaction.followup.send("❌ Order not found.", ephemeral=True)
                return
            
            # Get Atto balance
            balance_row = await self.bot.db.get_atto_balance(interaction.user.id)
            balance = dict(balance_row) if balance_row and not isinstance(balance_row, dict) else balance_row
            if not balance:
                await interaction.followup.send(
                    "❌ No Atto balance. Use `/attodeposit` to add funds.",
                    ephemeral=True
                )
                return
            
            balance_raw = balance.get("balance_raw", "0")
            
            # Get price
            price_usd = await _get_atto_price_usd()
            if not price_usd:
                await interaction.followup.send(
                    "❌ Unable to fetch Atto price. Please try again later.",
                    ephemeral=True
                )
                return
            
            # Calculate payment amount based on choice
            if choice == "discount":
                # Apply 2.5% discount
                final_price_cents = int(order_price_cents * (1 - PAYMENT_DISCOUNT_PERCENT / 100))
                cashback_cents = 0
            else:
                # Get 2.5% cashback
                final_price_cents = order_price_cents
                cashback_cents = int(order_price_cents * (PAYMENT_DISCOUNT_PERCENT / 100))
            
            # Convert to Atto
            required_atto_raw = _usd_to_atto(final_price_cents, price_usd)
            
            # Check balance
            if int(balance_raw) < int(required_atto_raw):
                await interaction.followup.send(
                    "❌ Insufficient Atto balance. Use `/attodeposit` or `/attoswap` to add funds.",
                    ephemeral=True
                )
                return
            
            # Deduct Atto balance
            await self.bot.db.deduct_atto_balance(interaction.user.id, required_atto_raw)
            
            # Add cashback if chosen
            if cashback_cents > 0:
                await self.bot.db.add_wallet_balance(interaction.user.id, cashback_cents, "atto_payment_cashback")
            
            # Update order status
            await self.bot.db.update_order_status(order_id, "fulfilled")
            
            # Log transaction
            await self.bot.db.log_atto_transaction(
                interaction.user.id, "payment", required_atto_raw, final_price_cents,
                cashback_raw=_usd_to_atto(cashback_cents, price_usd) if cashback_cents > 0 else "0",
                status="completed"
            )
            
            embed = create_embed(
                title="✅ Payment Complete",
                description=f"Paid {format_usd(final_price_cents)} with Atto",
                color=discord.Color.green()
            )
            
            if choice == "discount":
                embed.add_field(
                    name="💰 Discount Applied",
                    value=f"Saved {format_usd(order_price_cents - final_price_cents)} (2.5%)",
                    inline=False
                )
            else:
                embed.add_field(
                    name="🎁 Cashback",
                    value=f"Received {format_usd(cashback_cents)} cashback (2.5%)",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error processing Atto payment: {e}")
            await interaction.followup.send(
                "❌ Error processing payment. Please try again later.",
                ephemeral=True
            )
    
    @app_commands.command(name="attowithdraw", description="Withdraw Atto to external address")
    @app_commands.describe(address="Atto address to withdraw to", amount="Amount in USD to withdraw")
    async def atto_withdraw_command(self, interaction: discord.Interaction, address: str, amount: float):
        """Withdraw Atto to external address."""
        await interaction.response.defer(ephemeral=True)
        
        # Validate address format
        if not address.startswith("atto://"):
            await interaction.followup.send(
                "❌ Invalid Atto address format. Must start with 'atto://'",
                ephemeral=True
            )
            return
        
        if amount <= 0:
            await interaction.followup.send("❌ Amount must be greater than 0.", ephemeral=True)
            return
        
        amount_cents = int(amount * 100)
        
        try:
            # Get balance
            balance = await self.bot.db.get_atto_balance(interaction.user.id)
            if not balance:
                await interaction.followup.send(
                    "❌ No Atto balance. Use `/attodeposit` or `/attoswap` to add funds.",
                    ephemeral=True
                )
                return
            
            # Get price
            price_usd = await _get_atto_price_usd()
            if not price_usd:
                await interaction.followup.send(
                    "❌ Unable to fetch Atto price. Please try again later.",
                    ephemeral=True
                )
                return
            
            # Calculate required Atto
            required_atto_raw = _usd_to_atto(amount_cents, price_usd)
            balance_raw = balance.get("balance_raw", "0")
            
            if int(balance_raw) < int(required_atto_raw):
                await interaction.followup.send(
                    "❌ Insufficient Atto balance.",
                    ephemeral=True
                )
                return
            
            # Get main wallet address
            main_address = await self.bot.db.get_main_wallet_address()
            if not main_address:
                main_address = ATTO_MAIN_WALLET
                if not main_address:
                    await interaction.followup.send(
                        "❌ Main wallet not configured. Please contact admin.",
                        ephemeral=True
                    )
                    return
            
            # Send transaction
            tx_hash = await _send_atto_transaction(main_address, address, required_atto_raw)
            
            if tx_hash:
                # Deduct balance
                await self.bot.db.deduct_atto_balance(interaction.user.id, required_atto_raw)
                
                # Log transaction
                await self.bot.db.log_atto_transaction(
                    interaction.user.id, "withdrawal", required_atto_raw, amount_cents,
                    from_address=main_address, to_address=address, transaction_hash=tx_hash,
                    status="completed"
                )
                
                embed = create_embed(
                    title="✅ Withdrawal Complete",
                    description=f"Withdrew {format_usd(amount_cents)} to {address}",
                    color=discord.Color.green()
                )
                
                embed.add_field(
                    name="🔗 Transaction Hash",
                    value=f"`{tx_hash}`",
                    inline=False
                )
            else:
                # Log as pending
                await self.bot.db.log_atto_transaction(
                    interaction.user.id, "withdrawal", required_atto_raw, amount_cents,
                    from_address=main_address, to_address=address, status="pending"
                )
                
                embed = create_embed(
                    title="⏳ Withdrawal Initiated",
                    description=f"Withdrawing {format_usd(amount_cents)} to {address}",
                    color=discord.Color.blue()
                )
                
                embed.add_field(
                    name="💡 Note",
                    value="Withdrawal is being processed. This may take a few moments.",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error processing Atto withdrawal: {e}")
            await interaction.followup.send(
                "❌ Error processing withdrawal. Please try again later.",
                ephemeral=True
            )
    
    @app_commands.command(name="attoprice", description="Check current Atto price")
    async def atto_price_command(self, interaction: discord.Interaction):
        """Check current Atto price."""
        await interaction.response.defer(ephemeral=True)
        
        price_usd = await _get_atto_price_usd()
        
        if price_usd:
            embed = create_embed(
                title="💹 Atto Price",
                description=f"**Current Price:** ${price_usd:.6f} USD",
                color=discord.Color.gold()
            )
            
            embed.add_field(
                name="📊 Exchange",
                value="XT.com (ATTO/USDT)",
                inline=True
            )
        else:
            embed = create_embed(
                title="❌ Price Unavailable",
                description="Unable to fetch Atto price at this time.",
                color=discord.Color.red()
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="attosetup", description="[Admin] Set main wallet address")
    @app_commands.default_permissions(administrator=True)
    @admin_only()
    @app_commands.describe(address="Main Atto wallet address")
    async def atto_setup_command(self, interaction: discord.Interaction, address: str):
        """Admin: Set main wallet address."""
        await interaction.response.defer(ephemeral=True)
        
        if not address.startswith("atto://"):
            await interaction.followup.send(
                "❌ Invalid address format. Must start with 'atto://'",
                ephemeral=True
            )
            return
        
        try:
            await self.bot.db.set_main_wallet_address(address)
            
            embed = create_embed(
                title="✅ Main Wallet Set",
                description=f"Main wallet address updated:\n`{address}`",
                color=discord.Color.green()
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error setting main wallet: {e}")
            await interaction.followup.send(
                "❌ Error setting main wallet. Please try again.",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    """Load the Atto Integration cog."""
    await bot.add_cog(AttoIntegrationCog(bot))
    logger.info("Loaded extension: cogs.atto_integration")
