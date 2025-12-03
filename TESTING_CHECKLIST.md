# Apex Digital Bot - Manual Testing Checklist

This checklist provides a comprehensive guide for manual functional testing of the bot after deployment.

---

## Pre-Testing Setup

- [ ] Bot is online and connected to Discord
- [ ] All configuration completed (config.json)
- [ ] All required channels created
- [ ] All required roles created
- [ ] Database initialized (bot.db exists)
- [ ] Test users created (minimum 2 users for referral testing)
- [ ] Admin has access to admin commands

---

## 1. Bot Startup Tests

### 1.1. Initial Startup

- [ ] Bot starts without errors
- [ ] All 10 cogs load successfully:
  - [ ] StorefrontCog
  - [ ] WalletCog
  - [ ] OrdersCog
  - [ ] ManualOrdersCog
  - [ ] ProductImportCog
  - [ ] NotificationsCog
  - [ ] TicketManagementCog
  - [ ] RefundManagementCog
  - [ ] ReferralsCog
  - [ ] SetupCog
- [ ] Database connection established
- [ ] All 11 migrations applied
- [ ] Persistent views registered
- [ ] No errors in startup logs

### 1.2. Feature Availability Check

- [ ] chat-exporter status logged (installed/fallback)
- [ ] boto3 status logged (installed/local storage)
- [ ] Rate limiting system initialized
- [ ] Logging channels accessible

---

## 2. Setup Commands (Admin Only)

### 2.1. Storefront Setup

- [ ] Run `!setup_store` command
- [ ] Persistent message created with embed
- [ ] "Browse Products" button appears
- [ ] Button is clickable
- [ ] Message stored in permanent_messages table

### 2.2. Ticket Setup

- [ ] Run `!setup_tickets` command
- [ ] Persistent message created with embed
- [ ] "General Support" button appears
- [ ] "Refund Support" button appears
- [ ] Both buttons are clickable
- [ ] Message stored in permanent_messages table

---

## 3. Product Management

### 3.1. Product Import

- [ ] Open products_template.xlsx
- [ ] Add at least 5 test products
- [ ] Export as CSV
- [ ] Run `/import_products` command
- [ ] Attach CSV file
- [ ] Import completes successfully
- [ ] Success message shows count of imported products
- [ ] Products appear in database

### 3.2. Product Verification

- [ ] Click "Browse Products" button
- [ ] Main category dropdown appears
- [ ] Categories match imported products
- [ ] Select main category
- [ ] Sub-category dropdown appears
- [ ] Select sub-category
- [ ] Product details display correctly:
  - [ ] Service name
  - [ ] Variant name
  - [ ] Price (formatted as $X.XX)
  - [ ] Start time
  - [ ] Duration
  - [ ] Refill period
  - [ ] Additional info

---

## 4. Wallet System Tests

### 4.1. Initial Balance Check

- [ ] User runs `/balance`
- [ ] Response shows $0.00 balance
- [ ] Response shows $0.00 lifetime spent
- [ ] No errors

### 4.2. Deposit Request

- [ ] User runs `/deposit`
- [ ] Modal appears with amount field
- [ ] User enters amount (e.g., "10.00")
- [ ] Submit button works
- [ ] User receives confirmation message
- [ ] Admin notified in #payments channel

### 4.3. Admin Wallet Credit

- [ ] Admin runs `!deposit @user 1000` (for $10.00)
- [ ] User receives DM notification
- [ ] Balance updated in database
- [ ] Transaction logged in wallet_transactions
- [ ] Audit log posted to #audit channel
- [ ] User runs `/balance` and sees $10.00

### 4.4. Balance Display

- [ ] `/balance` shows correct balance
- [ ] Lifetime spent shows $0.00
- [ ] VIP tier shows "None" or "Client" if purchased
- [ ] Formatting correct ($X.XX)

---

## 5. Purchase Flow Tests

### 5.1. Wallet Payment

- [ ] User has sufficient balance (from step 4.3)
- [ ] User clicks "Browse Products"
- [ ] User selects category → sub-category → product
- [ ] Product details display
- [ ] "Pay with Wallet" button appears (green if balance sufficient)
- [ ] User clicks "Pay with Wallet"
- [ ] Rate limit check passes (max 3 uses per 5 minutes)
- [ ] Wallet balance deducted
- [ ] Order created in database
- [ ] Order ticket channel created (ticket-username-order1)
- [ ] Payment embed posted in order ticket with:
  - [ ] Product details
  - [ ] Payment amount
  - [ ] All enabled payment methods
  - [ ] Interactive buttons
