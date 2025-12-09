# Rate Limiting and Financial Cooldown System

This document describes the rate limiting and financial cooldown system, including admin bypass behavior and logging.

## Overview

The Apex bot implements two complementary protection systems:

1. **Rate Limiting** (`apex_core/rate_limiter.py`) - Prevents command abuse across different scopes
2. **Financial Cooldowns** (`apex_core/financial_cooldown_manager.py`) - Extra protection for sensitive financial operations

## Rate Limiting

### How it Works

The rate limiter tracks command usage across three scopes:
- **User**: Limits per user ID (most common)
- **Channel**: Limits per channel ID 
- **Guild**: Limits per guild ID

Commands specify:
- `cooldown`: Time window in seconds
- `max_uses`: Maximum uses within the cooldown window
- `per`: Scope (user/channel/guild)

### Decorator Usage

```python
@rate_limit(cooldown=60, max_uses=5, per="user", admin_bypass=True)
async def balance_command(self, interaction):
    # Command logic here
    pass
```

### Interactive Usage

```python
await enforce_interaction_rate_limit(
    interaction=interaction,
    command_key="button_action",
    cooldown=30,
    max_uses=3,
    per="user",
    admin_bypass=True,
)
```

## Financial Cooldowns

### How it Works

Financial commands have additional cooldown protection beyond basic rate limiting:

- **Ultra Sensitive**: 30-300 seconds (wallet payments, refunds, order completion)
- **Sensitive**: 5-86400 seconds (referral commands, staff operations)
- **Standard**: 10-60 seconds (balance queries, order history)

### Decorator Usage

```python
@financial_cooldown(
    seconds=30,
    tier=CooldownTier.ULTRA_SENSITIVE,
    operation_type="payment",
    admin_bypass=True
)
async def wallet_payment_command(self, interaction):
    # Payment logic here
    pass
```

## Admin Bypass Behavior

### How It Works

Administrators with the configured admin role can bypass both rate limits and financial cooldowns. This allows staff to:
- Respond quickly to user issues
- Perform maintenance without cooldown restrictions
- Handle emergency situations

### Bypass Conditions

Bypass occurs when:
1. `admin_bypass=True` is set on the decorator/function
2. User has the configured admin role
3. User is in a guild context (not DM)

## Logging

### Bypass Events

**Important**: Admin bypass events are logged at **INFO level** to ensure visibility in production logs.

#### Rate Limiting Bypasses

```
INFO: Admin {user_id} bypassed rate limit for {command_key} (scope={scope}, id={identifier})
```

**Example**:
```
INFO: Admin 123456789 bypassed rate limit for balance (scope=user, id=123456789)
INFO: Admin 123456789 bypassed rate limit for wallet_payment (scope=channel, id=987654321)
```

#### Financial Cooldown Bypasses

```
INFO: Admin {user_id} bypassed financial cooldown for {command_key}
```

**Example**:
```
INFO: Admin 123456789 bypassed financial cooldown for wallet_payment
INFO: Admin 123456789 bypassed financial cooldown for submitrefund
```

### Monitoring Bypasses

Operators should monitor INFO-level logs for bypass events to:
- Track staff usage patterns
- Identify potential misuse of admin privileges
- Audit compliance with operational procedures

#### Log Monitoring Commands

```bash
# View recent bypass events
grep "bypassed rate limit" logs/app.log
grep "bypassed financial cooldown" logs/app.log

# Monitor in real-time
tail -f logs/app.log | grep "bypassed"
```

### Violation Events

Non-admin users hitting rate limits generate **WARNING** level logs:

```
WARNING: Rate limit triggered | command=balance user=123456789 scope=user id=123456789
WARNING: Financial cooldown triggered | command=wallet_payment user=123456789 remaining=25s
```

## Configuration

### Admin Role Configuration

Admin role is configured in the bot config:

```python
Config(
    # ... other settings
    role_ids=RoleIDs(admin=123456789),  # Your admin role ID
)
```

### Custom Rate Limits

Custom rate limits can be configured per command:

```python
Config(
    # ... other settings
    rate_limits={
        "balance": RateLimitRule(cooldown=60, max_uses=2, per="user"),
        "wallet_payment": RateLimitRule(cooldown=30, max_uses=1, per="user"),
    }
)
```

### Custom Financial Cooldowns

Custom financial cooldowns can be configured per command:

```python
# The financial cooldown manager automatically picks up config
custom_cooldowns = {
    "wallet_payment": 45,  # Override to 45 seconds
    "balance": 15,         # Override to 15 seconds
}
```

## Audit Channel Integration

All bypass events also generate audit channel embeds (separate from INFO logs) for:
- Rich formatting with user mentions
- Dedicated audit trail
- Visual distinction from operational logs

Audit embeds include:
- Admin user mention and ID
- Command name
- Reason (Admin privilege)
- Timestamp

## Testing

Bypass logging can be tested using:

```bash
# Run bypass logging tests specifically
pytest tests/test_bypass_logging.py -v

# Run with specific keywords
pytest tests -k bypass_logging -v
```

## Troubleshooting

### High Bypass Volume

If seeing many bypass events:
1. Check if staff are using commands appropriately
2. Consider if cooldowns need adjustment for legitimate usage
3. Review audit logs for patterns

### Missing Bypass Logs

If bypass events aren't appearing:
1. Verify logging level is set to INFO or lower
2. Check that admin role ID is configured correctly
3. Ensure user is in guild context (not DM)

### Rate Limit Effectiveness

If rate limits aren't working:
1. Check configuration is properly loaded
2. Verify scope identifiers are correct
3. Review violation alert thresholds

## Best Practices

1. **Monitor INFO Logs**: Set up monitoring for bypass events
2. **Regular Audits**: Periodically review bypass patterns
3. **Minimize Bypass Usage**: Only bypass when operationally necessary
4. **Proper Configuration**: Ensure admin roles are correctly configured
5. **Testing**: Regularly test rate limiting behavior

## Related Files

- `apex_core/rate_limiter.py` - Core rate limiting implementation
- `apex_core/financial_cooldown_manager.py` - Financial cooldown system
- `tests/test_bypass_logging.py` - Bypass logging tests
- `tests/conftest.py` - Test fixtures and mocks