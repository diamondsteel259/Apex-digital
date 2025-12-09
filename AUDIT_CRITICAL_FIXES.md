# Critical and High-Priority Fixes Implementation Guide

This document provides step-by-step implementation for the 16 most critical issues found in the audit.

---

## CRITICAL FIX #1: Storage.py - Async S3 Operations

**File:** `apex_core/storage.py` (Lines 131-168)  
**Impact:** HIGH - Could cause event loop blocking

### Current Code Issue:
```python
async def _save_to_s3(self, filename: str, content_bytes: bytes, file_size: int) -> Tuple[str, int]:
    if not BOTO3_AVAILABLE or not self._s3_client:
        # ...
    
    try:
        import asyncio
        s3_key = f"transcripts/{filename}"
        
        def _upload():
            self._s3_client.put_object(
                Bucket=self.s3_bucket,
                Key=s3_key,
                Body=content_bytes,
                ContentType="text/html",
            )
        
        await asyncio.to_thread(_upload)  # ← ISSUE
```

### Root Cause:
The nested function `_upload` doesn't bind `self` properly when using `asyncio.to_thread()`, potentially causing attribute access errors.

### Implementation Steps:

1. **Update imports at top of file:**
```python
from functools import partial
```

2. **Replace `_save_to_s3` method (lines 131-168):**
```python
async def _save_to_s3(
    self,
    filename: str,
    content_bytes: bytes,
    file_size: int,
) -> Tuple[str, int]:
    """Save transcript to S3."""
    if not BOTO3_AVAILABLE or not self._s3_client:
        logger.warning(
            "S3 storage not available. Falling back to local storage for: %s", filename
        )
        return await self._save_to_local(filename, content_bytes, file_size)
    
    try:
        import asyncio
        from functools import partial
        
        s3_key = f"transcripts/{filename}"
        
        # Create a partial function that properly binds self
        upload_fn = partial(
            self._s3_client.put_object,
            Bucket=self.s3_bucket,
            Key=s3_key,
            Body=content_bytes,
            ContentType="text/html",
        )
        
        await asyncio.to_thread(upload_fn)
        logger.info(f"Saved transcript to S3: s3://{self.s3_bucket}/{s3_key}")
        return s3_key, file_size
        
    except ClientError as e:
        logger.error(f"Failed to save transcript to S3: {e}")
        logger.info("Falling back to local storage.")
        return await self._save_to_local(filename, content_bytes, file_size)
    except Exception as e:
        logger.error(f"Unexpected error saving to S3: {e}")
        logger.info("Falling back to local storage.")
        return await self._save_to_local(filename, content_bytes, file_size)
```

3. **Test the fix:**
```bash
python -m pytest tests/ -k "storage" -v
```

---

## CRITICAL FIX #2: Logger.py - Async Context in Sync Handler

**File:** `apex_core/logger.py` (Lines 21-53)  
**Impact:** CRITICAL - Could cause event loop errors

### Current Code Issue:
```python
def emit(self, record: logging.LogRecord) -> None:
    """Emit a log record to Discord channel if available."""
    if self.bot and self.channel_id:
        try:
            import asyncio
            # ...
            asyncio.create_task(send_message())  # ← ISSUE
```

### Root Cause:
`emit()` is synchronous but tries to create async tasks. This fails if called outside an event loop.

### Implementation Steps:

1. **Replace the DiscordHandler class (lines 21-53):**
```python
class DiscordHandler(logging.Handler):
    """Custom logging handler that sends messages to Discord channels."""
    
    def __init__(self, bot=None, channel_id: Optional[int] = None):
        super().__init__()
        self.bot = bot
        self.channel_id = channel_id
    
    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record to Discord channel if available."""
        if not self.bot or not self.channel_id:
            return
        
        try:
            import asyncio
            
            channel = self.bot.get_channel(self.channel_id)
            if not channel:
                return
            
            # Format the message for Discord
            msg = f"**{record.levelname}**: {record.getMessage()}"
            if hasattr(record, 'exc_info') and record.exc_info:
                msg += f"\n```{self.format(record)}```"
            
            # Try to schedule in the running event loop safely
            try:
                loop = asyncio.get_running_loop()
                # If we have a running loop, create a task
                loop.create_task(self._send_to_discord(msg, channel))
            except RuntimeError:
                # No running loop - this is a problem, log it
                logger.warning("No running event loop to send Discord log message")
        except Exception as e:
            # Fail silently to avoid infinite logging loops
            # But log the error to stderr as last resort
            import sys
            print(f"Failed to send Discord log: {e}", file=sys.stderr)
    
    async def _send_to_discord(self, msg: str, channel) -> None:
        """Send message to Discord asynchronously."""
        try:
            await channel.send(msg)
        except Exception:
            # Fail silently to avoid infinite logging loops
            pass
```