- [ ] User receives order confirmation DM
- [ ] Admin notified in #orders channel
- [ ] Transaction logged in wallet_transactions

### 5.2. Payment Proof Upload

- [ ] User in order ticket uploads image/file
- [ ] Bot detects attachment
- [ ] User receives DM confirmation
- [ ] Admin notified with attachment link
- [ ] Attachment metadata stored

### 5.3. Manual Order Completion

- [ ] Admin runs `!manual_complete @user ProductName 999` (for $9.99)
- [ ] Rate limit check passes (max 5 uses per minute)
- [ ] Order created in database
- [ ] User balance NOT deducted (manual payment)
- [ ] User lifetime spent updated
- [ ] VIP tier checked and role assigned if threshold met
- [ ] Referral cashback tracked if user has referrer
- [ ] Order logged to #orders channel
- [ ] User receives DM with order details

---

## 6. VIP Tier System Tests

### 6.1. First Purchase (Client Role)

- [ ] User with $0.00 spent makes first purchase
- [ ] "Client" role assigned automatically
- [ ] Role appears in user's role list
- [ ] Role assignment logged to #audit

### 6.2. Tier Progression

Test tier progression by making purchases to reach thresholds:

- [ ] User with $50+ spent gets "Apex VIP" role (1.5% discount)
- [ ] User with $100+ spent gets "Apex Elite" role (2.5% discount)
- [ ] User with $500+ spent gets "Apex Legend" role (3.75% discount)
- [ ] User with $1000+ spent gets "Apex Sovereign" role (5% discount)
- [ ] Lower tier roles removed when advancing
- [ ] Role change logged to #audit

### 6.3. Discount Application

- [ ] VIP user browses product
- [ ] Original price displayed
- [ ] Discounted price calculated correctly
- [ ] Discount percentage shown
- [ ] Final price charged is discounted amount

### 6.4. Profile Command

- [ ] User runs `/profile`
- [ ] Rate limit check passes (max 5 uses per minute)
- [ ] Profile displays:
  - [ ] Wallet balance
  - [ ] Total spent
  - [ ] VIP tier name
  - [ ] Discount percentage
  - [ ] Referral stats (referrer, invites, cashback earned/paid)

---

## 7. Ticket System Tests

### 7.1. General Support Ticket

- [ ] User clicks "General Support" button on ticket panel
- [ ] Ticket channel created: `ticket-username-QA`
- [ ] User added to channel permissions
- [ ] Admin role added to channel permissions
- [ ] Ticket type set to "support" in database
- [ ] Welcome message posted with:
  - [ ] Ticket ID
  - [ ] User info
  - [ ] Operating hours
  - [ ] Instructions
- [ ] Ticket logged to #tickets channel
- [ ] Last activity timestamp updated

### 7.2. Refund Support Ticket

- [ ] User clicks "Refund Support" button
- [ ] Refund support modal appears with policy
- [ ] Modal mentions `/submitrefund` command
- [ ] User can click "Understood" or "Cancel"

### 7.3. Multiple Tickets

- [ ] User creates support ticket (ticket-username-QA)
- [ ] User creates order ticket via purchase (ticket-username-order1)
- [ ] Both tickets exist simultaneously
- [ ] Counter increments for order tickets
- [ ] Second order creates ticket-username-order2

### 7.4. Ticket Activity Tracking

- [ ] User sends message in ticket
- [ ] Last activity timestamp updated
- [ ] Activity logged to database

### 7.5. Ticket Auto-Close (Optional - Long Test)

Note: Default is 48h warning, 49h close. For testing, consider temporarily modifying the code to use shorter intervals.

- [ ] Ticket inactive for configured period (48h default)
- [ ] Warning message sent to user
- [ ] Warning logged to #tickets
- [ ] After additional period (1h default), ticket closes
- [ ] Transcript exported (chat-exporter or fallback)
- [ ] Transcript saved (S3 or local)
- [ ] Transcript DM sent to user
- [ ] Channel archived/deleted
- [ ] Ticket status updated to "closed" in database
- [ ] Close logged to #tickets

