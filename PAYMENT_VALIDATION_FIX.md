# Payment Methods Validation Fix

## Summary
Fixed the wallet deposit command to accept any configured payment methods instead of requiring specific hardcoded payment method names.

## Problem
The `/deposit` command was logging errors and blocking users:
```
ERROR:cogs.wallet: Deposit command blocked: Missing payment methods in configuration: Binance Pay, Crypto Address
```

This occurred because the code had hardcoded payment method requirements:
```python
REQUIRED_PAYMENT_METHODS = ("Binance Pay", "Tip.cc", "Crypto Address")
```

## Solution
Replaced hardcoded payment method validation with flexible validation that:
1. Accepts ANY payment methods configured in `config/payments.json`
2. Only requires at least ONE enabled payment method
3. Filters methods based on `is_enabled` flag
4. Allows users full control over their payment configuration

## Changes Made

### File: `cogs/wallet.py`

#### 1. Removed Hardcoded Constant
```python
# REMOVED:
REQUIRED_PAYMENT_METHODS = ("Binance Pay", "Tip.cc", "Crypto Address")
```

#### 2. Replaced Method
```python
# OLD METHOD (removed):
def _get_payment_methods(self, required: Sequence[str]) -> list[PaymentMethod]:
    # Raised error if specific methods missing
    ...

# NEW METHOD (added):
def _get_all_enabled_payment_methods(self) -> list[PaymentMethod]:
    """Get all enabled payment methods from configuration.
    
    Returns:
        List of enabled payment methods.
        
    Raises:
        RuntimeError: If no payment methods are configured.
    """
    # Use payment settings if available, otherwise fall back to legacy payment methods
    if self.bot.config.payment_settings:
        all_methods = self.bot.config.payment_settings.payment_methods
    else:
        all_methods = self.bot.config.payment_methods
    
    # Filter for enabled payment methods
    enabled_methods = [
        method for method in all_methods 
        if method.metadata.get("is_enabled", True) != False
    ]
    
    if not enabled_methods:
        raise RuntimeError(
            "No payment methods are currently enabled. Please contact an admin."
        )
    
    return enabled_methods
```

#### 3. Updated Deposit Command
```python
# In deposit() command:
try:
    payment_methods = self._get_all_enabled_payment_methods()  # Changed from _get_payment_methods()
except RuntimeError as exc:
    logger.error("Deposit command blocked: %s", exc)
    await interaction.response.send_message(
        "Deposit methods are not configured. Please contact staff.", ephemeral=True
    )
    return
```

## Benefits

### ✅ Flexibility
- Users can configure any payment methods they want
- No hardcoded payment method names
- Works with custom payment providers

### ✅ Consistency
- Uses same filtering logic as `StorefrontCog`:
  ```python
  enabled_methods = [m for m in payment_methods if m.metadata.get("is_enabled", True) != False]
  ```

### ✅ Simple Validation
- Only checks that at least ONE payment method exists
- No unnecessary blocking of legitimate configurations

### ✅ Better Error Messages
- Clear error: "No payment methods are currently enabled"
- No more confusing "Missing payment methods: Binance Pay, Crypto Address" errors

## Testing

Validated the fix with multiple scenarios:
1. ✅ All methods enabled (default behavior)
2. ✅ Mixed enabled/disabled methods
3. ✅ All methods disabled (proper error)
4. ✅ User's actual config (Wallet, PayPal, Crypto) - works without "Binance Pay" or "Crypto Address"

## Example Configurations That Now Work

### Config 1: Minimal
```json
{
  "payment_methods": [
    {"name": "Wallet", "instructions": "...", "is_enabled": true},
    {"name": "PayPal", "instructions": "...", "is_enabled": true}
  ]
}
```
✅ Works - 2 enabled methods

### Config 2: Custom Providers
```json
{
  "payment_methods": [
    {"name": "Stripe", "instructions": "...", "is_enabled": true},
    {"name": "Square", "instructions": "...", "is_enabled": true},
    {"name": "Venmo", "instructions": "...", "is_enabled": true}
  ]
}
```
✅ Works - any payment method names accepted

### Config 3: Selective Enable/Disable
```json
{
  "payment_methods": [
    {"name": "Wallet", "instructions": "...", "is_enabled": true},
    {"name": "PayPal", "instructions": "...", "is_enabled": true},
    {"name": "Crypto", "instructions": "...", "is_enabled": true},
    {"name": "Binance", "instructions": "...", "is_enabled": false},
    {"name": "CryptoJar", "instructions": "...", "is_enabled": false}
  ]
}
```
✅ Works - only enabled methods used (3 out of 5)

## Acceptance Criteria

All requirements from the ticket have been met:

- ✅ Deposit command works with any payment methods in config
- ✅ No error logs about missing specific payment methods
- ✅ Deposit command succeeds with Wallet + PayPal + Crypto
- ✅ User can configure custom payment methods
- ✅ Validation only checks "at least one method exists"

## Related Files
- `cogs/wallet.py` - Modified
- `cogs/storefront.py` - Uses same filtering pattern (unchanged)
- `apex_core/config.py` - PaymentMethod dataclass (unchanged)
- `config/payments.json` - User configuration (unchanged)
