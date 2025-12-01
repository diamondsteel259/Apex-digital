# Refund Management & Approval Workflow

## Overview

This document describes the complete refund management and approval workflow implementation for the Apex Core Discord bot.

## Features Implemented

### 1. Database Schema (Migration v9)

**New `refunds` table:**
```sql
CREATE TABLE refunds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    user_discord_id INTEGER NOT NULL,
    requested_amount_cents INTEGER NOT NULL,
    handling_fee_cents INTEGER NOT NULL,
    final_refund_cents INTEGER NOT NULL,
    reason TEXT NOT NULL,
    proof_attachment_url TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    resolved_by_staff_id INTEGER,
    rejection_reason TEXT,
    FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE,
    FOREIGN KEY(user_discord_id) REFERENCES users(discord_id) ON DELETE CASCADE,
    FOREIGN KEY(resolved_by_staff_id) REFERENCES users(discord_id) ON DELETE SET NULL
);
```

**Indexes:**
- `idx_refunds_order` - For order lookups
- `idx_refunds_user` - For user refund history
- `idx_refunds_status` - For pending refund queries

### 2. Configuration Support

**New `RefundSettings` dataclass in config:**
```python
@dataclass(frozen=True)
class RefundSettings:
    enabled: bool
    max_days: int
    handling_fee_percent: float
```

**Config example:**
```json
{
  "refund_settings": {
    "enabled": true,
    "max_days": 3,
    "handling_fee_percent": 10.0
  }
}
```

### 3. User Commands

#### `/submitrefund` Slash Command
- **Parameters:**
  - `order_id`: The order ID to refund
  - `amount`: Requested refund amount in USD
  - `reason`: Detailed reason for refund request

- **Validation:**
  - Order must belong to user
  - Order must be in 'fulfilled' or 'refill' status
  - Order must be within configured refund window (default 3 days)
  - Amount must be valid USD format

- **Process:**
  1. Validates order eligibility
  2. Creates refund request with 10% handling fee
  3. Sends confirmation DM with reference number
  4. Notifies staff in tickets channel
  5. Logs to audit trail

### 4. Staff Commands

#### `!refund-approve` Command
- **Usage:** `!refund-approve @user order_id amount [reason]`
- **Permissions:** Administrator only
- **Process:**
  1. Finds pending refund for user/order
  2. Calculates handling fee (10%)
  3. Credits user wallet with final amount
  4. Updates refund status to 'approved'
  5. Logs transaction to wallet_transactions
  6. Sends confirmation DM to user
  7. Posts to audit channel

#### `!refund-reject` Command
- **Usage:** `!refund-reject @user order_id reason`
- **Permissions:** Administrator only
- **Process:**
  1. Finds pending refund for user/order
  2. Updates refund status to 'rejected'
  3. Records rejection reason
  4. Sends rejection DM to user
  5. Posts to audit channel

#### `!pending-refunds` Command
- **Usage:** `!pending-refunds`
- **Permissions:** Administrator only
- **Process:**
  1. Shows all pending refund requests
  2. Displays user, order, amount, and reason
  3. Limits to 10 results to avoid embed size limits

### 5. Database Methods

#### Refund Management Methods
```python
# Create refund request
await db.create_refund_request(
    order_id, user_discord_id, amount_cents, reason, 
    proof_attachment_url=None, handling_fee_percent=10.0
)

# Approve refund (credits wallet)
await db.approve_refund(
    refund_id, staff_discord_id, 
    approved_amount_cents=None, handling_fee_percent=10.0
)

# Reject refund
await db.reject_refund(refund_id, staff_discord_id, rejection_reason)

# Get user refunds
await db.get_user_refunds(user_discord_id, status=None)

# Get specific refund
await db.get_refund_by_id(refund_id)

# Get all pending refunds
await db.get_pending_refunds()

# Validate order for refund
await db.validate_order_for_refund(order_id, user_discord_id, max_days=3)
```

### 6. Integration with Ticket System

#### Enhanced Refund Support Modal
- Shows refund policy with configurable days and fee percentage
- Displays clear next steps for users
- Integrates with `/submitrefund` command workflow