---

## 8. Refund System Tests

### 8.1. Refund Request Submission

Prerequisites:
- [ ] User has at least one fulfilled order
- [ ] Order is within refund window (3 days default)

Steps:
- [ ] User runs `/submitrefund` in order ticket
- [ ] Rate limit check passes (max 1 use per hour)
- [ ] Modal appears with:
  - [ ] Amount field
  - [ ] Reason field
  - [ ] Proof URL field (optional)
- [ ] User fills in details and submits
- [ ] Validation checks pass:
  - [ ] Order exists and belongs to user
  - [ ] Order status is fulfilled or refill
  - [ ] Within time window
  - [ ] Amount ≤ original price
- [ ] Refund request created in database
- [ ] Handling fee calculated (10% default)
- [ ] Final refund amount calculated
- [ ] Admin notified in #audit channel
- [ ] User receives confirmation with details

### 8.2. List Pending Refunds

- [ ] Admin runs `!pending-refunds`
- [ ] List shows all pending refunds
- [ ] Each refund displays:
  - [ ] Refund ID
  - [ ] User
  - [ ] Order ID
  - [ ] Requested amount
  - [ ] Handling fee
  - [ ] Final refund amount
  - [ ] Reason
  - [ ] Created date

### 8.3. Approve Refund

- [ ] Admin runs `!refund-approve @user`
- [ ] Rate limit check passes (max 10 uses per minute)
- [ ] Admin cannot bypass (admin_bypass=False)
- [ ] Refund status updated to "approved"
- [ ] User wallet credited with final refund amount
- [ ] Transaction logged in wallet_transactions
- [ ] Refund record updated with:
  - [ ] resolved_at timestamp
  - [ ] resolved_by_staff_id
- [ ] User receives DM notification
- [ ] Audit log posted to #audit
- [ ] User balance check shows credited amount

### 8.4. Reject Refund

- [ ] Admin runs `!refund-reject @user "reason for rejection"`
- [ ] Rate limit check passes (max 10 uses per minute)
- [ ] Refund status updated to "rejected"
- [ ] Rejection reason stored
- [ ] Refund record updated with timestamps and staff ID
- [ ] User receives DM with rejection reason
- [ ] Audit log posted to #audit
- [ ] No wallet credit applied

### 8.5. Refund Validation Errors

Test these scenarios to ensure proper validation:

- [ ] User tries to refund non-existent order → Error message
- [ ] User tries to refund someone else's order → Error message
- [ ] User tries to refund after time window → Error message
- [ ] User tries to refund pending/cancelled order → Error message
- [ ] User tries to refund more than original amount → Error message
- [ ] User triggers rate limit (>1 request per hour) → Cooldown message

---

## 9. Referral System Tests

### 9.1. Get Referral Code

