# Payment System Testing Checklist

## Prerequisites
- [ ] Bot is running
- [ ] Database is initialized
- [ ] Config files are set up correctly
- [ ] Test server with proper roles and channels

## Configuration Tests

### Payment Config Loading
- [ ] Bot loads config/payments.json on startup
- [ ] No errors in logs related to payment config
- [ ] All 6 payment methods loaded
- [ ] is_enabled flags respected

### Enable/Disable Methods
- [ ] Set a method to `is_enabled: false`
- [ ] Restart bot
- [ ] Verify method doesn't appear in payment embed
- [ ] Re-enable and verify it reappears

## Storefront Flow

### Opening Purchase Ticket
- [ ] Run `!setup_store` command
- [ ] Select main category from dropdown
- [ ] Select sub-category
- [ ] View product details
- [ ] Click "Open Ticket" button

### Payment Embed Display
- [ ] Ticket channel created successfully
- [ ] Two embeds posted: owner summary and payment options
- [ ] Owner embed shows:
  - [ ] Customer mention and avatar
  - [ ] User ID
  - [ ] Ticket ID
  - [ ] Product details (service, variant, base price, final price, discount)
  - [ ] Service info (start time, duration, refill)
  - [ ] Payment info (amount due, user balance, status)
  - [ ] Operating hours
- [ ] Payment embed shows:
  - [ ] Title with variant name
  - [ ] Product details section
  - [ ] All enabled payment methods with emoji
  - [ ] Method-specific instructions and metadata
  - [ ] Important information footer
  - [ ] User avatar thumbnail

### Payment Method Details
Verify each enabled method displays correctly:

#### Wallet
- [ ] Shows "Use Wallet Balance" with green/red status
- [ ] Displays current balance
- [ ] Displays required amount
- [ ] Status shows ✅ Sufficient or ❌ Insufficient

#### Binance Pay
- [ ] Shows Pay ID
- [ ] Displays warning about paying owner account
- [ ] Includes link to Binance Pay

#### PayPal
- [ ] Shows payout email
- [ ] Includes payment link if configured

#### Tip.cc
- [ ] Shows command with amount auto-filled
- [ ] Includes link to Tip.cc
- [ ] Shows format warning

#### Crypto
- [ ] Lists available networks
- [ ] Shows instructions for requesting address

## Interactive Buttons

### Wallet Payment Button
When user has sufficient balance:
- [ ] Button is green
- [ ] Button is enabled
- [ ] Click button
- [ ] Verify ephemeral "processing" message
- [ ] Verify payment success message
- [ ] Check new balance displayed
- [ ] Verify order ID shown
- [ ] Confirm public message in ticket: "User paid $X.XX via Wallet. Order ID: #Y"
- [ ] Verify balance deducted from user's wallet
- [ ] Verify order created in database

When user has insufficient balance:
- [ ] Button is red
- [ ] Button is disabled
- [ ] Cannot click button

### Upload Payment Proof Button
- [ ] Button visible and clickable
- [ ] Click button
- [ ] Verify ephemeral instructions message
- [ ] Contains upload instructions
- [ ] Mentions staff verification

### Request Crypto Address Button
- [ ] Button visible and clickable
- [ ] Click button
- [ ] Verify ephemeral confirmation to user
- [ ] Shows available networks
- [ ] Public message posted in channel
- [ ] Admin role mentioned
- [ ] Staff instructions visible

## Payment Proof Upload

### File Upload Detection
- [ ] User uploads image/file in order ticket
- [ ] System detects upload automatically
- [ ] Embed posted in channel with:
  - [ ] User mention
  - [ ] Ticket ID
  - [ ] Attachment count
  - [ ] Links to attachments
- [ ] Admin role mentioned
- [ ] Staff verification instructions shown

### User Notification
- [ ] User receives DM
- [ ] DM confirms proof received
- [ ] DM mentions staff verification

### Edge Cases
- [ ] Upload in non-order ticket (no notification)
- [ ] Upload by bot (ignored)
- [ ] Upload with no attachments (ignored)
- [ ] Multiple attachments (all listed)

## Discount Calculation

