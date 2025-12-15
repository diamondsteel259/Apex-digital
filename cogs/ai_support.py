"""
AI Support System Cog

Provides AI-powered support with three tiers:
- Free: Gemini 2.5 Flash-Lite (10 general + 20 product questions/day)
- Premium: Groq Llama 3.1 8B (50 general + 100 product questions/day)
- Ultra: Gemini 2.5 Flash (100 general + 200 product questions/day + 50 images/month)
"""

from __future__ import annotations

import asyncio
import hashlib
import os
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

from apex_core.logger import get_logger
from apex_core.utils import create_embed
from apex_core.utils.admin_checks import admin_only

logger = get_logger()

# Tier limits
TIER_LIMITS = {
    "free": {"general": 10, "product": 20},
    "premium": {"general": 50, "product": 100},
    "ultra": {"general": 100, "product": 200, "images": 50}
}

# Model configurations
MODELS = {
    "free": "gemini-2.5-flash-lite",
    "premium": "llama-3.1-8b-instant",
    "ultra": "gemini-2.5-flash"
}

# Cost per 1K tokens (in cents)
COST_PER_1K_TOKENS = {
    "free": 0,  # Free tier
    "premium": 0.052,  # Groq: $0.00052 per 1K tokens
    "ultra": 7.5  # Gemini: $0.075 per 1M tokens = $0.075 per 1K tokens
}


def _get_user_tier(user: discord.Member) -> str:
    """Get user's AI tier based on roles."""
    role_names = [role.name.lower() for role in user.roles]
    
    if "ai ultra" in " ".join(role_names) or "💎 ai ultra" in " ".join(role_names):
        return "ultra"
    elif "ai premium" in " ".join(role_names) or "⚡ ai premium" in " ".join(role_names):
        return "premium"
    else:
        return "free"


def _is_product_question(question: str, product_keywords: list[str]) -> bool:
    """Check if question is about products/bot."""
    question_lower = question.lower()
    product_keywords_lower = [kw.lower() for kw in product_keywords]
    
    # Check for product-related keywords
    product_indicators = [
        "product", "buy", "purchase", "order", "price", "cost", "service",
        "available", "stock", "catalog", "store", "shop", "item", "variant",
        "category", "discount", "promo", "wallet", "balance", "refund",
        "ticket", "support", "command", "/", "!", "bot"
    ]
    
    # Check if question contains product keywords or bot-related terms
    if any(indicator in question_lower for indicator in product_indicators):
        return True
    
    # Check if question mentions any product names
    if any(kw in question_lower for kw in product_keywords_lower):
        return True
    
    return False


async def _build_product_context(db) -> str:
    """Build product context for AI."""
    try:
        products = await db.get_all_products(active_only=True)
        if not products:
            return "No products available."
        
        context = "AVAILABLE PRODUCTS:\n"
        for product in products[:50]:  # Limit to 50 products to avoid token limits
            # SQLite Row objects don't have .get() - convert to dict or use direct access
            if hasattr(product, "keys") and not isinstance(product, dict):
                product_dict = dict(product)
                name = product_dict.get("variant_name", "Unknown")
                price_cents = product_dict.get("price_cents", 0)
                category = product_dict.get("main_category", "Unknown")
                subcategory = product_dict.get("sub_category", "")
            else:
                name = product.get("variant_name", "Unknown")
                price_cents = product.get("price_cents", 0)
                category = product.get("main_category", "Unknown")
                subcategory = product.get("sub_category", "")
            price = f"${price_cents / 100:.2f}"
            
            context += f"- {name} ({category}"
            if subcategory:
                context += f" > {subcategory}"
            context += f"): {price}\n"
        
        if len(products) > 50:
            context += f"\n... and {len(products) - 50} more products."
        
        return context
    except Exception as e:
        logger.error(f"Error building product context: {e}")
        return "Product information unavailable."


