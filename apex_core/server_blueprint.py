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
            name="Apex Staff",
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
            name="Apex Client",
            color=discord.Color.blue(),
            permissions=customer_permissions,
            hoist=True,
            mentionable=False,
            position=5,
        ),
        RoleBlueprint(
            name="Apex Insider",
            color=discord.Color.gold(),
            permissions=customer_permissions,
            hoist=True,
            mentionable=False,
            position=4,
        ),
        RoleBlueprint(
            name="Client",
            color=discord.Color.dark_grey(),
            permissions=customer_permissions,
            hoist=False,
            mentionable=False,
        ),
        RoleBlueprint(
            name="Apex VIP",
            color=discord.Color.purple(),
            permissions=customer_permissions,
            hoist=True,
            mentionable=False,
        ),
        RoleBlueprint(
            name="Apex Elite",
            color=discord.Color.dark_purple(),
            permissions=customer_permissions,
            hoist=True,
            mentionable=False,
        ),
        RoleBlueprint(
            name="Apex Legend",
            color=discord.Color.orange(),
            permissions=customer_permissions,
            hoist=True,
            mentionable=False,
        ),
        RoleBlueprint(
            name="Apex Sovereign",
            color=discord.Color.dark_gold(),
            permissions=customer_permissions,
            hoist=True,
            mentionable=False,
        ),
        RoleBlueprint(
            name="Apex Zenith",
            color=discord.Color.gold(),
            permissions=customer_permissions,
            hoist=True,
            mentionable=False,
        ),
        RoleBlueprint(
            name="Apex Donor",
            color=discord.Color.magenta(),
            permissions=customer_permissions,
            hoist=True,
            mentionable=False,
        ),
        RoleBlueprint(
            name="Legendary Donor",
            color=discord.Color.dark_magenta(),
            permissions=customer_permissions,
            hoist=True,
            mentionable=False,
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
                "Apex Staff": {
                    "view_channel": True,
                    "send_messages": True,
                    "manage_messages": True,
                },
            },
            channels=[
                ChannelBlueprint(
                    name="products",
                    channel_type="text",
                    topic="🛍️ Browse our product catalog and open tickets to purchase",
                    panel_type="products",
                    overwrites={
                        "@everyone": {
                            "view_channel": True,
                            "send_messages": False,
                            "add_reactions": True,
                        },
                        "Apex Staff": {
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
                "Apex Staff": {
                    "view_channel": True,
                    "send_messages": True,
                    "manage_channels": True,
                },
            },
            channels=[
                ChannelBlueprint(
                    name="support",
                    channel_type="text",
                    topic="🛟 Need help? Click buttons below to open a ticket",
                    panel_type="support",
                    overwrites={
                        "@everyone": {
                            "view_channel": True,
                            "send_messages": False,
                            "add_reactions": True,
                        },
                        "Apex Staff": {
                            "view_channel": True,
                            "send_messages": True,
                        },
                    },
                ),
                ChannelBlueprint(
                    name="tickets",
                    channel_type="text",
                    topic="📋 Active support tickets - Staff only",
                    overwrites={
                        "@everyone": {
                            "view_channel": False,
                        },
                        "Apex Staff": {
                            "view_channel": True,
                            "send_messages": True,
                            "manage_channels": True,
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
                "Apex Staff": {
                    "view_channel": True,
                    "send_messages": True,
                },
            },
            channels=[
                ChannelBlueprint(
                    name="help",
                    channel_type="text",
                    topic="❓ How to use Apex Core - Read this first!",
                    panel_type="help",
                    overwrites={
                        "@everyone": {
                            "view_channel": True,
                            "send_messages": False,
                        },
                        "Apex Staff": {
                            "view_channel": True,
                            "send_messages": True,
                        },
                    },
                ),
                ChannelBlueprint(
                    name="reviews",
                    channel_type="text",
                    topic="⭐ Share your experience and earn rewards",
                    panel_type="reviews",
                    overwrites={
                        "@everyone": {
                            "view_channel": True,
                            "send_messages": False,
                        },
                        "Apex Client": {
                            "view_channel": True,
                            "send_messages": True,
                        },
                        "Client": {
                            "view_channel": True,
                            "send_messages": True,
                        },
                        "Apex Staff": {
                            "view_channel": True,
                            "send_messages": True,
                        },
                    },
                ),
                ChannelBlueprint(
                    name="announcements",
                    channel_type="text",
                    topic="📢 Important updates and announcements",
                    overwrites={
                        "@everyone": {
                            "view_channel": True,
                            "send_messages": False,
                        },
                        "Apex Staff": {
                            "view_channel": True,
                            "send_messages": True,
                        },
                    },
                ),
            ],
            position=3,
        ),
        
        # Logs Category (Staff only)
        CategoryBlueprint(
            name="📊 LOGS",
            overwrites={
                "@everyone": {
                    "view_channel": False,
                },
                "Apex Staff": {
                    "view_channel": True,
                    "send_messages": True,
                },
            },
            channels=[
                ChannelBlueprint(
                    name="audit-log",
                    channel_type="text",
                    topic="🔍 System audit logs and setup actions",
                    overwrites={
                        "@everyone": {
                            "view_channel": False,
                        },
                        "Apex Staff": {
                            "view_channel": True,
                            "send_messages": False,
                        },
                    },
                ),
                ChannelBlueprint(
                    name="payment-log",
                    channel_type="text",
                    topic="💳 Payment confirmations and transactions",
                    overwrites={
                        "@everyone": {
                            "view_channel": False,
                        },
                        "Apex Staff": {
                            "view_channel": True,
                            "send_messages": False,
                        },
                    },
                ),
                ChannelBlueprint(
                    name="error-log",
                    channel_type="text",
                    topic="⚠️ System errors and exceptions",
                    overwrites={
                        "@everyone": {
                            "view_channel": False,
                        },
                        "Apex Staff": {
                            "view_channel": True,
                            "send_messages": False,
                        },
                    },
                ),
                ChannelBlueprint(
                    name="wallet-log",
                    channel_type="text",
                    topic="💰 Wallet transactions and balance changes",
                    overwrites={
                        "@everyone": {
                            "view_channel": False,
                        },
                        "Apex Staff": {
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
