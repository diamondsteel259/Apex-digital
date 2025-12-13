# Logging Implementation Guide

This guide provides patterns and examples for completing comprehensive logging across all bot cogs.

## Logging Patterns by Category

### 1. Entry Point Logging (Commands, Buttons, Modals)

**When**: At the very beginning of every user interaction
**Level**: INFO
**Purpose**: Track who invoked what, where, and when

```python
@app_commands.command(name="example")
async def example(self, interaction: discord.Interaction, arg1: str) -> None:
    logger.info(
        "Command: /example | Args: arg1=%s | User: %s (%s) | Guild: %s | Channel: %s",
        arg1,
        interaction.user.name,
        interaction.user.id,
        interaction.guild_id,
        interaction.channel_id,
    )
    # ... rest of command logic
```

**Button Example**:
```python
async def callback(self, interaction: discord.Interaction) -> None:
    logger.info(
        "Button clicked: %s | User: %s (%s) | Guild: %s | Channel: %s",
        self.custom_id or "button",
        interaction.user.name,
        interaction.user.id,
        interaction.guild_id,
        interaction.channel_id,
    )
    # ... rest of callback logic
```

**Modal Example**:
```python
async def on_submit(self, interaction: discord.Interaction) -> None:
    logger.info(
        "Modal submitted: %s | User: %s (%s) | Guild: %s | Input: %s",
        self.title,
        interaction.user.name,
        interaction.user.id,
        interaction.guild_id,
        self.input_field.value[:100],  # First 100 chars
    )
    # ... rest of submission logic
```

### 2. Data Lookup Logging

**When**: Before and after database/config reads
**Level**: DEBUG for success, WARNING for not found, ERROR for failures

```python
# Before lookup
logger.debug("Fetching product | Product ID: %s | User: %s", product_id, user_id)

# After successful lookup
product = await bot.db.get_product(product_id)
if product:
    logger.debug("Product found: %s | ID: %s", product['name'], product_id)
else:
    logger.warning("Product not found | ID: %s | User: %s", product_id, user_id)
    # ... handle not found
```

**User Data Example**:
```python
logger.debug("Fetching user data | User: %s", user_id)
user_row = await bot.db.get_user(user_id)
if user_row:
    logger.debug(
        "User data found | User: %s | Balance: %s cents | Lifetime Spent: %s cents",
        user_id,
        user_row['wallet_balance_cents'],
        user_row['total_lifetime_spent_cents'],
    )
else:
    logger.warning("User not found in database | User: %s", user_id)
```

### 3. Discord API Call Logging

**When**: Before and after Discord API operations (channel/role/message creation, permission changes)
**Level**: INFO for major operations, DEBUG for minor ones, ERROR for failures

```python
# Channel creation
logger.info(
    "Creating ticket channel | Name: %s | Category: %s | User: %s | Guild: %s",
    channel_name,
    category.name,
    user_id,
    guild_id,
)
try:
    channel = await guild.create_text_channel(
        name=channel_name,
        category=category,
        overwrites=overwrites,
    )
    logger.info(
        "Channel created successfully | Name: %s | ID: %s | User: %s",
        channel.name,
        channel.id,
        user_id,
    )
except discord.HTTPException as e:
    logger.error(
        "Failed to create channel | Name: %s | User: %s | Error: %s",
        channel_name,
        user_id,
        str(e),
        exc_info=True,
    )
    # ... handle error
```

**Role Assignment Example**:
```python
logger.debug("Assigning role | Role: %s | User: %s | Guild: %s", role.name, user_id, guild_id)
try:
    await member.add_roles(role, reason=f"Earned through purchase")
    logger.info("Role assigned successfully | Role: %s | User: %s", role.name, user_id)
except discord.Forbidden:
    logger.error("Permission denied assigning role | Role: %s | User: %s", role.name, user_id)
```

### 4. Business Logic Logging

**When**: At key steps in workflows
**Level**: INFO for important steps, DEBUG for minor steps

```python
# Payment processing example
logger.info(
    "Processing payment | User: %s | Product: %s | Amount: %s cents | Method: %s",
    user_id,
    product_name,
    amount_cents,
    payment_method,
)

# VIP tier calculation
vip_tier = calculate_vip_tier(lifetime_spent, config)
logger.debug("VIP tier calculated | User: %s | Tier: %s", user_id, vip_tier.name if vip_tier else "None")

# Discount application
discount_percent = calculate_discount(user_id, product_id, vip_tier)
logger.debug(
    "Discount calculated | User: %s | Product: %s | Discount: %s%%",
    user_id,
    product_id,
    discount_percent,
)

# Order completion
logger.info(
    "Order completed | Order ID: %s | User: %s | Product: %s | Amount: %s cents",
    order_id,
    user_id,
    product_name,
    final_amount,
)
```

### 5. Error Logging

**When**: In all exception handlers
**Level**: ERROR
**Important**: Always include `exc_info=True` for full stack trace

```python
try:
    # ... operation
except ValueError as e:
    logger.error(
        "Validation error in %s | User: %s | Input: %s | Error: %s",
        operation_name,
        user_id,
        user_input,
        str(e),
        exc_info=True,
    )
    await interaction.followup.send("Invalid input. Please try again.", ephemeral=True)
except discord.HTTPException as e:
    logger.error(
        "Discord API error in %s | User: %s | Error: %s",
        operation_name,
        user_id,
        str(e),
        exc_info=True,
    )
    await interaction.followup.send("A Discord error occurred. Please try again.", ephemeral=True)
except Exception as e:
    logger.error(
        "Unexpected error in %s | User: %s | Error: %s",
        operation_name,
        user_id,
        str(e),
        exc_info=True,
    )
    await interaction.followup.send("An unexpected error occurred. Please contact support.", ephemeral=True)
```