async def _build_user_context(db, user_id: int, tier: str) -> str:
    """Build user-specific context for paid tiers."""
    if tier == "free":
        return ""
    
    try:
        user = await db.get_user(user_id)
        if not user:
            return ""
        
        # SQLite Row objects don't have .get() - convert to dict or use direct access
        if hasattr(user, "keys") and not isinstance(user, dict):
            user_dict = dict(user)
            balance_cents = user_dict.get("wallet_balance_cents", 0)
            total_spent = user_dict.get("total_lifetime_spent_cents", 0)
        else:
            balance_cents = user.get("wallet_balance_cents", 0)
            total_spent = user.get("total_lifetime_spent_cents", 0)
        
        context = "USER INFORMATION:\n"
        context += f"- Wallet Balance: ${balance_cents / 100:.2f}\n"
        
        # Get order count
        orders = await db.get_user_orders(user_id)
        context += f"- Total Orders: {len(orders)}\n"
        
        # Get VIP tier
        if total_spent >= 10000000:  # $100,000
            context += "- VIP Tier: Apex Zenith\n"
        elif total_spent >= 1000000:  # $10,000
            context += "- VIP Tier: Apex Sovereign\n"
        elif total_spent >= 500000:  # $5,000
            context += "- VIP Tier: Apex Legend\n"
        elif total_spent >= 100000:  # $1,000
            context += "- VIP Tier: Apex Elite\n"
        elif total_spent >= 50000:  # $500
            context += "- VIP Tier: Apex VIP\n"
        else:
            context += "- VIP Tier: Client\n"
        
        return context
    except Exception as e:
        logger.error(f"Error building user context: {e}")
        return ""


