# Referral/Invite Rewards System Implementation

## Overview

The referral rewards system allows users to earn 0.5% cashback on all purchases made by users they refer. The system tracks referrals, calculates cashback, and provides comprehensive statistics and management tools.

## Database Schema

### Referrals Table (Migration v10)

```sql
CREATE TABLE referrals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    referrer_user_id INTEGER NOT NULL,
    referred_user_id INTEGER UNIQUE NOT NULL,
    referred_total_spend_cents INTEGER DEFAULT 0,
    cashback_earned_cents INTEGER DEFAULT 0,
    cashback_paid_cents INTEGER DEFAULT 0,
    is_blacklisted INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(referrer_user_id) REFERENCES users(discord_id) ON DELETE CASCADE,
    FOREIGN KEY(referred_user_id) REFERENCES users(discord_id) ON DELETE CASCADE
)
```

**Indexes:**
- `idx_referrals_referrer` on `referrer_user_id`
- `idx_referrals_referred` on `referred_user_id`
- `idx_referrals_blacklist` on `is_blacklisted`

**Key Constraints:**
- `referred_user_id` is UNIQUE - each user can only be referred once
- Foreign keys cascade on delete to maintain referential integrity

## Database Methods

### Core Methods

1. **`create_referral(referrer_id: int, referred_id: int) -> int`**
   - Creates a referral link between two users
   - Validates against self-referral
   - Validates against duplicate referrals (UNIQUE constraint)
   - Returns referral record ID

2. **`log_referral_purchase(referred_id: int, order_id: int, amount_cents: int) -> Optional[int]`**
   - Logs a purchase by a referred user
   - Calculates 0.5% cashback
   - Updates `referred_total_spend_cents` and `cashback_earned_cents`
   - Skips if user is blacklisted
   - Returns cashback amount or None

3. **`get_referral_stats(referrer_id: int) -> dict`**
   - Returns comprehensive statistics:
     - `referral_count`: Number of users referred
     - `total_spend_cents`: Total spent by referred users
     - `total_earned_cents`: Total cashback earned
     - `total_paid_cents`: Total cashback paid out
     - `pending_cents`: Unpaid cashback (earned - paid)

4. **`calculate_pending_cashback(referrer_id: int) -> int`**
   - Returns pending (unpaid) cashback in cents

5. **`get_referrals(referrer_id: int) -> list[aiosqlite.Row]`**
   - Returns all referral records for a user
   - Ordered by creation date (newest first)

6. **`blacklist_referral_user(user_id: int) -> bool`**
   - Marks all referrals where user is the referrer as blacklisted
   - Returns True if records were updated, False otherwise

7. **`get_referrer_for_user(referred_id: int) -> Optional[int]`**
   - Returns the referrer's Discord ID for a given user
   - Returns None if user wasn't referred

## Purchase Integration

The referral system automatically tracks purchases through two integration points:

### 1. Wallet Purchases (`purchase_product`)

```python
# After order creation and wallet transaction
try:
    await self.log_referral_purchase(user_discord_id, order_id, price_paid_cents)
except Exception as e:
    logger.error(f"Error logging referral purchase for user {user_discord_id}: {e}")
```

### 2. Manual Orders (`create_manual_order`)

```python
# After order creation and lifetime spend update
try:
    await self.log_referral_purchase(user_discord_id, order_id, price_paid_cents)
except Exception as e:
    logger.error(f"Error logging referral purchase for user {user_discord_id}: {e}")
```

**Error Handling:** All referral tracking is wrapped in try-except blocks to ensure purchases complete even if referral tracking fails.

## User Commands

### `/invite`

**Description:** Get your referral link and earn cashback on referrals

**Functionality:**
- Displays user's referral code (their Discord ID)
- Shows current referral statistics
- Explains how the system works (0.5% cashback)
- Sends a DM with referral code for easy sharing

**Output:**
```
🎁 Your Referral Program

Earn 0.5% cashback on all purchases made by users you refer!

Your Referral Code: `123456789`

How it works:
1. Share your referral code with friends
2. They use /setref {your_code} when they join
3. You earn 0.5% cashback on their purchases
4. Cashback accumulates and can be paid out by staff

📊 Your Stats
Total Invited: X users
Total Referred Spend: $XXX.XX
Total Cashback Earned: $XXX.XX
Pending Cashback: $XXX.XX
```

### `/invites`

**Description:** View detailed statistics about your referrals