### 6. State Change Logging

**When**: When database records or config values change
**Level**: INFO
**Important**: Log old value → new value for auditing

```python
# Balance change
old_balance = user_row['wallet_balance_cents']
new_balance = await bot.db.update_balance(user_id, amount_change)
logger.info(
    "Balance updated | User: %s | Old: %s cents | New: %s cents | Change: %s cents | Reason: %s",
    user_id,
    old_balance,
    new_balance,
    amount_change,
    reason,
)

# Order status change
old_status = order['status']
await bot.db.update_order_status(order_id, new_status)
logger.info(
    "Order status updated | Order ID: %s | User: %s | Status: %s -> %s",
    order_id,
    user_id,
    old_status,
    new_status,
)

# Ticket closure
logger.info(
    "Ticket closed | Ticket ID: %s | Channel: %s | User: %s | Closed by: %s",
    ticket_id,
    channel_id,
    ticket_owner_id,
    closer_user_id,
)
```

## Cog-Specific Implementation Checklist

### storefront.py ✅ (Completed)
- [x] CategorySelect callback
- [x] SubCategorySelect callback  
- [x] VariantSelect callback
- [x] OpenTicketButton callback
- [x] CategoryPaginatorButton callback
- [x] WalletPaymentButton callback (full flow)
- [x] PaymentProofUploadButton callback
- [x] RequestCryptoAddressButton callback
- [ ] _show_sub_categories method
- [ ] _show_products method
- [ ] _handle_open_ticket method
- [ ] _calculate_discount method

### wallet.py ⚠️ (Partial)
- [x] /deposit command entry
- [ ] Deposit ticket channel creation
- [ ] /balance command
- [ ] /withdraw command (admin)
- [ ] Admin deposit operations
- [ ] Admin withdraw operations
- [ ] Payment method validation

### orders.py ⚠️ (Not Started)
- [ ] /orders command
- [ ] Order filtering logic
- [ ] Order embed formatting
- [ ] /admin_orders command
- [ ] Order search functionality
- [ ] Warranty status checks

### ticket_management.py ✅ (Partial)
- [x] General support button
- [x] Refund support button
- [x] GeneralSupportModal.on_submit (full flow)
- [ ] RefundSupportModal.on_submit
- [ ] /close command
- [ ] /delete command
- [ ] /add_user command
- [ ] /remove_user command
- [ ] Transcript generation
- [ ] S3 upload
- [ ] Inactivity check task

### refund_management.py ⚠️ (Not Started)
- [ ] /submitrefund command
- [ ] Refund eligibility checks
- [ ] Refund amount calculation
- [ ] /listrefunds command
- [ ] /approverefund command
- [ ] /denyrefund command
- [ ] Wallet crediting
- [ ] Notification sending

### referrals.py ⚠️ (Not Started)
- [ ] /invite command
- [ ] Referral code generation
- [ ] /setref command
- [ ] Referral relationship creation
- [ ] /profile command
- [ ] Referral stats calculation
- [ ] /payoutreferral command (admin)
- [ ] Cashback payout processing
- [ ] /referralstats command (admin)

### manual_orders.py ⚠️ (Not Started)
- [ ] /manual_complete command
- [ ] Amount validation
- [ ] Order creation
- [ ] VIP tier updates
- [ ] Role assignment
- [ ] Post-purchase processing

### product_import.py ⚠️ (Not Started)
- [ ] /upload_products command
- [ ] File validation
- [ ] CSV parsing
- [ ] Product validation
- [ ] Batch import
- [ ] Error collection and reporting

### notifications.py ⚠️ (Not Started)
- [ ] Warranty notification task start
- [ ] Warranty expiry query
- [ ] User grouping logic
- [ ] DM sending
- [ ] Admin summary
- [ ] /notify_warranty_expiry command

### financial_cooldown_management.py ⚠️ (Not Started)
- [ ] !cooldown-check command
- [ ] Cooldown retrieval
- [ ] !cooldown-reset command
- [ ] Cooldown clearing
- [ ] !cooldown-reset-all command

## Implementation Priority

1. **Critical Financial Operations** (Highest Priority):
   - refund_management.py (money handling)
   - manual_orders.py (money handling)
   - referrals.py (money handling)
   - wallet.py (complete remaining)

2. **User-Facing Features** (High Priority):
   - orders.py (order viewing)
   - ticket_management.py (complete remaining)
   - product_import.py (data operations)

3. **Background Tasks & Admin Tools** (Medium Priority):
   - notifications.py
   - financial_cooldown_management.py

4. **Remaining storefront.py methods** (Low Priority):
   - Already has comprehensive coverage at entry points

## Testing After Implementation

For each completed cog, test:
1. Run the command/click the button
2. Check logs show entry point with user/guild/channel
3. Trigger an error condition
4. Check logs show full error with exc_info=True
5. Complete a successful flow
6. Check logs show all major steps
7. Verify state changes logged with old→new values

## Log Level Guidelines

- **DEBUG**: Data lookups, minor steps, internal state
- **INFO**: User actions, major workflow steps, successful operations, state changes
- **WARNING**: Validation failures, not found, rate limits, non-critical issues
- **ERROR**: Exceptions, API failures, critical issues requiring attention

## Common Pitfalls to Avoid

1. **Don't log sensitive data**: Passwords, tokens, full credit card numbers
2. **Do log context**: Always include user_id, guild_id for debugging
3. **Use exc_info=True**: For all exception logging (full stack trace)
4. **Don't spam DEBUG**: Only log what's useful for debugging
5. **Log before and after**: For async operations that might fail
6. **Include IDs**: Discord IDs, database IDs, order IDs for traceability
7. **Log state changes**: Always log old→new for auditing