class AISupportCog(commands.Cog):
    """AI Support System with three tiers."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.gemini_client = None
        self.groq_client = None
        
        # Initialize API clients
        self._init_clients()
    
    def _init_clients(self):
        """Initialize AI API clients."""
        # Gemini API
        gemini_key = os.getenv("GEMINI_API_KEY")
        if gemini_key and GEMINI_AVAILABLE:
            try:
                genai.configure(api_key=gemini_key)
                self.gemini_client = genai
                logger.info("✅ Gemini API initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini API: {e}")
        else:
            if not gemini_key:
                logger.warning("⚠️ GEMINI_API_KEY not found in environment")
            if not GEMINI_AVAILABLE:
                logger.warning("⚠️ google-generativeai not installed")
        
        # Groq API
        groq_key = os.getenv("GROQ_API_KEY")
        if groq_key and GROQ_AVAILABLE:
            try:
                self.groq_client = Groq(api_key=groq_key)
                logger.info("✅ Groq API initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Groq API: {e}")
        else:
            if not groq_key:
                logger.warning("⚠️ GROQ_API_KEY not found in environment")
            if not GROQ_AVAILABLE:
                logger.warning("⚠️ groq not installed")
    
    async def _get_daily_usage(self, user_id: int, usage_date: date) -> dict:
        """Get or create daily usage record."""
        try:
            cursor = await self.bot.db._connection.execute(
                """
                SELECT * FROM ai_daily_usage
                WHERE user_discord_id = ? AND usage_date = ?
                """,
                (user_id, usage_date.isoformat())
            )
            row = await cursor.fetchone()
            
            if row:
                return {
                    "general_questions": row["general_questions"],
                    "product_questions": row["product_questions"],
                    "images_generated": row["images_generated"]
                }
            else:
                # Create new record
                await self.bot.db._connection.execute(
                    """
                    INSERT INTO ai_daily_usage (user_discord_id, usage_date)
                    VALUES (?, ?)
                    """,
                    (user_id, usage_date.isoformat())
                )
                await self.bot.db._connection.commit()
                return {"general_questions": 0, "product_questions": 0, "images_generated": 0}
        except Exception as e:
            logger.error(f"Error getting daily usage: {e}")
            return {"general_questions": 0, "product_questions": 0, "images_generated": 0}
    
    async def _increment_usage(self, user_id: int, usage_date: date, question_type: str):
        """Increment usage counter."""
        try:
            field = f"{question_type}_questions"
            await self.bot.db._connection.execute(
                f"""
                UPDATE ai_daily_usage
                SET {field} = {field} + 1
                WHERE user_discord_id = ? AND usage_date = ?
                """,
                (user_id, usage_date.isoformat())
            )
            await self.bot.db._connection.commit()
        except Exception as e:
            logger.error(f"Error incrementing usage: {e}")
    
    async def _log_usage(
        self,
        user_id: int,
        tier: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        question_preview: str
    ):
        """Log AI usage for cost tracking."""
        try:
            total_tokens = input_tokens + output_tokens
            cost_cents = int((total_tokens / 1000) * COST_PER_1K_TOKENS.get(tier, 0))
            
            await self.bot.db._connection.execute(
                """
                INSERT INTO ai_usage_logs
                (user_discord_id, tier, model, input_tokens, output_tokens, total_tokens, estimated_cost_cents, question_preview)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, tier, model, input_tokens, output_tokens, total_tokens, cost_cents, question_preview[:100])
            )
            await self.bot.db._connection.commit()
        except Exception as e:
            logger.error(f"Error logging usage: {e}")
    
    async def _check_limits(self, user: discord.Member, question: str, product_keywords: list[str]) -> tuple[bool, str]:
        """Check if user has remaining questions."""
        tier = _get_user_tier(user)
        limits = TIER_LIMITS.get(tier, TIER_LIMITS["free"])
        
        today = date.today()
        usage = await self._get_daily_usage(user.id, today)
        
        is_product = _is_product_question(question, product_keywords)
        question_type = "product" if is_product else "general"
        
        limit = limits.get(question_type, 0)
        current = usage.get(f"{question_type}_questions", 0)
        
        if current >= limit:
            remaining_general = limits.get("general", 0) - usage.get("general_questions", 0)
            remaining_product = limits.get("product", 0) - usage.get("product_questions", 0)
            
            return False, (
                f"❌ You've reached your daily limit for {question_type} questions!\n\n"
                f"**Your limits:**\n"
                f"- General questions: {remaining_general}/{limits.get('general', 0)} remaining\n"
                f"- Product/bot questions: {remaining_product}/{limits.get('product', 0)} remaining\n\n"
                f"Upgrade to Premium or Ultra for more questions!"
            )
        
        return True, ""
    
    async def _get_ai_response(
        self,
        question: str,
        tier: str,
        product_context: str,
        user_context: str
    ) -> tuple[str, int, int]:
        """Get AI response from appropriate model."""
        model_name = MODELS.get(tier, MODELS["free"])
        
        # Build system prompt
        system_prompt = f"""You are a helpful Discord bot assistant for Apex Core, a digital product marketplace.

{product_context}

{user_context}

RULES:
- You can reference product information above
- You CANNOT access supplier information
- You CANNOT access other users' data
- Be helpful, friendly, and professional
- If asked about products, provide accurate information from the context
- If you don't know something, say so honestly
"""
        
        if tier == "free":
            return await self._get_gemini_response(question, system_prompt, model_name)
        elif tier == "premium":
            return await self._get_groq_response(question, system_prompt)
        else:  # ultra
            return await self._get_gemini_response(question, system_prompt, model_name)
    
    async def _get_gemini_response(self, question: str, system_prompt: str, model_name: str) -> tuple[str, int, int]:
        """Get response from Gemini API."""
        if not self.gemini_client:
            raise RuntimeError("Gemini API not initialized")
        
        try:
            model = genai.GenerativeModel(model_name)
            
            full_prompt = f"{system_prompt}\n\nUser Question: {question}"
            
            response = await asyncio.to_thread(
                model.generate_content,
                full_prompt
            )
            
            text = response.text if response.text else "I apologize, but I couldn't generate a response."
            
            # Estimate tokens (rough: 1 token ≈ 4 characters)
            input_tokens = len(full_prompt) // 4
            output_tokens = len(text) // 4
            
            return text, input_tokens, output_tokens
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            raise RuntimeError(f"AI service error: {e}")
    
    async def _get_groq_response(self, question: str, system_prompt: str) -> tuple[str, int, int]:
        """Get response from Groq API."""
        if not self.groq_client:
            raise RuntimeError("Groq API not initialized")
        
        try:
            response = await asyncio.to_thread(
                self.groq_client.chat.completions.create,
                model=MODELS["premium"],
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": question}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            text = response.choices[0].message.content
            
            # Get actual token usage if available
            input_tokens = response.usage.prompt_tokens if hasattr(response.usage, 'prompt_tokens') else len(system_prompt + question) // 4
            output_tokens = response.usage.completion_tokens if hasattr(response.usage, 'completion_tokens') else len(text) // 4
            
            return text, input_tokens, output_tokens
        except Exception as e:
            logger.error(f"Groq API error: {e}")
            raise RuntimeError(f"AI service error: {e}")
    
    @app_commands.command(name="ai", description="Ask the AI assistant a question")
    @app_commands.describe(question="Your question for the AI assistant")
    async def ai_command(self, interaction: discord.Interaction, question: str):
        """Main AI command."""
        await interaction.response.defer(ephemeral=True)
        
        user = interaction.user
        if not isinstance(user, discord.Member):
            await interaction.followup.send("❌ This command can only be used in a server.", ephemeral=True)
            return
        
        tier = _get_user_tier(user)
        
        # Get product keywords for context
        try:
            products = await self.bot.db.get_all_products(active_only=True)
            product_keywords = [p.get("variant_name", "") for p in products[:20]]
        except:
            product_keywords = []
        
        # Check limits
        can_ask, limit_message = await self._check_limits(user, question, product_keywords)
        if not can_ask:
            await interaction.followup.send(limit_message, ephemeral=True)
            return
        
        # Build contexts
        product_context = await _build_product_context(self.bot.db)
        user_context = await _build_user_context(self.bot.db, user.id, tier)
        
        # Get AI response
        try:
            response_text, input_tokens, output_tokens = await self._get_ai_response(
                question, tier, product_context, user_context
            )
        except Exception as e:
            logger.error(f"AI response error: {e}")
            await interaction.followup.send(
                f"❌ Error getting AI response: {e}\n\nPlease try again later or contact support.",
                ephemeral=True
            )
            return
        
        # Update usage
        today = date.today()
        is_product = _is_product_question(question, product_keywords)
        question_type = "product" if is_product else "general"
        await self._increment_usage(user.id, today, question_type)
        
        # Log usage
        await self._log_usage(
            user.id, tier, MODELS.get(tier, "unknown"),
            input_tokens, output_tokens, question
        )
        
        # Get updated usage for display
        usage = await self._get_daily_usage(user.id, today)
        limits = TIER_LIMITS.get(tier, TIER_LIMITS["free"])
        
        # Create response embed
        embed = create_embed(
            title="🤖 AI Assistant Response",
            description=response_text[:2000],  # Discord embed limit
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="📊 Usage Today",
            value=(
                f"General: {usage['general_questions']}/{limits.get('general', 0)}\n"
                f"Product: {usage['product_questions']}/{limits.get('product', 0)}"
            ),
            inline=True
        )
        
        embed.add_field(
            name="💎 Tier",
            value=tier.title(),
            inline=True
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="aiusage", description="Check your AI usage statistics")
    async def ai_usage_command(self, interaction: discord.Interaction):
        """Check AI usage."""
        await interaction.response.defer(ephemeral=True)
        
        user = interaction.user
        if not isinstance(user, discord.Member):
            await interaction.followup.send("❌ This command can only be used in a server.", ephemeral=True)
            return
        
        tier = _get_user_tier(user)
        limits = TIER_LIMITS.get(tier, TIER_LIMITS["free"])
        today = date.today()
        usage = await self._get_daily_usage(user.id, today)
        
        embed = create_embed(
            title="📊 Your AI Usage",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="💎 Tier",
            value=tier.title(),
            inline=True
        )
        
        embed.add_field(
            name="📝 General Questions",
            value=f"{usage['general_questions']}/{limits.get('general', 0)}",
            inline=True
        )
        
        embed.add_field(
            name="🛍️ Product Questions",
            value=f"{usage['product_questions']}/{limits.get('product', 0)}",
            inline=True
        )
        
        if tier == "ultra":
            embed.add_field(
                name="🖼️ Images Generated",
                value=f"{usage['images_generated']}/{limits.get('images', 0)}",
                inline=True
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="aisubscribe", description="Subscribe to AI Premium or Ultra tier")
    @app_commands.describe(tier="Tier to subscribe to")
    @app_commands.choices(tier=[
        app_commands.Choice(name="Premium - $5/month (50 general + 100 product questions/day)", value="premium"),
        app_commands.Choice(name="Ultra - $10/month (100 general + 200 product questions/day + 50 images)", value="ultra")
    ])
    async def ai_subscribe_command(self, interaction: discord.Interaction, tier: app_commands.Choice[str]):
        """Subscribe to AI tier."""
        await interaction.response.defer(ephemeral=True)
        
        # TODO: Implement subscription payment flow
        await interaction.followup.send(
            f"🚧 Subscription system coming soon!\n\n"
            f"You selected: **{tier.name}**\n\n"
            f"Contact an admin to set up your subscription.",
            ephemeral=True
        )
    
    @app_commands.command(name="aiadmin", description="Admin: View AI usage statistics")
    @app_commands.default_permissions(administrator=True)
    @admin_only()
    async def ai_admin_command(self, interaction: discord.Interaction):
        """Admin command for AI statistics."""
        await interaction.response.defer(ephemeral=True)
        
        # TODO: Implement admin statistics
        await interaction.followup.send(
            "🚧 Admin statistics coming soon!",
            ephemeral=True
        )


async def setup(bot: commands.Bot):
    """Load the AI Support cog."""
    await bot.add_cog(AISupportCog(bot))
    logger.info("Loaded extension: cogs.ai_support")