### VIP Tier Discounts
- [ ] User with no purchases shows 0% discount
- [ ] User with $50+ lifetime shows correct VIP tier discount
- [ ] Final price calculated correctly
- [ ] Owner embed shows correct discount percentage

### Display Verification
- [ ] Base price shown in owner embed
- [ ] Final price (after discount) shown correctly
- [ ] Discount percentage displayed
- [ ] User sees only final price in payment embed

## Admin Experience

### Order Summary Embed
- [ ] Clear customer identification
- [ ] Complete product information
- [ ] Accurate pricing details
- [ ] Payment status visible
- [ ] Operating hours reference
- [ ] Professional formatting

### Notifications
- [ ] Admin role mentioned when ticket opens
- [ ] Admin mentioned on payment proof upload
- [ ] Admin mentioned on crypto address request
- [ ] All notifications clear and actionable

## Error Handling

### Invalid Product
- [ ] Inactive product shows "no longer available"
- [ ] Missing product handled gracefully

### Insufficient Balance
- [ ] Clear error message
- [ ] Shows required vs. available balance
- [ ] User not charged

### Payment Processing Error
- [ ] Error caught and logged
- [ ] User-friendly error message
- [ ] Transaction rolled back

### Missing Configuration
- [ ] Missing payment method falls back gracefully
- [ ] Missing metadata doesn't crash
- [ ] Warnings in logs if issues detected

## Integration Tests

### Database Integration
- [ ] User created if doesn't exist
- [ ] Balance fetched correctly
- [ ] Order created successfully
- [ ] Ticket linked to channel
- [ ] Transaction recorded

### Wallet Integration
- [ ] Balance check works
- [ ] Payment deduction atomic
- [ ] New balance correct
- [ ] Transaction logged

### Discount System Integration
- [ ] VIP tier calculated correctly
- [ ] Role discounts applied
- [ ] Combined discounts work
- [ ] Discount shown in owner embed

## Edge Cases

### Multiple Tickets
- [ ] User can open multiple order tickets
- [ ] Each gets unique channel name
- [ ] Payment detection works in each

### Operating Hours
- [ ] Operating hours displayed
- [ ] No blocking during ticket creation
- [ ] Information accessible to user

### DM Failures
- [ ] If DMs disabled, ticket still works
- [ ] Warning logged but process continues
- [ ] User informed in ticket channel

### Channel Permissions
- [ ] User can see ticket channel
- [ ] Admin can see ticket channel
- [ ] Others cannot see channel
- [ ] User can upload files

## Performance

### Embed Rendering
- [ ] Payment embed loads quickly
- [ ] No lag with multiple methods
- [ ] Images (avatars) load correctly

### Button Responsiveness
- [ ] Buttons respond immediately
- [ ] No double-click issues
- [ ] Proper loading states

## Regression Tests

### Existing Functionality
- [ ] Regular product purchases still work
- [ ] Support tickets unaffected
- [ ] Wallet commands functional
- [ ] Order history accessible

### Backward Compatibility
- [ ] Old config.json payment_methods still work
- [ ] New config doesn't break existing features
- [ ] Bot starts with either config format

## Documentation

### Code Documentation
- [ ] docs/PAYMENT_SYSTEM.md exists
- [ ] Examples clear
- [ ] Configuration explained
- [ ] Integration points documented

### Implementation Notes
- [ ] PAYMENT_SYSTEM_IMPLEMENTATION.md complete
- [ ] Changes summarized
- [ ] Features listed
- [ ] Testing guide included

## Final Checks

### Code Quality
- [x] Python syntax valid (py_compile passed)
- [x] No import errors
- [x] Proper error handling
- [x] Logging in place

### Git Status
- [x] All changes staged
- [x] New files added
- [x] .gitignore updated
- [x] Ready for commit

### Deployment Ready
- [ ] No hardcoded values
- [ ] Config example provided
- [ ] Dependencies documented
- [ ] Migration path clear

## Notes

Record any issues or observations during testing:

```
[Date] [Tester] [Issue/Observation]
- 
- 
- 
```

## Sign-Off

- [ ] All critical tests passed
- [ ] Major functionality verified
- [ ] Documentation complete
- [ ] Ready for production

Tested by: _______________
Date: _______________
