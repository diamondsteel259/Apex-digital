# Apex Core Discord Bot

A feature-rich Discord bot for automated product distribution, ticketing, and VIP management.

## Features

- **Automated Product Distribution**: SQLite-backed product catalog with role assignments and content delivery
- **VIP System**: Multi-tier VIP system with automatic discount application
- **Wallet System**: Internal wallet with transaction tracking and lifetime spending
- **Operating Hours**: Configurable business hours with Discord timestamp formatting
- **Payment Methods**: Flexible payment method configuration with custom instructions
- **Logging**: Comprehensive logging channels for audit, payments, tickets, and errors

## Setup

### Prerequisites

- Python 3.11 or higher
- Discord bot token (from [Discord Developer Portal](https://discord.com/developers/applications))

### Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd apex-core
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure the bot:
   ```bash
   cp config.example.json config.json
   ```
   
   Edit `config.json` with your bot token, guild IDs, role IDs, and other settings.

4. Run the bot:
   ```bash
   python bot.py
   ```

## Configuration

The `config.json` file contains all bot settings:

- **token**: Your Discord bot token
- **bot_prefix**: Command prefix (default: `!`)
- **guild_ids**: List of Discord server IDs where the bot operates
- **role_ids**: Role IDs for admin and VIP tiers
- **ticket_categories**: Category IDs for support, billing, and sales tickets
- **operating_hours**: Start and end hours in UTC (24-hour format)
- **payment_methods**: List of accepted payment methods with instructions and metadata
- **vip_thresholds**: Spending thresholds for VIP tiers (in cents) and discount percentages
- **logging_channels**: Channel IDs for logging audit, payments, tickets, and errors

## Project Structure

```
apex-core/
├── bot.py                    # Main bot entrypoint
├── config.example.json       # Example configuration
├── config.json              # Your configuration (gitignored)
├── requirements.txt         # Python dependencies
├── apex_core/              # Core modules
│   ├── __init__.py
│   ├── config.py           # Configuration loader
│   ├── database.py         # SQLite data layer
│   └── utils/              # Shared utilities
│       ├── __init__.py
│       ├── currency.py     # Currency formatting
│       ├── embeds.py       # Embed factory
│       ├── timestamps.py   # Discord timestamp helpers
│       └── vip.py          # VIP tier calculations
└── cogs/                   # Bot cogs (to be implemented)
    └── __init__.py
```

## Database Schema

### Users Table
- `id`: Primary key
- `discord_id`: Unique Discord user ID
- `wallet_balance_cents`: Current wallet balance in cents
- `total_lifetime_spent_cents`: Total amount spent lifetime
- `vip_tier`: Current VIP tier (tier1, tier2, tier3, or NULL)
- `created_at`: Account creation timestamp
- `updated_at`: Last update timestamp

### Products Table
- `id`: Primary key
- `name`: Product name
- `price_cents`: Price in cents
- `role_id`: Discord role ID to assign on purchase
- `content_payload`: Content URL or instructions
- `is_active`: Whether product is available for purchase
- `created_at`: Product creation timestamp
- `updated_at`: Last update timestamp

### Discounts Table
- `id`: Primary key
- `user_id`: Specific user (NULL for global/VIP discounts)
- `product_id`: Specific product (NULL for all products)
- `vip_tier`: VIP tier requirement (NULL for user-specific)
- `discount_percent`: Discount percentage (0-100)
- `description`: Discount description
- `expires_at`: Expiration timestamp (NULL for no expiration)
- `is_stackable`: Whether discount can stack with others
- `created_at`: Discount creation timestamp

## Development

### Adding New Cogs

1. Create a new file in the `cogs/` directory (e.g., `cogs/shop.py`)
2. Implement your cog class extending `commands.Cog`
3. Add a `setup()` function to load the cog
4. The bot will automatically load it on startup

Example:
```python
from discord.ext import commands

class MyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.hybrid_command()
    async def mycommand(self, ctx):
        await ctx.send("Hello!")

async def setup(bot):
    await bot.add_cog(MyCog(bot))
```

### Utilities

The `apex_core.utils` module provides:

- `format_usd(cents)`: Format cents as USD string (e.g., 1999 → "$19.99")
- `discord_timestamp(dt, style)`: Generate Discord timestamp strings
- `operating_hours_window(operating_hours)`: Get Discord timestamps for configured hours
- `render_operating_hours(operating_hours)`: Get human-readable operating hours string
- `create_embed(...)`: Create standardized embeds
- `calculate_vip_tier(total_spent_cents, config)`: Calculate VIP tier based on spending

### Database Access

Access the database in cogs via `self.bot.db`:

```python
# Ensure user exists
user = await self.bot.db.ensure_user(discord_id)

# Update wallet
new_balance = await self.bot.db.update_wallet_balance(discord_id, delta_cents=1000)

# Create product
product_id = await self.bot.db.create_product(
    name="Premium Access",
    price_cents=2999,
    role_id=123456789,
    content_payload="https://example.com/content"
)
```

## License

See LICENSE file for details.
