"""Server infrastructure blueprint for Apex Core.

This module defines the complete server structure including roles, categories,
channels, and permission overwrites required for Apex Core to function.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Literal

import discord


@dataclass
class RoleBlueprint:
    """Blueprint for a Discord role."""
    name: str
    color: discord.Color
    permissions: discord.Permissions
    hoist: bool = False
    mentionable: bool = False
    position: Optional[int] = None
    reason: str = "Apex Core full server setup"


@dataclass
class ChannelBlueprint:
    """Blueprint for a Discord channel."""
    name: str
    channel_type: Literal["text", "voice"]
    overwrites: Dict[str, Dict[str, bool]] = field(default_factory=dict)
    panel_type: Optional[str] = None
    topic: Optional[str] = None
    position: Optional[int] = None
    reason: str = "Apex Core full server setup"


@dataclass
class CategoryBlueprint:
    """Blueprint for a Discord category with channels."""
    name: str
    overwrites: Dict[str, Dict[str, bool]] = field(default_factory=dict)
    channels: List[ChannelBlueprint] = field(default_factory=list)
    position: Optional[int] = None
    reason: str = "Apex Core full server setup"


@dataclass
class ServerBlueprint:
    """Complete server infrastructure blueprint."""
    roles: List[RoleBlueprint] = field(default_factory=list)
    categories: List[CategoryBlueprint] = field(default_factory=list)


def get_apex_core_blueprint() -> ServerBlueprint:
    """Get the standard Apex Core server blueprint.
    
    Returns:
        ServerBlueprint with all required roles, categories, and channels
    """
    
    # Define roles
    customer_permissions = discord.Permissions(
        view_channel=True,
        send_messages=True,
        embed_links=True,
        attach_files=True,
        read_message_history=True,
        add_reactions=True,
        use_external_emojis=True,
    )

    roles = [
        RoleBlueprint(
            name="🔴 Apex Staff",
            color=discord.Color.red(),
            permissions=discord.Permissions(
                view_channel=True,
                send_messages=True,
                embed_links=True,
                attach_files=True,
                read_message_history=True,
                manage_channels=True,
                manage_messages=True,
                manage_roles=True,
                kick_members=True,
                ban_members=True,
                view_audit_log=True,
            ),
            hoist=True,
            mentionable=True,
            position=10,
        ),
        RoleBlueprint(
            name="🔵 Apex Client",
            color=discord.Color.blue(),
            permissions=customer_permissions,
            hoist=True,
            mentionable=False,
            position=5,
        ),
        RoleBlueprint(
            name="⭐ Apex Insider",
            color=discord.Color.gold(),
            permissions=customer_permissions,
            hoist=True,
            mentionable=False,
            position=4,
        ),
        RoleBlueprint(
            name="👤 Client",
            color=discord.Color.dark_grey(),
            permissions=customer_permissions,
            hoist=False,
            mentionable=False,
        ),
        RoleBlueprint(
            name="💜 Apex VIP",
            color=discord.Color.purple(),
            permissions=customer_permissions,
            hoist=True,
            mentionable=False,
        ),
        RoleBlueprint(
            name="💎 Apex Elite",
            color=discord.Color.dark_purple(),
            permissions=customer_permissions,
            hoist=True,
            mentionable=False,
        ),
        RoleBlueprint(
            name="👑 Apex Legend",
            color=discord.Color.orange(),
            permissions=customer_permissions,
            hoist=True,
            mentionable=False,
        ),
        RoleBlueprint(
            name="🌟 Apex Sovereign",
            color=discord.Color.dark_gold(),
            permissions=customer_permissions,
            hoist=True,
            mentionable=False,
        ),
        RoleBlueprint(
            name="✨ Apex Zenith",
            color=discord.Color.gold(),
            permissions=customer_permissions,
            hoist=True,
            mentionable=False,
        ),
        RoleBlueprint(
            name="💝 Apex Donor",
            color=discord.Color.magenta(),
            permissions=customer_permissions,
            hoist=True,
            mentionable=False,
        ),
        RoleBlueprint(
            name="🎖️ Legendary Donor",
            color=discord.Color.dark_magenta(),
            permissions=customer_permissions,
            hoist=True,
            mentionable=False,
        ),
        # AI Support Tiers
        RoleBlueprint(
            name="🤖 AI Free",
            color=discord.Color.light_grey(),
            permissions=customer_permissions,
            hoist=True,
            mentionable=False,
            position=3,
        ),
        RoleBlueprint(
            name="⚡ AI Premium",
            color=discord.Color.blue(),
            permissions=customer_permissions,
            hoist=True,
            mentionable=False,
            position=2,
        ),
        RoleBlueprint(
            name="💎 AI Ultra",
            color=discord.Color.gold(),
            permissions=customer_permissions,
            hoist=True,
            mentionable=False,
            position=1,
        ),
    ]

    # Define categories with channels
    categories = [
        # Products Category
        CategoryBlueprint(
            name="📦 PRODUCTS",
            overwrites={
                "@everyone": {
                    "view_channel": True,
                    "send_messages": False,
                    "add_reactions": True,
                },
                "🔴 Apex Staff": {
                    "view_channel": True,
                    "send_messages": True,
                    "manage_messages": True,
                },
            },
            channels=[
                ChannelBlueprint(
                    name="🛍️-products",
                    channel_type="text",
                    topic="🛍️ Browse our product catalog and open tickets to purchase",
                    panel_type="products",
                    overwrites={
                        "@everyone": {
                            "view_channel": True,
                            "send_messages": False,
                            "add_reactions": True,
                        },
                        "🔴 Apex Staff": {
                            "view_channel": True,
                            "send_messages": True,
                        },
                    },
                ),
            ],
            position=1,
        ),
        
        # Support Category
        CategoryBlueprint(
            name="🛟 SUPPORT",
            overwrites={
                "@everyone": {
                    "view_channel": True,
                    "send_messages": False,
                },
                "🔴 Apex Staff": {
                    "view_channel": True,
                    "send_messages": True,
                    "manage_channels": True,
                },
            },
            channels=[
                ChannelBlueprint(
                    name="🛟-support",
                    channel_type="text",
                    topic="🛟 Need help? Click buttons below to open a ticket",
                    panel_type="support",
                    overwrites={
                        "@everyone": {
                            "view_channel": True,
                            "send_messages": False,
                            "add_reactions": True,
                        },
                        "🔴 Apex Staff": {
                            "view_channel": True,
                            "send_messages": True,
                        },
                    },
                ),
            ],
            position=2,
        ),
        
        # Information Category
        CategoryBlueprint(
            name="📋 INFORMATION",
            overwrites={
                "@everyone": {
                    "view_channel": True,
                    "send_messages": False,
                    "add_reactions": True,
                },
                "🔴 Apex Staff": {
                    "view_channel": True,
                    "send_messages": True,
                },
            },
            channels=[
                ChannelBlueprint(
                    name="🎉-welcome",
                    channel_type="text",
                    topic="🎉 Welcome to Apex Core! Read this first!",
                    panel_type="welcome",
                    overwrites={
                        "@everyone": {
                            "view_channel": True,
                            "send_messages": False,
                            "add_reactions": True,
                        },
                        "🔴 Apex Staff": {
                            "view_channel": True,
                            "send_messages": True,
                            "manage_messages": True,
                        },
                    },
                ),
                ChannelBlueprint(
                    name="📜-rules-and-tos",
                    channel_type="text",
                    topic="📜 Server rules, terms of service, and policies",
                    panel_type="rules",
                    overwrites={
                        "@everyone": {
                            "view_channel": True,
                            "send_messages": False,
                            "add_reactions": True,
                        },
                        "🔴 Apex Staff": {
                            "view_channel": True,
                            "send_messages": True,
                            "manage_messages": True,
                        },
                    },
                ),
                ChannelBlueprint(
                    name="🔒-privacy",
                    channel_type="text",
                    topic="🔒 Privacy policy and data protection information",
                    panel_type="privacy",
                    overwrites={
                        "@everyone": {
                            "view_channel": True,
                            "send_messages": False,
                            "add_reactions": True,
                        },
                        "🔴 Apex Staff": {
                            "view_channel": True,
                            "send_messages": True,
                            "manage_messages": True,
                        },
                    },
                ),
                ChannelBlueprint(
                    name="❓-help",
                    channel_type="text",
                    topic="❓ How to use Apex Core - Read this first!",
                    panel_type="help",
                    overwrites={
                        "@everyone": {
                            "view_channel": True,
                            "send_messages": False,
                        },
                        "🔴 Apex Staff": {
                            "view_channel": True,
                            "send_messages": True,
                        },
                    },
                ),
                ChannelBlueprint(
                    name="❓-faq",
                    channel_type="text",
                    topic="❓ Frequently Asked Questions - Find answers instantly",
                    panel_type="faq",
                    overwrites={
                        "@everyone": {
                            "view_channel": True,
                            "send_messages": False,
                            "add_reactions": True,
                        },
                        "🔴 Apex Staff": {
                            "view_channel": True,
                            "send_messages": True,
                            "manage_messages": True,
                        },
                    },
                ),
                ChannelBlueprint(
                    name="⭐-reviews",
                    channel_type="text",
                    topic="⭐ Share your experience and earn rewards",
                    panel_type="reviews",
                    overwrites={
                        "@everyone": {
                            "view_channel": True,
                            "send_messages": False,
                        },
                "🔵 Apex Client": {
                    "view_channel": True,
                    "send_messages": True,
                },
                "👤 Client": {
                    "view_channel": True,
                    "send_messages": True,
                },
                "🔴 Apex Staff": {
                    "view_channel": True,
                    "send_messages": True,
                },
                    },
                ),
                ChannelBlueprint(
                    name="🏆-testimonials",
                    channel_type="text",
                    topic="🏆 Customer testimonials and success stories",
                    overwrites={
                        "@everyone": {
                            "view_channel": True,
                            "send_messages": False,
                            "add_reactions": True,
                        },
                        "🔴 Apex Staff": {
                            "view_channel": True,
                            "send_messages": True,
                            "manage_messages": True,
                        },
                    },
                ),
                ChannelBlueprint(
                    name="📢-announcements",
                    channel_type="text",
                    topic="📢 Important updates and announcements",
                    overwrites={
                        "@everyone": {
                            "view_channel": True,
                            "send_messages": False,
                        },
                        "🔴 Apex Staff": {
                            "view_channel": True,
                            "send_messages": True,
                        },
                    },
                ),
                ChannelBlueprint(
                    name="📊-status",
                    channel_type="text",
                    topic="📊 System status, maintenance updates, and service information",
                    overwrites={
                        "@everyone": {
                            "view_channel": True,
                            "send_messages": False,
                            "add_reactions": True,
                        },
                        "🔴 Apex Staff": {
                            "view_channel": True,
                            "send_messages": True,
                            "manage_messages": True,
                        },
                    },
                ),
            ],
            position=3,
        ),
        
        # VIP Category
        CategoryBlueprint(
            name="💎 VIP LOUNGE",
            overwrites={
                "@everyone": {
                    "view_channel": False,
                },
                "💜 Apex VIP": {
                    "view_channel": True,
                    "send_messages": True,
                    "add_reactions": True,
                },
                "💎 Apex Elite": {
                    "view_channel": True,
                    "send_messages": True,
                    "add_reactions": True,
                },
                "👑 Apex Legend": {
                    "view_channel": True,
                    "send_messages": True,
                    "add_reactions": True,
                },
                "🌟 Apex Sovereign": {
                    "view_channel": True,
                    "send_messages": True,
                    "add_reactions": True,
                },
                "✨ Apex Zenith": {
                    "view_channel": True,
                    "send_messages": True,
                    "add_reactions": True,
                },
                "🔴 Apex Staff": {
                    "view_channel": True,
                    "send_messages": True,
                    "manage_messages": True,
                },
            },
            channels=[
                ChannelBlueprint(
                    name="💎-vip-lounge",
                    channel_type="text",
                    topic="💎 Exclusive VIP community - Early access, exclusive deals, and VIP-only content",
                    overwrites={
                        "@everyone": {
                            "view_channel": False,
                        },
                        "💜 Apex VIP": {
                            "view_channel": True,
                            "send_messages": True,
                            "add_reactions": True,
                        },
                        "💎 Apex Elite": {
                            "view_channel": True,
                            "send_messages": True,
                            "add_reactions": True,
                        },
                        "👑 Apex Legend": {
                            "view_channel": True,
                            "send_messages": True,
                            "add_reactions": True,
                        },
                        "🌟 Apex Sovereign": {
                            "view_channel": True,
                            "send_messages": True,
                            "add_reactions": True,
                        },
                        "✨ Apex Zenith": {
                            "view_channel": True,
                            "send_messages": True,
                            "add_reactions": True,
                        },
                        "🔴 Apex Staff": {
                            "view_channel": True,
                            "send_messages": True,
                            "manage_messages": True,
                        },
                    },
                ),
            ],
            position=4,
        ),
        
        # AI Support Category
        CategoryBlueprint(
            name="🤖 AI SUPPORT",
            overwrites={
                "@everyone": {
                    "view_channel": True,
                    "send_messages": True,
                    "add_reactions": True,
                },
                "🔴 Apex Staff": {
                    "view_channel": True,
                    "send_messages": True,
                    "manage_messages": True,
                },
            },
            channels=[
                ChannelBlueprint(
                    name="🤖-ai-support",
                    channel_type="text",
                    topic="🤖 Ask questions, get help, and interact with AI - Free tier: 10 questions/day | Premium: 50/day | Ultra: 100/day + images",
                    overwrites={
                        "@everyone": {
                            "view_channel": True,
                            "send_messages": True,
                            "add_reactions": True,
                        },
                        "🔴 Apex Staff": {
                            "view_channel": True,
                            "send_messages": True,
                            "manage_messages": True,
                        },
                    },
                ),
            ],
            position=5,
        ),
        
        # Community Category
        CategoryBlueprint(
            name="💬 COMMUNITY",
            overwrites={
                "@everyone": {
                    "view_channel": True,
                    "send_messages": True,
                    "add_reactions": True,
                },
                "🔴 Apex Staff": {
                    "view_channel": True,
                    "send_messages": True,
                    "manage_messages": True,
                },
            },
            channels=[
                ChannelBlueprint(
                    name="💡-suggestions",
                    channel_type="text",
                    topic="💡 Share your suggestions and feedback - Help us improve!",
                    overwrites={
                        "@everyone": {
                            "view_channel": True,
                            "send_messages": True,
                            "add_reactions": True,
                        },
                        "🔴 Apex Staff": {
                            "view_channel": True,
                            "send_messages": True,
                            "manage_messages": True,
                        },
                    },
                ),
                ChannelBlueprint(
                    name="💰-tips",
                    channel_type="text",
                    topic="💰 Tip other users and show appreciation - Use /tip command",
                    overwrites={
                        "@everyone": {
                            "view_channel": True,
                            "send_messages": True,
                            "add_reactions": True,
                        },
                        "🔴 Apex Staff": {
                            "view_channel": True,
                            "send_messages": True,
                            "manage_messages": True,
                        },
                    },
                ),
                ChannelBlueprint(
                    name="🎁-airdrops",
                    channel_type="text",
                    topic="🎁 Claim airdrops and share codes - Use /claimairdrop command",
                    overwrites={
                        "@everyone": {
                            "view_channel": True,
                            "send_messages": True,
                            "add_reactions": True,
                        },
                        "🔴 Apex Staff": {
                            "view_channel": True,
                            "send_messages": True,
                            "manage_messages": True,
                        },
                    },
                ),
            ],
            position=6,
        ),
        
        # Staff Area Category
        CategoryBlueprint(
            name="🔒 STAFF AREA",
            overwrites={
                "@everyone": {
                    "view_channel": False,
                },
                "🔴 Apex Staff": {
                    "view_channel": True,
                    "send_messages": True,
                    "manage_channels": True,
                    "manage_messages": True,
                },
            },
            channels=[
                ChannelBlueprint(
                    name="🎫-tickets",
                    channel_type="text",
                    topic="🎫 Active support tickets - Staff only",
                    overwrites={
                        "@everyone": {
                            "view_channel": False,
                        },
                        "🔴 Apex Staff": {
                            "view_channel": True,
                            "send_messages": True,
                            "manage_channels": True,
                        },
                    },
                ),
                ChannelBlueprint(
                    name="📜-transcripts",
                    channel_type="text",
                    topic="📜 Ticket transcripts archive - Staff only",
                    overwrites={
                        "@everyone": {
                            "view_channel": False,
                        },
                        "🔴 Apex Staff": {
                            "view_channel": True,
                            "send_messages": True,
                            "manage_messages": True,
                        },
                    },
                ),
                ChannelBlueprint(
                    name="📦-order-logs",
                    channel_type="text",
                    topic="📦 Order processing and fulfillment logs - Staff only",
                    overwrites={
                        "@everyone": {
                            "view_channel": False,
                        },
                        "🔴 Apex Staff": {
                            "view_channel": True,
                            "send_messages": True,
                            "manage_messages": True,
                        },
                    },
                ),
            ],
            position=6,
        ),
        
        # Logs Category (Staff only)
        CategoryBlueprint(
            name="📊 LOGS",
            overwrites={
                "@everyone": {
                    "view_channel": False,
                },
                "🔴 Apex Staff": {
                    "view_channel": True,
                    "send_messages": True,
                },
            },
            channels=[
                ChannelBlueprint(
                    name="🔍-audit-log",
                    channel_type="text",
                    topic="🔍 System audit logs and setup actions",
                    overwrites={
                        "@everyone": {
                            "view_channel": False,
                        },
                        "🔴 Apex Staff": {
                            "view_channel": True,
                            "send_messages": False,
                        },
                    },
                ),
                ChannelBlueprint(
                    name="💳-payment-log",
                    channel_type="text",
                    topic="💳 Payment confirmations and transactions",
                    overwrites={
                        "@everyone": {
                            "view_channel": False,
                        },
                        "🔴 Apex Staff": {
                            "view_channel": True,
                            "send_messages": False,
                        },
                    },
                ),
                ChannelBlueprint(
                    name="⚠️-error-log",
                    channel_type="text",
                    topic="⚠️ System errors and exceptions",
                    overwrites={
                        "@everyone": {
                            "view_channel": False,
                        },
                        "🔴 Apex Staff": {
                            "view_channel": True,
                            "send_messages": False,
                        },
                    },
                ),
                ChannelBlueprint(
                    name="💰-wallet-log",
                    channel_type="text",
                    topic="💰 Wallet transactions and balance changes",
                    overwrites={
                        "@everyone": {
                            "view_channel": False,
                        },
                        "🔴 Apex Staff": {
                            "view_channel": True,
                            "send_messages": False,
                        },
                    },
                ),
            ],
            position=4,
        ),
    ]
    
    return ServerBlueprint(roles=roles, categories=categories)
