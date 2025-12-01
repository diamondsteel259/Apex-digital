# Referral Cashback Batching System

## Overview

The Referral Cashback Batching System automates the process of paying out accumulated referral cashback to users who have referred others to the platform. This system allows administrators to process cashback payouts efficiently, either in bulk or for individual users.

## Features

### 1. Batch Processing
- **Command**: `!sendref-cashb`
- **Description**: Process all pending cashback for all eligible referrers
- **Permissions**: Admin only
- **Features**:
  - Automatic detection of all referrers with pending cashback
  - Excludes blacklisted users automatically
  - Shows comprehensive summary before execution
  - Displays top 10 payouts by amount
  - Interactive confirmation with Confirm/Cancel buttons
  - Detailed results reporting

### 2. Individual User Processing
- **Command**: `!sendref-cashb @user`
- **Description**: Process cashback for a specific referrer
- **Permissions**: Admin only
- **Features**:
  - Targeted payout for single user
  - Validates user has pending cashback
  - Checks if user is blacklisted
  - Interactive confirmation workflow
  - Individual audit trail

### 3. Automatic Wallet Integration
- Credits user wallet balance automatically
- Creates audit trail in `wallet_transactions` table
- Transaction type: `referral_cashback`
- Includes metadata: batch_id, referral_count

### 4. User Notifications
- Automatic DM sent to each referrer upon payout
- Shows amount credited
- Displays number of referrals
- Shows new wallet balance
- Includes batch ID for reference

### 5. Audit Trail
- Complete logging to #audit channel
- Batch ID for traceability (format: `BATCH-YYYYMMDD-HHMMSS`)
- Records:
  - Users paid
  - Total amount distributed
  - Failed payouts (if any)
  - Processing timestamp
  - Admin who initiated the batch

## Database Methods

### `get_all_pending_referral_cashbacks()`
Returns list of all referrers with pending cashback (earned > paid).

**Returns:**
```python
[
    {
        "referrer_id": 123456789,
        "pending_cents": 1500,  # $15.00
        "referral_count": 10
    },
    ...
]
```

**Features:**
- Excludes blacklisted users
- Groups by referrer_id
- Calculates pending as (earned - paid)
- Ordered by pending amount (descending)

### `get_pending_cashback_for_user(referrer_id)`
Returns pending cashback details for a specific referrer.

**Parameters:**
- `referrer_id` (int): Discord ID of the referrer

**Returns:**
```python
{
    "pending_cents": 1500,
    "referral_count": 10,
    "is_blacklisted": False,
    "referral_details": [
        {"user_id": 111111, "amount_cents": 500},
        {"user_id": 222222, "amount_cents": 1000}
    ]
}
```

### `mark_cashback_paid(referrer_id, amount_cents)`
Updates referrals table to mark cashback as paid.

**Parameters:**
- `referrer_id` (int): Discord ID of the referrer
- `amount_cents` (int): Amount being paid out

**Action:**
Sets `cashback_paid_cents = cashback_earned_cents` for all non-blacklisted referrals for this referrer.

## Usage Examples

### Batch Mode (All Users)

```
Admin: !sendref-cashb
Bot:   [Displays summary embed]
       💰 Referral Cashback Batch Summary
       
       📊 Batch Statistics
       Users Receiving Payment: 15
       Total Amount: $127.50
       Average Per User: $8.50
       
       🏆 Top Payouts
       1. @User1 - $25.00 (50 referrals)
       2. @User2 - $18.50 (37 referrals)
       3. @User3 - $15.25 (30 referrals)
       ...
       
       [Confirm] [Cancel]

Admin: [Clicks Confirm]
Bot:   ✅ Referral Cashback Batch Complete
       
       📊 Results
       Users Paid: 15
       Total Distributed: $127.50
       Failed: 0
       Batch ID: BATCH-20231215-143022
```

### Individual User Mode

```
Admin: !sendref-cashb @User1
Bot:   💰 Individual Referral Cashback Payout
       
       Payment Details
       User: @User1
       Amount: $25.00
       Active Referrals: 50
       
       [Confirm] [Cancel]

Admin: [Clicks Confirm]
Bot:   ✅ Referral Cashback Batch Complete
       
       📊 Results
       Users Paid: 1
       Total Distributed: $25.00
       Failed: 0
       Batch ID: BATCH-20231215-143045
```

### User Notification (DM)

```
Bot DM to Referrer:
💰 Referral Cashback Received!

Your referral cashback has been paid out!

Amount Credited: $25.00
From Referrals: 50 users
New Wallet Balance: $125.00

Thank you for helping grow our community! 🎉

Apex Core • Batch ID: BATCH-20231215-143022
```

## Transaction Details

### Wallet Transaction Entry
```python
{
    "user_discord_id": 123456789,
    "amount_cents": 2500,  # $25.00
    "balance_after_cents": 12500,  # $125.00
    "transaction_type": "referral_cashback",
    "description": "Referral cashback - 50 active referrals",
    "metadata": {
        "batch_id": "BATCH-20231215-143022",
        "referral_count": 50
    }
}
```

### Referrals Table Update
```sql
UPDATE referrals
SET cashback_paid_cents = cashback_earned_cents
WHERE referrer_user_id = ?
  AND is_blacklisted = 0
  AND (cashback_earned_cents - cashback_paid_cents) > 0
```

## Error Handling

### Missing Wallet
- System automatically creates wallet for user via `ensure_user()`
- No manual intervention required

### Blacklisted Users
- Automatically excluded from batch processing
- Individual mode shows error message
- No cashback credited

### Failed Payouts
- Individual user failures don't stop batch processing
- Failed users logged in results
- Error details included in summary
- Pending cashback preserved for retry

### No Pending Cashback
- Batch mode: Shows "No pending cashback" message
- Individual mode: Shows "User has no pending cashback" error