**Functionality:**
- Shows comprehensive referral statistics
- Lists up to 10 most recent referrals with individual stats
- Displays blacklisted status for each referral
- Shows total earnings per referral

**Output:**
```
📊 Your Referral Stats

Summary:
Total Invited: X users
Total Referred Spend: $XXX.XX
Total Cashback Earned: $XXX.XX
Cashback Paid Out: $XXX.XX
Pending Cashback: $XXX.XX

Your Referrals (X total):
1. @Username - $XXX.XX spent - $X.XX earned - ✅ Active
2. @Username - $XXX.XX spent - $X.XX earned - 🚫 Blacklisted
...
```

### `/setref <referrer_code>`

**Description:** Set your referrer to earn them cashback on your purchases

**Parameters:**
- `referrer_code`: The referral code (Discord ID) from the person who invited you

**Functionality:**
- Links a new user to their referrer
- One-time only operation (UNIQUE constraint)
- Validates referrer exists in the server
- Prevents self-referral
- Sends DM notifications to both parties

**Validations:**
- Referrer code must be valid numeric Discord ID
- Cannot refer yourself
- Cannot be referred more than once
- Referrer must be a member of the server

**Notifications:**
- Referrer receives: "🎉 New Referral! {username} has joined using your referral code!"
- Referred user receives: "✅ Referral Confirmed. You were invited by {referrer}!"

### `/profile [member]`

**Description:** View your profile including referral stats

**Parameters:**
- `member` (optional): Member to view profile for (admin only)

**Functionality:**
- Shows wallet balance and lifetime spending
- Shows total order count
- Shows comprehensive referral statistics
- Shows account creation date and first purchase date

**Output:**
```
👤 Profile • Username

💰 Wallet & Spending
Balance: $XXX.XX
Lifetime Spent: $XXX.XX
Total Orders: XX

🎁 Referral Stats
Total Referrals: X users
Referred Spend: $XXX.XX
Cashback Earned: $XXX.XX
Cashback Paid Out: $XXX.XX
Pending Cashback: $XXX.XX

📅 Account Info
Joined: YYYY-MM-DD
First Purchase: YYYY-MM-DD HH:MM:SS
```

## Admin Commands

### `!referral-blacklist @user`

**Aliases:** `!refund-blacklist`

**Description:** Blacklist a user from earning referral cashback

**Permissions:** Admin only

**Functionality:**
- Marks all referrals where the user is the referrer as blacklisted
- User can still use the store
- User no longer earns cashback on referred purchases
- Sends DM notification to the blacklisted user

**Output:**
```
🚫 User Blacklisted

User: @Username (123456789)
Action: All referral earnings have been marked as blacklisted.

This user can still use the store but will no longer earn referral cashback.
```

**User Notification:**
```
⚠️ Referral Program Suspension

Your referral program access has been suspended due to policy violations.

You can still use the store, but you will no longer earn referral cashback.
Contact staff if you have questions.
```

## Fraud Prevention

### Blacklist System

- **Purpose:** Prevent fraudulent referral activity
- **Retroactive:** Blacklisting affects all existing referrals
- **Non-intrusive:** Blacklisted users can still make purchases
- **Trackable:** `is_blacklisted` field allows queries and reports

### Validation Checks

1. **Self-referral prevention:** Cannot use your own code
2. **Duplicate prevention:** UNIQUE constraint on `referred_user_id`
3. **Server membership:** Referrer must be in the server
4. **One-time only:** Users can only be referred once ever

## Cashback Calculation

**Rate:** 0.5% (0.005) of purchase amount

**Calculation:**
```python
cashback_cents = int(amount_cents * 0.005)
```

**Example:**
- Purchase: $100.00 (10,000 cents)
- Cashback: $0.50 (50 cents)

**Rounding:** Integer conversion rounds down to nearest cent

## Pending vs Paid Cashback

### Pending Cashback
- Earned but not yet paid out to user's wallet
- Accumulates with each referred purchase
- Tracked in `cashback_earned_cents` field

### Paid Cashback
- Amount already credited to referrer's wallet
- Tracked in `cashback_paid_cents` field
- Requires manual staff payout (future feature)

### Calculation
```
Pending = cashback_earned_cents - cashback_paid_cents
```

## Error Handling

### Purchase Integration
- Referral tracking errors are logged but don't block purchases
- Uses try-except blocks around `log_referral_purchase()`
- Ensures store functionality continues even if referral system fails

