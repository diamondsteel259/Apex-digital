# Rate Limiting System

## Overview

The Apex Core bot implements comprehensive rate limiting to protect sensitive financial operations and administrative commands from abuse and spam. Rate limits are enforced at the command level with per-user, per-channel, or per-guild scopes.

## Architecture

### Core Components

#### `apex_core/rate_limiter.py`

The rate limiting system consists of several key classes:

- **`RateLimitBucket`**: Tracks usage for a specific entity (user/channel/guild) with sliding window algorithm
- **`RateLimiter`**: Global singleton managing all buckets, violation tracking, and staff alerts
- **`RateLimitSettings`**: Normalized configuration for each protected command
- **`RateLimitRule`**: Configuration dataclass loaded from `config.json`

### Rate Limiting Approaches

#### 1. Decorator for Commands

Use the `@rate_limit()` decorator for slash commands and prefix commands:

```python
from apex_core.rate_limiter import rate_limit

@app_commands.command(name="balance")
@rate_limit(cooldown=60, max_uses=2, per="user", config_key="balance")
async def balance(self, interaction: discord.Interaction):
    # Command implementation
    pass
```

#### 2. Manual Enforcement for Callbacks

For button callbacks or other interactions, use `enforce_interaction_rate_limit()`:

```python
from apex_core.rate_limiter import enforce_interaction_rate_limit

async def callback(self, interaction: discord.Interaction):
    allowed = await enforce_interaction_rate_limit(
        interaction,
        command_key="wallet_payment",
        cooldown=300,
        max_uses=3,
        per="user",
    )
    if not allowed:
        return
    
    # Process payment...
```

## Protected Commands

### High Priority (Financial Operations)

| Command | Cooldown | Max Uses | Scope | Notes |
|---------|----------|----------|-------|-------|
| `/balance` | 60s | 2 | user | View wallet balance |
| Wallet Payment Button | 300s (5min) | 3 | user | Process instant payment |
| `/submitrefund` | 3600s (1hr) | 1 | user | Submit refund request |
| `/setref` | 86400s (24hrs) | 1 | user | Set referrer (one-time) |
| `!refund-approve` | 60s | 10 | user | Staff: approve refunds |
| `!manual_complete` | 60s | 5 | user | Staff: complete orders |

### Moderate Priority (Informational)

| Command | Cooldown | Max Uses | Scope | Notes |
|---------|----------|----------|-------|-------|
| `/orders` | 60s | 5 | user | View order history |
| `/profile` | 60s | 5 | user | View user profile |
| `/invites` | 60s | 3 | user | View referral stats |

## Configuration

### config.json Structure

Add a `rate_limits` section to override default rate limits:

```json
{
  "rate_limits": {
    "balance": {
      "cooldown": 60,
      "max_uses": 2,
      "per": "user"
    },
    "wallet_payment": {
      "cooldown": 300,
      "max_uses": 3,
      "per": "user"
    },
    "submitrefund": {
      "cooldown": 3600,
      "max_uses": 1,
      "per": "user"
    },
    "setref": {
      "cooldown": 86400,
      "max_uses": 1,
      "per": "user"
    }
  }
}
```

### Parameters

- **`cooldown`**: Time window in seconds for rate limiting
- **`max_uses`**: Maximum number of uses allowed within the cooldown window
- **`per`**: Scope of rate limiting:
  - `"user"`: Per-user rate limit (most common)
  - `"channel"`: Per-channel rate limit
  - `"guild"`: Per-guild rate limit

### Decorator Parameters

- **`cooldown`**: Cooldown period in seconds (required)
- **`max_uses`**: Maximum uses within cooldown (required)
- **`per`**: Scope ("user", "channel", "guild") - default: "user"
- **`config_key`**: Key to lookup in config.json rate_limits (optional)
- **`admin_bypass`**: Whether admins bypass limits - default: True

## Admin Bypass

### Behavior

By default, users with the admin role bypass all rate limits. This is useful for testing and administrative operations.

**Key Points:**
- Admin bypasses are logged to the audit channel with a blue embed
- Staff commands (`!refund-approve`, `!manual_complete`) set `admin_bypass=False` for accountability
- Bypasses are tracked but do not count as violations

### Audit Log Example

```
🔓 Rate Limit Bypass
Admin: @AdminUser (123456789)
Command: `balance`
Reason: Admin privilege
```

## Violation Tracking

### Thresholds

- **Alert Threshold**: 3 violations within 5 minutes
- **Alert Cooldown**: 10 minutes between staff alerts per user/command

### Staff Alerts

When a user exceeds the alert threshold, staff are notified in the audit channel:

```
⚠️ Rate Limit Violations
User: @SpammyUser (987654321)
Command: `balance`
Violations (5m window): 5
Scope: user
Limit: 2 per 60s
```

### Violation History

- Violations are tracked per user/command combination
- History is pruned after 5 minutes
- Multiple violations of different commands are tracked separately

## User Feedback

### Rate Limit Message Format

When a user is rate limited, they receive a clear message:

```
⏱️ Please wait 45s before using this command again.
You can use this command 0 more times in the current window.
```

Time formatting:
- Less than 60s: "45s"
- 60-3599s: "5m 30s"
- 3600s+: "1h 15m"

## Implementation Examples

### Example 1: Slash Command

```python
from discord import app_commands
from apex_core.rate_limiter import rate_limit

class MyCog(commands.Cog):
    @app_commands.command(name="example")
    @rate_limit(cooldown=300, max_uses=5, per="user", config_key="example")
    async def example_command(self, interaction: discord.Interaction):
        await interaction.response.send_message("Success!", ephemeral=True)
```

### Example 2: Prefix Command