- [ ] User A runs `/invite`
- [ ] Response shows referral code (User A's Discord ID)
- [ ] Shows current referral stats:
  - [ ] Total invites
  - [ ] Total earned
  - [ ] Cashback pending
- [ ] User A receives DM with referral code and instructions

### 9.2. Set Referral Code

- [ ] User B runs `/setref <UserA_Discord_ID>`
- [ ] Rate limit check passes (max 1 use per 24 hours)
- [ ] Validation passes:
  - [ ] User B has no existing referrer
  - [ ] Not trying to refer themselves
  - [ ] Referrer (User A) exists
- [ ] Referral link created in database
- [ ] User B receives confirmation message
- [ ] User A receives DM notification about new referral
- [ ] Both parties notified with 0.5% cashback info

### 9.3. Referral Purchase Tracking

- [ ] User B (with referrer) makes purchase for $10.00
- [ ] Purchase completes successfully
- [ ] Referral cashback calculated: $10.00 × 0.5% = $0.05
- [ ] Referral record updated:
  - [ ] referred_total_spend_cents increases by 1000
  - [ ] cashback_earned_cents increases by 5
- [ ] Cashback marked as pending (earned > paid)
- [ ] User A can check with `/invites` to see pending cashback

### 9.4. View Referral Stats

- [ ] User A (referrer) runs `/invites`
- [ ] Rate limit check passes (max 3 uses per minute)
- [ ] Response shows detailed breakdown:
  - [ ] List of all referrals
  - [ ] Each referral shows:
    - [ ] User mention
    - [ ] Total spent
    - [ ] Cashback earned
    - [ ] Cashback paid
    - [ ] Blacklist status
  - [ ] Summary totals
  - [ ] Pending cashback amount

### 9.5. Process Cashback (Batch)

- [ ] Admin runs `!sendref-cashb` (no user specified)
- [ ] Confirmation embed appears showing:
  - [ ] Total referrers with pending cashback
  - [ ] Total cashback amount
  - [ ] Confirm/Cancel buttons
- [ ] Admin clicks "Confirm"
- [ ] Bot processes all pending cashback:
  - [ ] For each referrer with pending cashback:
    - [ ] Wallet credited with pending amount
    - [ ] Transaction created (type='referral_cashback')
    - [ ] Referral records updated (cashback_paid_cents)
    - [ ] DM sent to referrer
- [ ] Summary posted to #audit channel with:
  - [ ] Batch ID (BATCH-YYYYMMDD-HHMMSS)
  - [ ] Users processed
  - [ ] Total amount
  - [ ] Any errors
- [ ] Users check balance and see cashback credited

### 9.6. Process Cashback (Individual)

- [ ] Admin runs `!sendref-cashb @user`
- [ ] Confirmation embed shows:
  - [ ] User mention
  - [ ] Pending cashback amount
  - [ ] Referral count
- [ ] Admin confirms
- [ ] Cashback processed for that user only
- [ ] Same steps as batch but for single user
- [ ] Audit log shows mode="individual"

### 9.7. Blacklist Referral User

- [ ] Admin runs `!referral-blacklist @user`
- [ ] User's referral record updated (is_blacklisted=1)
- [ ] User can still make purchases
- [ ] User's referrer does NOT earn cashback on future purchases
- [ ] Existing earned cashback remains (not removed)
- [ ] Admin receives confirmation
- [ ] Audit log posted

### 9.8. Referral Validation Errors

- [ ] User tries `/setref` with own Discord ID → Error (self-referral)
- [ ] User with existing referrer tries `/setref` again → Error (already linked)
- [ ] User tries `/setref` with invalid/non-existent user ID → Error
- [ ] User triggers rate limit (>1 per 24h on setref) → Cooldown message

---

## 10. Orders Command Tests

### 10.1. View Order History

- [ ] User with orders runs `/orders`
- [ ] Rate limit check passes (max 5 uses per minute)
- [ ] List shows all user's orders (paginated if >10)
- [ ] Each order displays:
  - [ ] Order ID
  - [ ] Product name (or "Manual Order")
  - [ ] Amount paid (formatted)
  - [ ] Discount applied
  - [ ] Order date
  - [ ] Status
  - [ ] Warranty expiration (if applicable)

### 10.2. Empty Order History

- [ ] New user with no orders runs `/orders`
- [ ] Message indicates no orders found
- [ ] No errors

---

## 11. Rate Limiting Tests

### 11.1. Balance Command Rate Limit

- [ ] User runs `/balance` command
- [ ] Works successfully (1st use)
- [ ] User runs `/balance` again immediately
- [ ] Works successfully (2nd use)
- [ ] User runs `/balance` 3rd time within 60 seconds
- [ ] Rate limit triggered
- [ ] Error message shows:
  - [ ] Time remaining until cooldown expires
  - [ ] Uses left (0/2)
  - [ ] Clear explanation
- [ ] After 60 seconds, user can use command again

### 11.2. Wallet Payment Rate Limit

- [ ] User makes wallet payment
- [ ] Works successfully (1st use)
- [ ] User makes 2nd wallet payment within 5 minutes
- [ ] Works successfully (2nd use)
- [ ] User makes 3rd wallet payment within 5 minutes
- [ ] Works successfully (3rd use)
- [ ] User tries 4th wallet payment within 5 minutes
- [ ] Rate limit triggered (max 3 per 5 minutes)
- [ ] Error message displayed

### 11.3. Submitrefund Rate Limit

- [ ] User runs `/submitrefund`
- [ ] Works successfully
- [ ] User tries `/submitrefund` again within 1 hour
- [ ] Rate limit triggered (max 1 per hour)
- [ ] Error message shows cooldown time

### 11.4. Setref Rate Limit

- [ ] User runs `/setref` command
- [ ] Works successfully (one-time action)
- [ ] User tries `/setref` again within 24 hours
- [ ] Rate limit triggered (max 1 per 24 hours)
- [ ] Error message displayed

### 11.5. Admin Bypass

- [ ] Admin user runs rate-limited command
- [ ] Command succeeds despite rate limit
- [ ] Bypass logged to #audit channel with:
  - [ ] Admin mention
  - [ ] Command name
  - [ ] Timestamp

### 11.6. Staff Command Rate Limits (No Admin Bypass)

- [ ] Admin runs `!refund-approve` 10 times within 60 seconds
- [ ] All succeed (max 10 per minute)
- [ ] Admin tries 11th time within same minute
- [ ] Rate limit triggered (admin_bypass=False for accountability)
- [ ] Error message displayed

### 11.7. Violation Tracking

- [ ] User triggers rate limit 3 times within 5 minutes on same command
- [ ] Staff alert posted to #audit channel showing:
  - [ ] User mention
  - [ ] Command name
  - [ ] Violation count
  - [ ] Timestamp
- [ ] User triggers rate limit again within 10 minutes
- [ ] No duplicate alert (10-minute cooldown between alerts)

---

## 12. Admin Commands Tests

### 12.1. Setup Store

- [ ] Admin runs `!setup_store`
- [ ] Command requires admin role
- [ ] Non-admin cannot run command
- [ ] Panel created successfully (tested in step 2.1)

### 12.2. Setup Tickets

- [ ] Admin runs `!setup_tickets`
- [ ] Command requires admin role
- [ ] Panel created successfully (tested in step 2.2)

### 12.3. Deposit Command

- [ ] Admin runs `!deposit @user 500`
- [ ] User wallet credited $5.00
- [ ] Transaction logged
- [ ] Audit log posted

### 12.4. Manual Complete

- [ ] Tested in step 5.3

### 12.5. Pending Refunds

- [ ] Tested in step 8.2

### 12.6. Refund Approve/Reject

- [ ] Tested in steps 8.3 and 8.4

### 12.7. Referral Blacklist

- [ ] Tested in step 9.7

### 12.8. Send Referral Cashback

- [ ] Tested in steps 9.5 and 9.6

---

## 13. Error Handling Tests

### 13.1. Invalid Commands

- [ ] User runs non-existent slash command
- [ ] Discord shows "Application did not respond" (expected)
- [ ] No bot crash

### 13.2. Missing Permissions

- [ ] Remove bot's "Manage Roles" permission
- [ ] Try to assign VIP role via purchase
- [ ] Error logged to #errors channel
- [ ] User receives error message
- [ ] Bot continues running

### 13.3. Database Errors

- [ ] Stop bot
- [ ] Delete or corrupt bot.db file
- [ ] Start bot
- [ ] Database recreates and migrations run
- [ ] Bot starts successfully

### 13.4. Invalid User Input

- [ ] User tries to deposit negative amount
- [ ] Validation error displayed
- [ ] User tries to deposit non-numeric value
- [ ] Validation error displayed
- [ ] User tries to submitrefund with invalid amount
- [ ] Validation error displayed

### 13.5. Discord API Errors

- [ ] Simulate Discord API slowdown (difficult to test)
- [ ] Bot should handle rate limits gracefully
- [ ] Errors logged to #errors channel

---

## 14. Logging Tests

### 14.1. Audit Channel

Verify these events are logged to #audit:

- [ ] Wallet credits (admin deposits)
- [ ] Manual order completions
- [ ] Refund approvals/rejections
- [ ] Referral cashback payouts
- [ ] VIP role assignments
- [ ] Rate limit admin bypasses
- [ ] Rate limit violations (after 3 violations)

### 14.2. Payments Channel

Verify these events are logged to #payments:

- [ ] Deposit requests
- [ ] Payment proof uploads
- [ ] Wallet payments

### 14.3. Tickets Channel

Verify these events are logged to #tickets:

- [ ] Ticket creation
- [ ] Ticket closure
- [ ] Auto-close warnings

### 14.4. Orders Channel

Verify these events are logged to #orders:

- [ ] Purchase orders
- [ ] Manual orders
- [ ] Order fulfillment status updates

### 14.5. Errors Channel

Verify these events are logged to #errors:

- [ ] Permission errors
- [ ] Database errors
- [ ] Discord API errors
- [ ] Unexpected exceptions

### 14.6. Log Files

- [ ] Check logs/bot.log exists
- [ ] Contains startup messages
- [ ] Contains operation logs
- [ ] No sensitive data (passwords, tokens)

---

## 15. Data Integrity Tests

### 15.1. Wallet Balance Accuracy

- [ ] User starts with $0.00
- [ ] Admin deposits $10.00
- [ ] Balance shows $10.00
- [ ] User purchases $3.00 item
- [ ] Balance shows $7.00
- [ ] User receives $2.00 refund
- [ ] Balance shows $9.00
- [ ] All transactions logged correctly
- [ ] No discrepancies

### 15.2. Transaction Ledger

- [ ] All wallet operations create transaction records
- [ ] Each transaction has:
  - [ ] User Discord ID
  - [ ] Amount (positive or negative)
  - [ ] Balance after transaction
  - [ ] Transaction type
  - [ ] Description
  - [ ] Related IDs (order, ticket, staff)
  - [ ] Timestamp
- [ ] Running balance calculation is accurate

### 15.3. Referral Cashback Accuracy

- [ ] Referrer starts with $0 earned, $0 paid
- [ ] Referred user purchases $20.00
- [ ] Cashback earned = $20.00 × 0.5% = $0.10
- [ ] Record shows earned_cents = 10, paid_cents = 0
- [ ] After cashback payout, paid_cents = 10
- [ ] Referrer wallet increased by $0.10
- [ ] Multiple purchases accumulate correctly

### 15.4. VIP Tier Thresholds

- [ ] User with $49.99 spent has "Client" role
- [ ] User spends $0.01 more (total $50.00)
- [ ] "Apex VIP" role assigned
- [ ] "Client" role removed
- [ ] Discount changes to 1.5%
- [ ] Future purchases use new discount

### 15.5. Foreign Key Integrity

- [ ] Try to delete user with existing orders
- [ ] Verify foreign key constraints prevent orphaned data
- [ ] Or verify cascading deletes work correctly
- [ ] Database integrity maintained

---

## 16. Performance Tests (Optional)

### 16.1. Concurrent Operations

- [ ] Multiple users browse storefront simultaneously
- [ ] No lag or errors
- [ ] All users receive correct data

### 16.2. Large Order History

- [ ] User with 50+ orders runs `/orders`
- [ ] Command responds quickly (<2 seconds)
- [ ] Pagination works correctly

### 16.3. Batch Cashback Processing

- [ ] 20+ users have pending cashback
- [ ] Admin runs `!sendref-cashb`
- [ ] All processed within reasonable time (<30 seconds)
- [ ] No errors or timeouts
- [ ] All users receive correct amounts

---

## 17. Security Tests

### 17.1. Configuration Security

- [ ] config.json is in .gitignore
- [ ] config.json not committed to Git
- [ ] No hardcoded tokens in code
- [ ] Environment variables work correctly

### 17.2. User Data Isolation

- [ ] User A cannot access User B's orders
- [ ] User A cannot access User B's wallet
- [ ] User A cannot access User B's refunds
- [ ] Proper permission checks in place

### 17.3. Admin Restrictions

- [ ] Non-admin cannot run admin commands
- [ ] Proper role checks enforced
- [ ] Error messages don't reveal sensitive info

---

## Testing Summary

### Results

- Total Test Categories: 17
- Total Test Items: 300+
- Tests Passed: ___ / ___
- Tests Failed: ___ / ___
- Critical Issues Found: ___
- Non-Critical Issues Found: ___

### Issues Log

| Issue # | Category | Severity | Description | Status |
|---------|----------|----------|-------------|--------|
| 1 | | | | |
| 2 | | | | |

### Notes

---

## Sign-Off

- [ ] All critical features tested and working
- [ ] All known issues documented
- [ ] Bot ready for production use
- [ ] Monitoring in place
- [ ] Backup strategy confirmed

**Tester:** ___________________
**Date:** ___________________
**Signature:** ___________________

---

*Use this checklist during deployment to ensure all features are working correctly before going live with users.*