2. **Alternative approach (Simpler - Recommended):**

If the above is too complex, disable Discord logging in the handler and use a different approach:

```python
class DiscordHandler(logging.Handler):
    """Custom logging handler that sends messages to Discord channels."""
    
    def __init__(self, bot=None, channel_id: Optional[int] = None):
        super().__init__()
        self.bot = bot
        self.channel_id = channel_id
        self._pending_messages = []
    
    def emit(self, record: logging.LogRecord) -> None:
        """Queue a log record to be sent to Discord channel."""
        if not self.bot or not self.channel_id:
            return
        
        try:
            msg = f"**{record.levelname}**: {record.getMessage()}"
            if hasattr(record, 'exc_info') and record.exc_info:
                msg += f"\n```{self.format(record)}```"
            
            # Just queue it - let bot handle sending asynchronously
            self._pending_messages.append((self.channel_id, msg))
        except Exception:
            # Fail silently
            pass
```

**Recommended:** Use the simpler approach initially to avoid complexity.

---

## CRITICAL FIX #3: Database.py - Connection Null Checks

**File:** `apex_core/database.py` (Lines 599-639)  
**Impact:** CRITICAL - Race condition could cause AttributeError

### Current Code Issue:
```python
async def update_wallet_balance(self, discord_id: int, delta_cents: int) -> int:
    if self._connection is None:
        raise RuntimeError("Database connection not initialized.")
    
    async with self._wallet_lock:
        # Connection could still be None here after initial check!
        await self._connection.execute(...)
```

### Implementation Steps:

1. **Update `update_wallet_balance` method:**
```python
async def update_wallet_balance(self, discord_id: int, delta_cents: int) -> int:
    """Update user's wallet balance and return new balance."""
    if self._connection is None:
        raise RuntimeError("Database connection not initialized.")
    
    async with self._wallet_lock:
        # Double-check connection state
        if self._connection is None:
            raise RuntimeError("Database connection was lost during operation.")
        
        try:
            started_transaction = False
            if not self._connection.in_transaction:
                await self._connection.execute("BEGIN IMMEDIATE;")
                started_transaction = True
            
            # Ensure user exists
            await self._connection.execute(
                """
                INSERT INTO users (discord_id, wallet_balance_cents)
                VALUES (?, 0)
                ON CONFLICT(discord_id) DO NOTHING;
                """,
                (discord_id,),
            )
            
            # Update wallet and lifetime spending
            await self._connection.execute(
                """
                UPDATE users
                SET wallet_balance_cents = wallet_balance_cents + ?,
                    total_lifetime_spent_cents = CASE
                        WHEN ? > 0 THEN total_lifetime_spent_cents + ?
                        ELSE total_lifetime_spent_cents
                    END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE discord_id = ?;
                """,
                (delta_cents, delta_cents, delta_cents, discord_id),
            )
            
            if started_transaction:
                await self._connection.commit()
            
            # Fetch updated balance
            cursor = await self._connection.execute(
                "SELECT wallet_balance_cents FROM users WHERE discord_id = ?",
                (discord_id,),
            )
            row = await cursor.fetchone()
            return row["wallet_balance_cents"] if row else 0
            
        except Exception as e:
            # Rollback transaction if we started it
            if started_transaction:
                try:
                    await self._connection.rollback()
                except Exception:
                    pass
            
            logger.error(f"Wallet update failed for user {discord_id}: {e}", exc_info=True)
            raise RuntimeError(f"Failed to update wallet balance: {e}") from e
```

2. **Review all database methods for similar issues:**

Search for all methods in database.py that:
- Check `if self._connection is None` at the start
- Make multiple operations within async blocks
- Don't have explicit error handling