## Audit Channel Log

```
💰 Referral Cashback Batch Processed
Batch ID: BATCH-20231215-143022

Summary
Users Paid: 15
Total Amount: $127.50
Failed: 0
Processed By: @AdminUser
Mode: Batch

Batch ID: BATCH-20231215-143022
```

## Implementation Details

### Confirmation View
- **Class**: `CashbackConfirmView`
- **Timeout**: 120 seconds
- **Buttons**: Confirm (green), Cancel (red)
- **Permission Check**: Only command issuer can interact
- **Lifecycle**: Automatically disables buttons after action

### Batch ID Format
- Pattern: `BATCH-YYYYMMDD-HHMMSS`
- Example: `BATCH-20231215-143022`
- Timezone: UTC
- Purpose: Unique identifier for traceability

### Processing Flow
1. Admin issues command
2. System queries pending cashbacks
3. Displays summary with confirmation buttons
4. Admin clicks Confirm
5. System processes each user:
   - Ensures wallet exists
   - Credits wallet balance
   - Logs transaction
   - Updates referrals table
   - Sends DM notification
6. Reports results to admin
7. Logs to audit channel

## Edge Cases

### Zero Pending Cashback
- Batch: Shows informational message
- Individual: Shows error message
- No processing occurs

### All Users Blacklisted
- Treated same as zero pending cashback
- No users to process
- Informational message displayed

### Partial Failures
- Successful payouts are committed
- Failed payouts are logged but don't rollback successful ones
- Results show both success and failure counts
- Failed users can be retried later

### User Not in Server
- DM notification may fail (gracefully handled)
- Cashback still credited to wallet
- Logged as info (not error)

### Concurrent Executions
- Wallet updates use asyncio.Lock for thread safety
- Database uses IMMEDIATE transactions
- No double-payment risk

## Best Practices

### Regular Batching
- Run weekly or bi-weekly batches
- Reduces individual processing overhead
- Provides consistent payout schedule

### Audit Trail Review
- Check #audit channel after each batch
- Verify batch IDs in wallet transactions
- Monitor for failed payouts

### Individual Payouts
- Use for urgent requests
- Special cases or VIP users
- Testing after system changes

### Monitoring
- Track total distributed per batch
- Monitor average payout per user
- Watch for unusually high pending amounts

## Configuration

Currently the system does not require additional configuration beyond existing referral settings:

- **Cashback Rate**: 0.5% (defined in `log_referral_purchase()`)
- **Blacklist Support**: Built-in via `is_blacklisted` flag
- **Admin Role**: Uses existing `role_ids.admin` from config.json

### Future: Automatic Scheduling (Optional)

Can be extended with config.json settings:

```json
{
  "referral_settings": {
    "auto_batch_enabled": true,
    "batch_day": "friday",
    "batch_hour_utc": 15
  }
}
```

Would require implementing a discord.py task loop in ReferralsCog.

## Security Considerations

### Admin-Only Access
- Command restricted to users with admin role
- Confirmation required before execution
- No user can trigger their own payout

### Double-Payment Prevention
- `mark_cashback_paid()` sets paid = earned
- Query filters for (earned > paid)
- Subsequent runs won't re-pay same cashback

### Audit Trail
- Complete logging to #audit channel
- Batch IDs for traceability
- Wallet transactions preserve metadata

### Error Recovery
- Failed payouts don't lose data
- Pending cashback preserved
- Can be retried safely

## Testing

### Manual Testing Checklist
1. ✅ Create test referrals with pending cashback
2. ✅ Run `!sendref-cashb` (batch mode)
3. ✅ Verify confirmation embed displays correctly
4. ✅ Click Confirm and verify payouts
5. ✅ Check wallet balances updated
6. ✅ Verify wallet_transactions created
7. ✅ Confirm referrals table updated
8. ✅ Check DMs sent to users
9. ✅ Verify audit channel log
10. ✅ Test individual mode with `!sendref-cashb @user`
11. ✅ Test blacklist exclusion
12. ✅ Test zero pending cashback case
13. ✅ Test non-admin user rejection

### Automated Tests
See `test_referral_cashback.py` for database method tests.

## Troubleshooting

### Issue: Cashback not showing in pending
**Check:**
- User has referred someone (`/invites` command)
- Referred user made purchases
- Referrer is not blacklisted
- Cashback not already paid

### Issue: Batch processes 0 users
**Check:**
- Any users have pending cashback > 0
- Users are not blacklisted
- Database referrals table populated

### Issue: Individual payout fails
**Check:**
- User exists in database
- User has pending cashback
- User not blacklisted
- Admin has permission

### Issue: DM notification not sent
**Reason:** User has DMs disabled or bot is not mutual contact
**Impact:** None - cashback still credited
**Resolution:** User can check wallet balance

## Future Enhancements

1. **Automatic Scheduling**: Weekly task loop for batch processing
2. **History Command**: `!sendref-cashb history` to view past batches
3. **CSV Export**: Export batch results to spreadsheet
4. **Notification Settings**: User preference for DM notifications
5. **Batch Limits**: Configure max users per batch
6. **Retry Logic**: Automatic retry for failed payouts
7. **Dashboard**: Web interface for batch monitoring

## Related Documentation

- [REFERRAL_SYSTEM_IMPLEMENTATION.md](REFERRAL_SYSTEM_IMPLEMENTATION.md) - Core referral system
- [README.md](README.md) - Bot overview and setup
- [AUDIT_REPORT.md](AUDIT_REPORT.md) - Complete system audit

## Support

For issues or questions about the referral cashback batching system:
1. Check this documentation
2. Review logs in #audit channel
3. Examine wallet_transactions table
4. Check database referrals table
5. Contact system administrator
