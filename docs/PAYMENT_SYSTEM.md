# Payment System Documentation

## Overview

The payment system provides a comprehensive, configurable payment display for purchase tickets. It supports multiple payment methods, wallet integration, and payment proof verification.

## Configuration

Payment methods are configured in `config/payments.json`. Each method supports:

- **name**: Display name of the payment method
- **instructions**: Text instructions shown to users
- **emoji**: Optional emoji for visual identification
- **is_enabled**: Boolean flag to enable/disable the method
- **metadata**: Method-specific configuration data

### Example Payment Method

```json
{
  "name": "Binance",
  "instructions": "Send the desired USD amount via Binance Pay and include your Discord username in the note field.",
  "emoji": "🟡",
  "is_enabled": true,
  "metadata": {
    "pay_id": "123456789",
    "reference": "Use your Discord username",
    "url": "https://pay.binance.com/en",
    "warning": "⚠️ Pay the owner account, NOT the bot"
  }
}
```

## Payment Methods

### 1. Wallet (Internal)
- **Type**: `internal`
- **Features**: 
  - Instant payment processing
  - Balance check with visual indicators (green/red)
  - Automatic order creation
- **Button**: `WalletPaymentButton` - disabled if insufficient balance

### 2. Binance Pay
- **Metadata Fields**:
  - `pay_id`: Binance Pay ID
  - `url`: Link to Binance Pay
  - `warning`: Safety notice
- **Display**: Pay ID, URL, and warning message

### 3. PayPal
- **Metadata Fields**:
  - `payout_email`: PayPal email address
  - `payment_link`: Direct payment link
- **Display**: Email and clickable payment link

### 4. Tip.cc
- **Metadata Fields**:
  - `command`: Command template (use `{amount}` placeholder)
  - `url`: Link to Tip.cc
  - `warning`: Format reminder
- **Display**: Auto-filled command with amount, URL, and warning

### 5. CryptoJar
- **Metadata Fields**:
  - `command`: Command template (use `{amount}` placeholder)
  - `url`: Link to CryptoJar
  - `warning`: Instructions
- **Display**: Auto-filled command with amount, URL, and warning

### 6. Crypto (Custom Networks)
- **Type**: `custom_networks`
- **Metadata Fields**:
  - `networks`: Array of supported networks (e.g., ["Bitcoin", "Ethereum", "Solana"])
  - `note`: Additional instructions
- **Button**: `RequestCryptoAddressButton` - notifies staff to provide address
- **Workflow**:
  1. User clicks "Request Crypto Address"
  2. Staff receives notification in ticket channel
  3. Staff provides appropriate address
  4. User sends payment and uploads proof

## Payment Embed

When a user opens a purchase ticket, they see a comprehensive payment embed with:

### Header Section
- Title: "💳 Payment Options for {variant_name}"
- Product details: Service, Variant, Price, ETA
- User avatar thumbnail

### Payment Methods Section
For each enabled payment method:
- Method name with emoji
- Instructions
- Method-specific details based on metadata
- Visual status indicators (for Wallet)

### Information Section
- Confirmation timeline
- Support contact info
- Payment proof upload instructions

## Interactive Buttons

### WalletPaymentButton
- **Style**: Green (sufficient) or Red (insufficient)
- **Behavior**: 
  - Checks balance before processing
  - Creates order and deducts amount
  - Posts confirmation in ticket channel
  - Sends ephemeral success message to user
- **Disabled**: When balance is insufficient

### PaymentProofUploadButton
- **Style**: Primary (blue)
- **Behavior**: 
  - Shows ephemeral instructions
  - Prompts user to upload file in channel

### RequestCryptoAddressButton
- **Style**: Secondary (gray)
- **Behavior**:
  - Notifies staff in ticket channel
  - Lists available networks
  - Sends ephemeral confirmation to user

## Payment Proof Workflow

### User Upload
1. User uploads screenshot/file in ticket channel
2. System detects attachment via `on_message` listener
3. Validates channel name matches `ticket-*-order*` pattern

### Automatic Notifications
- **In Ticket Channel**:
  - Embed with user info and attachment links
  - Admin role mention
  - Verification instructions
- **User DM**:
  - Confirmation that proof was received
  - Staff verification timeline

### Staff Verification
Staff can verify payment using existing admin commands (e.g., `!confirm`).

## Owner Notifications

When a ticket is opened, staff receive a detailed embed with:

### Customer Information
- Username and mention
- User ID
- Display avatar thumbnail

### Product Details
- Service name
- Variant name
- Base price (before discount)
- Final price (after discount)
- Discount percentage

### Service Information
- Start time/ETA
- Duration
- Refill policy

### Payment Information
- Amount due
- User's wallet balance
- Payment status

### Additional Information
- Operating hours
- Any product-specific notes

## Integration with Database

The payment system integrates with existing database methods:

- `get_user()` - Fetch wallet balance
- `purchase_product()` - Process wallet payments
- `get_product()` - Retrieve product details
- `get_ticket_by_channel()` - Validate payment proof uploads

## Discount Calculation

Payment embed shows discounted prices based on:
1. VIP tier (calculated from lifetime spend)
2. Product-specific role discounts
3. Combined discount calculations

## Error Handling

### Insufficient Balance
- Wallet button disabled
- Clear visual indicator (red color)
- Shows required vs. available balance

### Payment Processing Errors
- Caught and logged
- User-friendly error messages
- Transaction rollback on failure

### Missing Configuration
- Graceful fallback to config.json payment_methods
- Disabled methods automatically hidden
- Validation warnings in logs

## Best Practices

1. **Enable/Disable Methods**: Use `is_enabled: false` to temporarily disable payment methods
2. **Update Instructions**: Keep metadata current with actual payment processes
3. **Test Changes**: Update config/payments.json and reload bot
4. **Monitor Logs**: Check for payment processing errors
5. **Validate Metadata**: Ensure all required fields are present for each method type

## Customization

To add a new payment method:

1. Add entry to `config/payments.json`
2. Set `is_enabled: true`
3. Provide clear instructions
4. Add relevant metadata fields
5. Optionally update `_build_payment_embed()` for custom display logic

## Security Considerations

- Payment proof stored as Discord attachment URLs (ephemeral)
- Wallet transactions use IMMEDIATE transactions for consistency
- Admin verification required before order fulfillment
- User-uploaded content should be reviewed by staff
- Payment details (Pay IDs, addresses) stored in config, not database