```python
from discord.ext import commands
from apex_core.rate_limiter import rate_limit

class MyCog(commands.Cog):
    @commands.command(name="staff-action")
    @commands.has_permissions(administrator=True)
    @rate_limit(cooldown=60, max_uses=10, per="user", admin_bypass=False)
    async def staff_action(self, ctx: commands.Context):
        await ctx.send("Action completed!")
```

### Example 3: Button Callback

```python
from apex_core.rate_limiter import enforce_interaction_rate_limit

class PaymentButton(discord.ui.Button):
    async def callback(self, interaction: discord.Interaction):
        allowed = await enforce_interaction_rate_limit(
            interaction,
            command_key="payment_button",
            cooldown=300,
            max_uses=3,
            per="user",
            config_key="payment_button",
        )
        if not allowed:
            return
        
        # Process payment
        await interaction.response.send_message("Payment processed!", ephemeral=True)
```

## Monitoring and Logging

### Log Levels

- **DEBUG**: Admin bypasses, successful rate limit checks
- **WARNING**: Rate limit triggers, repeated violations
- **INFO**: General rate limiter initialization

### Audit Channel Events

The audit channel logs:
1. **Admin Bypasses** (Blue embeds) - When admins bypass rate limits
2. **Violation Alerts** (Orange embeds) - When users exceed violation threshold

### Example Log Output

```
[2024-01-15 10:30:45] WARNING:apex_core.rate_limiter: Rate limit triggered | command=balance user=123456789 scope=user id=123456789
[2024-01-15 10:30:46] DEBUG:apex_core.rate_limiter: Admin 987654321 bypassed rate limit for balance
```

## Best Practices

### 1. Choose Appropriate Scopes

- **Use `"user"`** for most commands to prevent individual abuse
- **Use `"channel"`** for commands that affect channel state
- **Use `"guild"`** for global actions that affect the entire server

### 2. Set Reasonable Limits

- Financial operations: Strict limits (1-3 uses per 5-60 minutes)
- Informational commands: Moderate limits (3-5 uses per minute)
- Admin commands: Loose limits but no bypass (5-10 uses per minute)

### 3. Use Config Keys

Always provide a `config_key` to allow server owners to customize limits:

```python
@rate_limit(cooldown=60, max_uses=5, per="user", config_key="mycommand")
```

### 4. Consider Admin Bypass

- Set `admin_bypass=True` (default) for user-facing commands
- Set `admin_bypass=False` for staff commands to maintain accountability

### 5. Test Rate Limits

Test rate limits during development:
1. Execute command repeatedly
2. Verify rate limit message appears
3. Check audit channel for violation alerts
4. Test admin bypass behavior

## Troubleshooting

### Common Issues

#### 1. Rate Limit Not Applying

**Cause**: Decorator order matters

**Solution**: Place `@rate_limit()` directly above the command function:

```python
@app_commands.command()
@app_commands.describe(...)  # ❌ Wrong order
@rate_limit(...)

# Should be:
@app_commands.command()
@rate_limit(...)  # ✓ Correct
@app_commands.describe(...)
async def command(...):
```

#### 2. Admin Bypass Not Working

**Cause**: User doesn't have admin role or role_ids.admin is misconfigured

**Solution**: 
1. Check `config.json` role_ids.admin is correct
2. Verify user has the admin role
3. Check audit channel for bypass logs

#### 3. Violations Not Alerting Staff

**Cause**: Alert cooldown prevents duplicate alerts

**Solution**: 
- Wait 10 minutes between tests
- Trigger violations from different users
- Check audit channel permissions

#### 4. Config Override Not Working

**Cause**: Invalid JSON or missing rate_limits section

**Solution**:
1. Validate config.json syntax
2. Ensure rate_limits is at root level
3. Check logs for config parsing errors

## Performance Considerations

### Memory Usage

- Each rate limit bucket stores timestamp history (deque)
- Old timestamps are pruned automatically
- Memory usage is O(n) where n = active users × protected commands

### Concurrency

- All bucket operations use asyncio.Lock for thread safety
- No race conditions in timestamp tracking
- Violation history also uses locks for consistency

### Scalability

For bots with:
- **< 1000 users**: No concerns
- **1000-10000 users**: Monitor memory usage (~10-50 MB)
- **> 10000 users**: Consider external rate limiting (Redis)

## Migration Guide

### Adding Rate Limiting to Existing Commands

1. Import the decorator:
   ```python
   from apex_core.rate_limiter import rate_limit
   ```

2. Add decorator with sensible defaults:
   ```python
   @rate_limit(cooldown=60, max_uses=5, per="user", config_key="command_name")
   ```

3. Update config.example.json with the new limit:
   ```json
   "rate_limits": {
     "command_name": {
       "cooldown": 60,
       "max_uses": 5,
       "per": "user"
     }
   }
   ```

4. Test the command to ensure rate limiting works

### Adjusting Existing Limits

1. Update config.json rate_limits section
2. No bot restart required - changes apply immediately on next use
3. Monitor audit channel for any issues

## Security Considerations

### Protection Against

- **Spam**: Prevents command flooding
- **Abuse**: Limits financial operation frequency
- **DoS**: Prevents resource exhaustion from repeated commands
- **Exploitation**: Rate limits sensitive operations

### Not Protected Against

- **DMs to Bot**: Rate limits only apply in guilds
- **API Abuse**: Discord's API limits are separate
- **Multiple Accounts**: Each account has separate rate limits

### Additional Security

Consider implementing:
- User reputation system
- IP-based rate limiting (requires proxy)
- Automatic temporary bans for excessive violations
- Command blacklist for problematic users

## Future Enhancements

Potential improvements:
- Persistent rate limit storage (Redis/database)
- Dynamic rate limits based on server size
- Per-role rate limit overrides
- Rate limit statistics dashboard
- Whitelist/blacklist system