#### Refund Policy Display
```
🛡️ Refund Policy
Refunds accepted within 3 days of order completion | 10% handling fee applied | Information verification required

Order ID: #12345
Ticket ID: #67890
Priority: High

Refund Reason: User provided reason

Next Steps:
1. Use /submitrefund to submit your formal refund request
2. Staff will review and approve/reject within 24 hours
3. Approved refunds will be credited to your wallet minus handling fee
```

### 7. Audit Trail

#### Wallet Transaction Logging
- Every approved refund logs to `wallet_transactions` table
- Transaction type: 'refund'
- Includes order_id, refund_id, handling_fee_cents, staff_id
- Complete audit trail for financial tracking

#### Audit Channel Posts
- All refund approvals and rejections posted to audit channel
- Includes complete details: user, order, amounts, staff, reasons
- Timestamped for chronological tracking

## Workflow Summary

### User Flow
1. User clicks "Refund Support" button
2. Refund policy modal displays with configurable terms
3. User opens refund ticket with order ID and reason
4. User runs `/submitrefund` with order details
5. System validates order eligibility
6. Refund request created with calculated handling fee
7. User receives DM confirmation with reference number
8. Staff notified in tickets channel

### Staff Flow
1. Staff sees new refund notifications
2. Staff runs `!pending-refunds` to see all requests
3. Staff reviews order and request details
4. Staff runs `!refund-approve` or `!refund-reject`
5. System processes refund (credits wallet) or rejection
6. User receives DM with outcome
7. Audit trail updated

## Configuration Options

### Refund Settings
- `enabled`: Enable/disable refund system (default: true)
- `max_days`: Maximum days after order for refunds (default: 3)
- `handling_fee_percent`: Handling fee percentage (default: 10.0)

### Required Channels
- `audit`: For logging refund decisions
- `tickets`: For refund notifications

### Required Roles
- `admin`: For staff refund commands

## Security & Validation

### Input Validation
- Order ID ownership verification
- Order status validation (fulfilled/refill only)
- Refund window enforcement
- Amount format validation
- User permission checks

### Transaction Safety
- Database transactions with rollback on errors
- Atomic wallet balance updates with asyncio.Lock
- Foreign key constraints for data integrity
- Comprehensive error handling and logging

### Audit Compliance
- Complete transaction logging
- Staff action tracking
- User notification records
- Configurable audit channel posting

## Error Handling

### User-Facing Errors
- Clear error messages for invalid inputs
- Graceful handling of missing orders
- Informative messages for eligibility issues

### System Errors
- Comprehensive logging for debugging
- Transaction rollback on failures
- Staff notification for critical errors

## Testing Checklist

### Database Migration
- [x] Migration v9 creates refunds table
- [x] Indexes created properly
- [x] Foreign key constraints enforced

### Configuration
- [x] RefundSettings dataclass defined
- [x] Config parsing works correctly
- [x] Default fallbacks implemented

### Commands
- [x] `/submitrefund` slash command implemented
- [x] `!refund-approve` command implemented
- [x] `!refund-reject` command implemented
- [x] `!pending-refunds` command implemented

### Integration
- [x] Ticket system integration updated
- [x] Refund policy display enhanced
- [x] Staff notification system working

### Audit Trail
- [x] Wallet transaction logging
- [x] Audit channel posting
- [x] User DM confirmations

## File Structure

```
apex_core/
├── database.py          # Refund table migration (v9) + refund methods
├── config.py           # RefundSettings dataclass + parsing
cogs/
├── refund_management.py # Complete refund management cog
├── ticket_management.py # Enhanced refund ticket modal
config/
└── example.json        # Refund settings example
```

## Future Enhancements

### Potential Improvements
1. Refund request attachments/screenshot support
2. Bulk refund processing for multiple orders
3. Refund analytics and reporting
4. Automated refund eligibility checks
5. Refund request status tracking UI
6. Integration with payment processors for direct refunds

### Scalability Considerations
1. Pagination for large refund lists
2. Caching for frequently accessed refund data
3. Background processing for refund notifications
4. Rate limiting for refund submissions

This implementation provides a complete, production-ready refund management system with comprehensive audit trails, user-friendly interfaces, and robust security measures.