### User-facing Errors
- Invalid referral code: "Invalid referral code. Please provide a valid numeric code."
- Self-referral: "You cannot refer yourself!"
- Already referred: "You have already been referred by {user}. Each user can only be referred once."
- Referrer not found: "The referrer must be a member of this server."

## DM Notifications

### On `/invite` Command
```
🎁 Your Referral Link

Your referral code is: `123456789`

Share this code with friends! They can use /setref {your_code} to link their account to you.

You earn 0.5% cashback on all their purchases!
```

### On Successful `/setref`

**To Referrer:**
```
🎉 New Referral!

Username (DisplayName) has joined using your referral code!

You will now earn 0.5% cashback on all their purchases.
```

**To Referred User:**
```
✅ Referral Confirmed

You were invited by ReferrerName!

They will earn 0.5% cashback on your purchases. Enjoy shopping at Apex Core!
```

### On Blacklist

**To Blacklisted User:**
```
⚠️ Referral Program Suspension

Your referral program access has been suspended due to policy violations.

You can still use the store, but you will no longer earn referral cashback.
Contact staff if you have questions.
```

## Technical Implementation

### Files Modified

1. **`apex_core/database.py`**
   - Added migration v10 (`_migration_v10`)
   - Updated `target_schema_version` to 10
   - Added 7 referral-related methods
   - Integrated referral tracking into `purchase_product()` and `create_manual_order()`

2. **`cogs/referrals.py`** (NEW)
   - 330+ lines
   - 4 slash commands: `/invite`, `/invites`, `/setref`, `/profile`
   - 1 prefix command: `!referral-blacklist`
   - Comprehensive embed formatting
   - DM notification system
   - Error handling and validation

### Code Quality

- **Type hints:** All methods properly typed
- **Async patterns:** Consistent async/await usage
- **Error handling:** Comprehensive try-except blocks
- **Logging:** Detailed error logging with context
- **Documentation:** Full docstrings on all methods

## Testing Checklist

### Database Migration
- [ ] Migration v10 creates referrals table
- [ ] All indexes are created
- [ ] Foreign keys work correctly
- [ ] UNIQUE constraint prevents duplicates

### User Commands
- [ ] `/invite` displays stats correctly
- [ ] `/invite` sends DM with code
- [ ] `/invites` shows detailed breakdown
- [ ] `/setref` creates referral link
- [ ] `/setref` prevents self-referral
- [ ] `/setref` prevents duplicates
- [ ] `/setref` validates server membership
- [ ] `/setref` sends DM notifications
- [ ] `/profile` shows all stats correctly

### Admin Commands
- [ ] `!referral-blacklist` requires admin
- [ ] Blacklist prevents future cashback
- [ ] Blacklist sends DM notification
- [ ] Blacklist doesn't affect store usage

### Purchase Integration
- [ ] Wallet purchases track cashback
- [ ] Manual orders track cashback
- [ ] Cashback calculates correctly (0.5%)
- [ ] Blacklisted users don't earn cashback
- [ ] Errors don't block purchases

### Edge Cases
- [ ] Self-referral blocked
- [ ] Duplicate referral blocked
- [ ] Non-existent referrer handled
- [ ] Blacklisted user can still shop
- [ ] Stats show 0 for new users

## Future Enhancements

1. **Automated Payout:** Command to batch-pay pending cashback to wallets
2. **Referral Leaderboard:** Show top referrers by earnings
3. **Tiered Cashback:** Higher percentages for more referrals
4. **Referral Bonuses:** One-time bonuses for reaching milestones
5. **Analytics Dashboard:** Admin view of referral program health
6. **Export Reports:** CSV export of referral data
7. **Webhook Integration:** Real-time notifications to Discord channels
8. **Referral History:** Detailed per-referral purchase history

## Migration Notes

- **Schema Version:** Updated from 9 to 10
- **Backward Compatible:** Old data is preserved
- **No Downtime:** Migration runs on bot startup
- **Idempotent:** Can run migration multiple times safely
- **Rollback:** Keep database backup before first run

## Performance Considerations

- **Indexes:** All lookup columns are indexed for fast queries
- **Async Operations:** All database calls are async
- **Error Isolation:** Referral failures don't impact purchases
- **Efficient Queries:** Uses aggregation for statistics
- **Minimal Overhead:** Single query per purchase for referral check

## Security Considerations

- **Input Validation:** All user inputs validated
- **SQL Injection:** Protected by parameterized queries
- **Permission Checks:** Admin commands require role
- **Rate Limiting:** Discord's built-in rate limiting applies
- **DM Privacy:** DMs fail gracefully if blocked