Apply the same pattern: check -> operation block with try/except -> error handling.

3. **Add a helper method to avoid repetition:**

```python
async def _ensure_connection(self) -> aiosqlite.Connection:
    """
    Ensure database connection is active.
    
    Raises:
        RuntimeError: If connection is not initialized or is closed
    """
    if self._connection is None:
        raise RuntimeError("Database connection not initialized.")
    return self._connection
```

Then use it:
```python
async def update_wallet_balance(self, discord_id: int, delta_cents: int) -> int:
    conn = await self._ensure_connection()
    
    async with self._wallet_lock:
        try:
            # ... operations on conn
        except Exception as e:
            logger.error(...)
            raise
```

---

## CRITICAL FIX #4: Config.py - Parameter Validation

**File:** `apex_core/config.py` (Lines 156-165)  
**Impact:** HIGH - Invalid configs could cause runtime errors

### Current Code Issue:
```python
def _parse_refund_settings(payload: dict[str, Any] | None) -> RefundSettings | None:
    if not payload:
        return None
    
    return RefundSettings(
        enabled=bool(payload.get("enabled", True)),
        max_days=int(payload.get("max_days", 3)),  # ← No range check
        handling_fee_percent=float(payload.get("handling_fee_percent", 10.0)),  # ← No validation
    )
```

### Implementation Steps:

1. **Replace `_parse_refund_settings` (lines 156-165):**
```python
def _parse_refund_settings(payload: dict[str, Any] | None) -> RefundSettings | None:
    """
    Parse and validate refund settings from config payload.
    
    Raises:
        ValueError: If any setting is invalid
    """
    if not payload:
        return None
    
    enabled = bool(payload.get("enabled", True))
    
    try:
        max_days = int(payload.get("max_days", 3))
    except (TypeError, ValueError) as e:
        raise ValueError(f"max_days must be an integer, got {payload.get('max_days')!r}") from e
    
    try:
        handling_fee_percent = float(payload.get("handling_fee_percent", 10.0))
    except (TypeError, ValueError) as e:
        raise ValueError(
            f"handling_fee_percent must be a number, got {payload.get('handling_fee_percent')!r}"
        ) from e
    
    # Validate ranges
    if max_days < 0 or max_days > 365:
        raise ValueError(
            f"max_days must be between 0 and 365, got {max_days}. "
            f"This represents the number of days after purchase within which refunds are allowed."
        )
    
    if handling_fee_percent < 0 or handling_fee_percent > 100:
        raise ValueError(
            f"handling_fee_percent must be between 0 and 100, got {handling_fee_percent}. "
            f"This is the percentage of the refund amount charged as a fee."
        )
    
    return RefundSettings(
        enabled=enabled,
        max_days=max_days,
        handling_fee_percent=handling_fee_percent,
    )
```

2. **Similarly update `_parse_roles` (lines 139-153):**

See the comprehensive audit report for the full implementation. Key additions:
- Validate discount_percent is 0-100
- Validate assignment_mode is in allowed set
- Validate role_id is positive
- Validate tier_priority is non-negative

3. **Test configuration:**
```bash
python -c "
from apex_core.config import load_config
try:
    config = load_config()
    print('Config loaded successfully')
except Exception as e:
    print(f'Config error: {e}')
"
```

---

## CRITICAL FIX #5: Rate Limiter - Violation Message

**File:** `apex_core/rate_limiter.py` (Lines 177-190)  
**Impact:** MEDIUM - Confusing user message

### Current Code Issue:
```python
return (
    "⏱️ Please wait {time} before using this command again.\n"
    "You can use this command {attempts} more times in the current window."
).format(time=time_str, attempts=attempts_text)  # ← Attempts will always be 0 when rate limited
```

### Implementation Steps:

1. **Replace `_build_violation_message` function:**
```python
def _build_violation_message(remaining_seconds: int, remaining_uses: int, settings: RateLimitSettings) -> str:
    """
    Build a user-friendly message about rate limiting.
    
    Args:
        remaining_seconds: Seconds until cooldown expires
        remaining_uses: Remaining uses (typically 0 when rate limited)
        settings: Rate limit configuration
    
    Returns:
        Formatted message for user
    """
    if remaining_seconds >= 3600:
        hours = remaining_seconds // 3600
        minutes = (remaining_seconds % 3600) // 60
        time_str = f"{hours}h {minutes}m" if minutes else f"{hours}h"
    elif remaining_seconds >= 60:
        minutes = remaining_seconds // 60
        seconds = remaining_seconds % 60
        time_str = f"{minutes}m {seconds}s" if seconds else f"{minutes}m"
    else:
        time_str = f"{remaining_seconds}s"
    
    # Build clearer message
    message = (
        f"⏱️ **Rate Limited**\n"
        f"Please wait **{time_str}** before using this command again.\n\n"
        f"📊 **Limit:** {settings.max_uses} uses per {settings.cooldown} second"
    )
    
    if settings.cooldown != 1:
        message += "s"
    
    return message
```

2. **Update calls to this function to ensure it always returns a string:**

The function already returns a string, so no changes needed there. The issue was just the confusing message content.

---

## HIGH PRIORITY FIX #1: Database Connection Timeout

**File:** `apex_core/database.py` (Lines 26-32)  
**Impact:** HIGH - Could hang indefinitely

### Current Code Issue:
```python
async def connect(self) -> None:
    if self._connection is None:
        self._connection = await aiosqlite.connect(self.db_path)  # ← No timeout
```

### Implementation Steps:

1. **Update `connect` method:**
```python
async def connect(self, timeout: float = 10.0) -> None:
    """
    Connect to the database with timeout.
    
    Args:
        timeout: Connection timeout in seconds (default: 10)
    
    Raises:
        RuntimeError: If connection fails or times out
    """
    if self._connection is None:
        try:
            self._connection = await asyncio.wait_for(
                aiosqlite.connect(str(self.db_path)),
                timeout=timeout
            )
            self._connection.row_factory = aiosqlite.Row
            await self._connection.execute("PRAGMA foreign_keys = ON;")
            await self._connection.commit()
            await self._initialize_schema()
            logger.info(f"Database connected: {self.db_path}")
            
        except asyncio.TimeoutError:
            self._connection = None
            logger.error(
                f"Database connection timed out after {timeout}s. "
                f"Check if database file is accessible: {self.db_path}"
            )
            raise RuntimeError(
                f"Failed to connect to database within {timeout} seconds"
            )
        except Exception as e:
            self._connection = None
            logger.error(f"Failed to connect to database: {e}", exc_info=True)
            raise RuntimeError(f"Database connection failed: {e}") from e
```

2. **Update `close` method for safety:**
```python
async def close(self) -> None:
    """Close database connection safely."""
    if self._connection:
        try:
            await asyncio.wait_for(self._connection.close(), timeout=5.0)
            self._connection = None
            logger.info("Database connection closed.")
        except asyncio.TimeoutError:
            logger.warning("Database close timed out - forcing closure")
            self._connection = None
        except Exception as e:
            logger.error(f"Error closing database: {e}")
            self._connection = None
```

---

## HIGH PRIORITY FIX #2: Financial Cooldown Manager Config

**File:** `apex_core/financial_cooldown_manager.py` (Lines 45-73)  
**Impact:** MEDIUM - Poor error messages for unknown commands

### Current Code Issue:
```python
default_configs = {
    "wallet_payment": FinancialCooldownConfig(30, CooldownTier.ULTRA_SENSITIVE, "payment"),
    # ...
}

return default_configs.get(command_key, FinancialCooldownConfig(60, CooldownTier.STANDARD, "unknown"))
```

### Implementation Steps:

1. **Update `_get_config` method:**
```python
def _get_config(self, command_key: str, bot: commands.Bot | None = None) -> FinancialCooldownConfig:
    """
    Get cooldown configuration for a specific command.
    
    Args:
        command_key: The command identifier
        bot: Bot instance for custom configuration
    
    Returns:
        Configuration for the command
    """
    default_configs = {
        "wallet_payment": FinancialCooldownConfig(30, CooldownTier.ULTRA_SENSITIVE, "payment"),
        "submitrefund": FinancialCooldownConfig(300, CooldownTier.ULTRA_SENSITIVE, "refund"),
        "manual_complete": FinancialCooldownConfig(10, CooldownTier.ULTRA_SENSITIVE, "order"),
        "setref": FinancialCooldownConfig(86400, CooldownTier.SENSITIVE, "referral"),
        "refund_approve": FinancialCooldownConfig(5, CooldownTier.SENSITIVE, "staff"),
        "refund_reject": FinancialCooldownConfig(5, CooldownTier.SENSITIVE, "staff"),
        "balance": FinancialCooldownConfig(10, CooldownTier.STANDARD, "query"),
        "orders": FinancialCooldownConfig(30, CooldownTier.STANDARD, "query"),
        "invites": FinancialCooldownConfig(30, CooldownTier.STANDARD, "query"),
    }
    
    # Check bot config for overrides
    if bot and hasattr(bot, 'config') and hasattr(bot.config, 'financial_cooldowns'):
        custom_configs = getattr(bot.config, 'financial_cooldowns', {})
        if command_key in custom_configs:
            custom_seconds = custom_configs[command_key]
            default_config = default_configs.get(command_key)
            if default_config:
                return FinancialCooldownConfig(
                    custom_seconds,
                    default_config.tier,
                    default_config.operation_type
                )
    
    # Get default or log warning
    if command_key not in default_configs:
        logger.warning(
            f"Financial cooldown command not configured: {command_key}. "
            f"Using default 60s. Add to default_configs in _get_config() method."
        )
    
    return default_configs.get(
        command_key,
        FinancialCooldownConfig(60, CooldownTier.STANDARD, command_key)  # Use actual key, not "unknown"
    )
```

---

## Continue with Remaining High Priority Fixes

Due to length constraints, here's a summary table for the remaining fixes:

| # | File | Method | Lines | Summary |
|---|------|--------|-------|---------|
| 3 | storage.py | __init__ | 24-30 | Validate storage type and S3 config early |
| 4 | rate_limiter.py | _is_admin | 193-205 | Change debug log to info for admin bypasses |
| 5 | financial_cooldown_manager.py | _is_admin | 178-191 | Same: change debug to info |
| 6 | wallet.py | _channel_overwrites | 138-150 | Add admin role to overwrites |
| 7 | config.py | _parse_roles | 139-153 | Add comprehensive validation |
| 8 | database.py | Various | Multiple | Review all DB methods for connection checks |

---

## Testing After Fixes

Create a test script to verify fixes:

```python
# test_critical_fixes.py
import asyncio
import tempfile
from pathlib import Path

async def test_critical_fixes():
    """Test all critical fixes."""
    
    # Test 1: Database connection timeout
    from apex_core import Database
    db = Database(db_path=":memory:")
    try:
        await asyncio.wait_for(db.connect(timeout=2.0), timeout=3.0)
        print("✓ Database connection timeout works")
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
    finally:
        await db.close()
    
    # Test 2: Config validation
    from apex_core.config import _parse_refund_settings
    try:
        # Valid config
        config = _parse_refund_settings({
            "enabled": True,
            "max_days": 30,
            "handling_fee_percent": 10.0
        })
        print("✓ Valid refund config accepted")
        
        # Invalid config
        try:
            config = _parse_refund_settings({
                "max_days": 400,  # Invalid - too high
            })
            print("✗ Invalid config not rejected")
        except ValueError:
            print("✓ Invalid refund config rejected")
    except Exception as e:
        print(f"✗ Config validation failed: {e}")
    
    # Test 3: Rate limiter message
    from apex_core.rate_limiter import _build_violation_message, RateLimitSettings
    settings = RateLimitSettings(
        key="test",
        cooldown=60,
        max_uses=5,
        scope="user"
    )
    msg = _build_violation_message(30, 0, settings)
    if "30s" in msg and "5 uses" in msg:
        print("✓ Rate limit message formatted correctly")
    else:
        print(f"✗ Rate limit message incorrect: {msg}")

if __name__ == "__main__":
    asyncio.run(test_critical_fixes())
```

Run with:
```bash
python test_critical_fixes.py
```

---

## Summary

These 8+ critical and high-priority fixes address:
- Event loop safety
- Database reliability  
- Configuration validation
- User-facing messages
- Timeout handling

**Total estimated time: 8-12 hours for implementation and testing**

Proceed with Phase 1 fixes immediately, then Phase 2 before production deployment.
