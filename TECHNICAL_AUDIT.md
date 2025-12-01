# Apex Core - Technical Implementation Audit

## Part 1: Database Schema Deep Dive

### Migration History

The database uses a versioned migration system for forward compatibility:

```
v1: Base Schema (8 tables)
v2: Product Table Migration (schema modernization)
v3: Index Creation (query optimization)
v4: Ticket Extensions (type, order_id, staff assignment, priority)
v5: Wallet Transactions (ledger system)
v6: Order Extensions (warranty, renewal tracking)
v7: Transcripts (ticket archive storage)
```

### Detailed Column Specifications

#### Users Table
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id INTEGER UNIQUE NOT NULL,              -- Discord user ID
    wallet_balance_cents INTEGER DEFAULT 0,          -- Current balance in cents
    total_lifetime_spent_cents INTEGER DEFAULT 0,    -- Cumulative spending for VIP tiers
    has_client_role INTEGER DEFAULT 0,               -- Boolean: has "Client" role
    manually_assigned_roles TEXT,                    -- JSON string of manually assigned role IDs
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

**Key Features**:
- Thread-safe wallet updates via IMMEDIATE transaction
- Lifetime spend tracking for VIP tier qualification
- Supports both automatic and manual role assignment

#### Products Table (After v2 migration)
```sql
CREATE TABLE products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    main_category TEXT NOT NULL,                     -- e.g., "Services", "Consulting"
    sub_category TEXT NOT NULL,                      -- e.g., "SEO", "Web Design"
    service_name TEXT NOT NULL,                      -- e.g., "Website Optimization"
    variant_name TEXT NOT NULL,                      -- e.g., "3-Month Basic Plan"
    price_cents INTEGER NOT NULL,                    -- Pricing in cents (avoid float)
    start_time TEXT,                                 -- Optional: service start time
    duration TEXT,                                   -- Optional: e.g., "30 days", "3 months"
    refill_period TEXT,                              -- Optional: renewal period
    additional_info TEXT,                            -- Optional: JSON metadata
    role_id INTEGER,                                 -- Optional: role to assign
    content_payload TEXT,                            -- Optional: JSON delivery payload
    is_active INTEGER DEFAULT 1,                     -- Soft delete flag
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

**Important**:
- Prices stored in cents to avoid floating-point errors
- Supports digital delivery via content_payload
- Optional role assignment per product
- All text fields support category hierarchies

#### Tickets Table (After v4 migration)
```sql
CREATE TABLE tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_discord_id INTEGER NOT NULL,                -- User who opened ticket
    channel_id INTEGER UNIQUE NOT NULL,              -- Discord ticket channel ID
    status TEXT DEFAULT 'open',                      -- open, closed, pending
    type TEXT DEFAULT 'support',                     -- support, billing, sales
    order_id INTEGER,                                -- Linked order ID (if applicable)
    assigned_staff_id INTEGER,                       -- Discord ID of assigned staff
    closed_at TIMESTAMP,                             -- When was ticket closed?
    priority TEXT,                                   -- Optional: high, normal, low
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_discord_id) REFERENCES users(discord_id) ON DELETE CASCADE
)
```

**Lifecycle**:
1. User purchases product → ticket created
2. User interacts → last_activity updated
3. After 48h inactivity → warning sent
4. After 49h inactivity → auto-closed
5. On close → transcript archived

#### Orders Table (After v6 migration)
```sql
CREATE TABLE orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_discord_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    price_paid_cents INTEGER NOT NULL,               -- Actual price after discount
    discount_applied_percent REAL DEFAULT 0,         -- VIP/role discount applied
    order_metadata TEXT,                             -- JSON: custom order info
    status TEXT DEFAULT 'pending',                   -- pending, completed, refunded
    warranty_expires_at TIMESTAMP,                   -- Warranty end date (if applicable)
    last_renewed_at TIMESTAMP,                       -- Last warranty renewal date
    renewal_count INTEGER DEFAULT 0,                 -- Number of renewals
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_discord_id) REFERENCES users(discord_id),
    FOREIGN KEY(product_id) REFERENCES products(id)
)
```

**Warranty Management**:
- Warranty optional (null if no warranty)
- Renewal tracking for recurring services
- Status management for post-purchase lifecycle

#### Wallet Transactions Table (Migration v5)
```sql
CREATE TABLE wallet_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_discord_id INTEGER NOT NULL,
    amount_cents INTEGER NOT NULL,                   -- Signed: positive=credit, negative=debit
    balance_after_cents INTEGER NOT NULL,            -- Balance snapshot after transaction
    transaction_type TEXT NOT NULL,                  -- deposit, purchase, refund, staff_credit, bonus
    description TEXT,                                -- Human-readable reason
    order_id INTEGER,                                -- Links to order (if applicable)
    ticket_id INTEGER,                               -- Links to ticket (if applicable)
    staff_discord_id INTEGER,                        -- Who initiated (for staff_credit)
    metadata TEXT,                                   -- JSON: additional context
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_discord_id) REFERENCES users(discord_id),
    FOREIGN KEY(order_id) REFERENCES orders(id),
    FOREIGN KEY(ticket_id) REFERENCES tickets(id)
)
```

**Audit Trail**:
- Immutable transaction history
- Balance snapshot for reconciliation
- Indexed on (user_discord_id, created_at DESC) for efficient queries
- Supports VIP tier auditing

#### Transcripts Table (Migration v7)
```sql
CREATE TABLE transcripts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL,
    user_discord_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,                     -- Original Discord channel ID
    storage_type TEXT NOT NULL,                      -- 'local' or 's3'
    storage_path TEXT NOT NULL,                      -- File path or S3 key
    file_size_bytes INTEGER,                         -- For quota tracking
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(ticket_id) REFERENCES tickets(id)
)
```

**Storage Options**:
- Local: `storage_path` = `/transcripts/ticket-123-support.html`
- S3: `storage_path` = `transcripts/ticket-123-support.html`

---

## Part 2: Command & Interaction Analysis

### All Registered Commands by Type

#### Slash Commands (App Commands)

1. **OrdersCog**
   - `/orders` - View order history
   - `/transactions` - View wallet transactions
   - `/order-status` - Update order status (admin)
   - `/renew-warranty` - Renew warranty (admin)
   - `/warranty-expiry` - Check expiring warranties (admin)

2. **WalletCog**
   - `/deposit` - Create deposit ticket
   - `/balance` - Check wallet balance
   - `/addbalance` - Add funds (admin)

3. **ManualOrdersCog**
   - `/manual_complete` - Manually complete order (admin)
   - `/assign_role` - Manually assign role (admin)
   - `/remove_role` - Manually remove role (admin)

4. **ProductImportCog**
   - `/import_products` - Bulk import from template

5. **NotificationsCog**
   - `/test-warranty-notification` - Test notification (admin)

#### Text Commands (Prefix Commands)

1. **StorefrontCog**
   - `!setup_store` - Initialize storefront (admin)

#### Interactive Components (Buttons/Selects)

**Persistent Views** (custom_id format):
- `storefront:category_select` - Main category selector
- `storefront:category_prev_button` / `storefront:category_next_button` - Pagination
- `storefront:product_button` - Purchase initiator

**Ephemeral Views** (timeout ~120s):
- SubCategory selector
- Product details view
- Payment instructions view

---

## Part 3: Configuration & Runtime Behavior

### Configuration Loading Pipeline

```
main()
├─ Load config.json via load_config()
│  ├─ Parse token (or use env var override)
│  ├─ Parse role_ids, ticket_categories
│  ├─ Parse operating_hours
│  ├─ Parse roles (VIP tiers)
│  ├─ Parse logging_channels
│  └─ Try to load payment_settings (optional)
├─ If DISCORD_TOKEN env var exists, override token
├─ Validate payment settings if config/payments.json exists
├─ Create ApexCoreBot with config
└─ Start bot with token
```

### Runtime Initialization Sequence

```
ApexCoreBot.setup_hook()
├─ db.connect()
│  ├─ Connect to apex_core.db
│  ├─ Enable foreign keys
│  └─ _initialize_schema()
│     ├─ Create schema_migrations table
│     └─ _apply_pending_migrations()
│        ├─ Check current version
│        ├─ For each pending migration:
│        │  ├─ Execute migration function
│        │  └─ Record in schema_migrations
│        └─ Log final version
├─ storage.initialize()
│  ├─ Check TRANSCRIPT_STORAGE_TYPE
│  ├─ If 's3': initialize boto3 client
│  └─ If 'local': create transcripts/ directory
├─ _load_cogs()
│  └─ Load all .py files from cogs/ directory
└─ For each guild_id in config.guild_ids:
   ├─ Copy global commands to guild
   └─ Sync command tree
```

### VIP Tier Calculation Logic

```python
# From roles.py calculate_vip_tier()
lifetime_spend_cents = user.total_lifetime_spent_cents

# Check each role in priority order
for role in config.roles:
    if role.assignment_mode == "automatic_spend":
        if lifetime_spend_cents >= role.unlock_condition:
            highest_tier = role
    elif role.assignment_mode == "automatic_first_purchase":
        if user has made any purchase:
            assign_tier = role
```

**Auto-Promotion Flow**:
1. User makes purchase → total_lifetime_spent updated
2. Post-purchase check → calculate_vip_tier()
3. If new tier > current tier → handle_vip_promotion()
4. Grant new role, remove old role

---

## Part 4: Payment & Order Processing

### Payment Method Configuration

Required fields in `config/payments.json`:
```json
{
  "payment_methods": [
    {
      "name": "Binance Pay",
      "instructions": "Send payment to wallet address: ...",
      "emoji": "💰",
      "metadata": {
        "url": "https://binance.com/pay",
        "address": "wallet_address",
        "network": "BSC"
      }
    }
  ],
  "order_confirmation_template": "Your order #{order_id} for {service_name} ({variant_name}) is confirmed. Price: {price}. ETA: {eta}",
  "refund_policy": "Full refund within 30 days..."
}
```

### Order Confirmation Template Validation

```python
# From config.py _validate_order_confirmation_template()
required_placeholders = {
    "{order_id}",           # Order ID number
    "{service_name}",       # Product service name
    "{variant_name}",       # Product variant
    "{price}",              # Formatted price
    "{eta}"                 # Estimated time to completion
}

# All must be present in order_confirmation_template
```

### Purchase Processing Pipeline

```
User clicks "Purchase" button
├─ Check if product is active
├─ Resolve user from Discord member
├─ Create ticket in appropriate category
├─ Calculate applicable discount
│  ├─ Check VIP tier discount
│  ├─ Check role-based discount
│  └─ Apply highest discount
├─ Create order record
├─ Create wallet transaction (debit)
├─ Update user balance
├─ Update total_lifetime_spent
├─ Check for VIP promotion
├─ Send order confirmation
├─ Log payment to logging_channels.payments
└─ Emit post-purchase event
```

---

## Part 5: Ticket Lifecycle

### Ticket Creation (from purchase)

```
Product purchase initiated
├─ Create ticket in category matching ticket type
├─ Set ticket.type based on product type
├─ Link ticket.order_id to created order
├─ Send order confirmation message
├─ Set auto-close timeout (49 hours)
└─ Log to logging_channels.tickets
```

### Automatic Ticket Closure

```
Every 10 minutes: ticket_lifecycle_task runs
├─ Get all open tickets
├─ For each ticket:
│  ├─ Calculate inactivity duration
│  ├─ If > 48h: send warning if not already warned
│  ├─ If > 49h: 
│  │  ├─ Generate transcript (if chat_exporter available)
│  │  ├─ Archive transcript to transcripts table
│  │  ├─ Store to local or S3 per config
│  │  ├─ Close ticket
│  │  └─ Archive channel
│  └─ Log action
└─ Update warned_tickets set
```

### Transcript Generation & Storage

```
Ticket closure triggered
├─ If chat_exporter available:
│  ├─ Export channel messages to HTML
│  ├─ Generate filename: ticket-{id}-{name}.html
│  ├─ Send to storage.save_transcript()
│  ├─ Local: save to transcripts/ directory
│  │  └─ Return file path
│  ├─ S3: upload to s3://bucket/transcripts/
│  │  └─ Return S3 key
│  └─ Record in transcripts table with:
│     ├─ ticket_id reference
│     ├─ user_discord_id
│     ├─ channel_id
│     ├─ storage_type ('local' or 's3')
│     ├─ storage_path
│     └─ file_size_bytes
└─ Log archived location
```

---

## Part 6: Role Management System

### Role Assignment Modes

1. **automatic_first_purchase**
   - Trigger: User completes first purchase
   - Action: Grant role automatically
   - Example: "Client" role

2. **automatic_spend**
   - Trigger: User's lifetime_spent ≥ unlock_condition cents
   - Action: Grant role automatically on VIP check
   - Example: "Apex VIP" at $50 (5000 cents)

3. **manual**
   - Trigger: Admin runs `/assign_role`
   - Action: Grant role explicitly
   - Example: "Apex Donor" for contributions

4. **automatic_all_ranks**
   - Trigger: User has all other roles
   - Action: Grant super-tier role
   - Example: "Apex Zenith" (7.5% discount)

### Role Benefits Tracking

```json
{
  "name": "Apex VIP",
  "benefits": [
    "Priority access to new products",
    "Early bird discounts",
    "VIP support channel access"
  ]
}
```

**Note**: Benefits are configuration flags. Implementation depends on specific use case.

### Discord Role Sync

Roles defined in `config.json` match Discord role IDs:
```
role_ids: {
  "admin": 123456789,        // Admin commands check
}

roles: [
  {
    "name": "Client",
    "role_id": 111111111,    // Discord role ID to assign
    ...
  }
]
```

**Assignment**:
```python
# From roles.py
member = interaction.user
role = discord.utils.get(guild.roles, id=role_id)
await member.add_roles(role)
```

---

## Part 7: Wallet & Balance Management

### Thread-Safe Balance Updates

```python
# From database.py update_wallet_balance()
async with self._wallet_lock:
    await self._connection.execute("BEGIN IMMEDIATE;")
    
    # Ensure user exists
    INSERT INTO users (discord_id, wallet_balance_cents)
    VALUES (?, 0)
    ON CONFLICT DO NOTHING
    
    # Update balance atomically
    UPDATE users
    SET wallet_balance_cents = wallet_balance_cents + delta,
        total_lifetime_spent_cents = CASE WHEN delta > 0 ...
    WHERE discord_id = ?
    
    await self._connection.commit()
    # Return new balance
```

### Transaction Types

```
deposit          - User funded wallet via payment
purchase         - User spent wallet on order (negative)
refund           - Refund to user (positive)
staff_credit     - Admin credited wallet
bonus            - Promotional bonus
withdrawal       - User withdrew from wallet (negative)
```

### Balance Reconciliation Query

```sql
SELECT 
    SUM(amount_cents) as total_change,
    MAX(balance_after_cents) as final_balance
FROM wallet_transactions
WHERE user_discord_id = ?
GROUP BY user_discord_id
```

---

## Part 8: Error Handling & Logging

### Logging Channels

Configured in `logging_channels`:

1. **audit**: Administrative actions, role changes, config updates
2. **payments**: All financial transactions, deposits, purchases
3. **tickets**: Ticket creation, closure, assignment events
4. **errors**: Application errors, exceptions, failed operations
5. **order_logs** (optional): Order status changes, warranty events
6. **transcript_archive** (optional): Archived ticket transcripts

### Error Recovery Patterns

```python
# Pattern 1: Graceful Optional Dependency
try:
    import chat_exporter
    CHAT_EXPORTER_AVAILABLE = True
except ImportError:
    CHAT_EXPORTER_AVAILABLE = False

# Usage:
if CHAT_EXPORTER_AVAILABLE:
    transcript = await chat_exporter.export(...)
else:
    logger.warning("chat_exporter not available, skipping transcript")
```

```python
# Pattern 2: Fallback Configuration
try:
    payment_settings = load_payment_settings()
except FileNotFoundError:
    logger.info("Using legacy inline payment methods")
    payment_settings = None
```

```python
# Pattern 3: Database Transaction Rollback
try:
    await self._connection.execute("BEGIN IMMEDIATE;")
    # ... operations ...
    await self._connection.commit()
except Exception as e:
    logger.error(f"Transaction failed: {e}")
    await self._connection.rollback()
    raise
```

---

## Part 9: Performance Considerations

### Database Indexes

Optimized for common query patterns:

| Index | Purpose | Query Pattern |
|-------|---------|---------------|
| `idx_discounts_expires_at` | Retrieve active discounts | WHERE expires_at > NOW() |
| `idx_tickets_user_status` | Get user's open tickets | WHERE user_discord_id = ? AND status = ? |
| `idx_orders_user` | Get user's order history | WHERE user_discord_id = ? |
| `idx_orders_status` | Find orders by status | WHERE status = ? |
| `idx_orders_warranty_expiry` | Find expiring warranties | WHERE warranty_expires_at BETWEEN ? AND ? |
| `idx_wallet_transactions_user` | Get recent transactions | WHERE user_discord_id = ? ORDER BY created_at DESC |
| `idx_wallet_transactions_type` | Analyze transaction types | WHERE transaction_type = ? |
| `idx_transcripts_ticket` | Find transcript by ticket | WHERE ticket_id = ? |
| `idx_transcripts_user` | Get user's transcripts | WHERE user_discord_id = ? |

### Query Optimization Tips

1. **Prefer indexed columns** in WHERE clauses
2. **Use LIMIT** for pagination
3. **Order by indexed column** for sorting
4. **Avoid FULL TABLE SCAN** without indexes

---

## Part 10: Security Considerations

### Access Control

```python
# Admin check pattern
def _is_admin(self, member: discord.Member | None) -> bool:
    if member is None:
        return False
    admin_role_id = self.bot.config.role_ids.admin
    return any(role.id == admin_role_id for role in member.roles)

# Usage in commands
@app_commands.command()
async def admin_command(self, interaction: discord.Interaction):
    member = self._resolve_member(interaction)
    if not self._is_admin(member):
        await interaction.response.send_message("Unauthorized", ephemeral=True)
        return
    # ... admin logic ...
```

### Data Validation

```python
# Order confirmation template validation
if "{order_id}" not in template:
    raise ValueError("Template missing required {order_id} placeholder")

# Price validation
if price_cents < 0:
    raise ValueError("Price must be positive")

# Discord ID validation
if not (0 < discord_id < 2**63 - 1):
    raise ValueError("Invalid Discord ID")
```

### Secrets Management

```bash
# Never commit to config.json:
DISCORD_TOKEN=secret_token  # Use environment variable
S3_ACCESS_KEY=access_key    # Use environment variables
S3_SECRET_KEY=secret_key    # Use environment variables

# Never commit __pycache__ or .venv
# .gitignore handles this
```

---

## Part 11: Testing Coverage

### Test Modules

| Module | Tests | Coverage |
|--------|-------|----------|
| test_database.py | 30+ | Schema, migrations, CRUD |
| test_payments_config.py | 20+ | Config validation, parsing |
| test_products_template.py | 15+ | Template processing |
| test_wallet_transactions.py | 25+ | Transaction ledger, balance |
| test_ticket_management.py | 10+ | Ticket lifecycle |

### Example Test Pattern

```python
@pytest.mark.asyncio
async def test_wallet_update():
    db = Database(":memory:")
    await db.connect()
    
    # Create user
    await db.ensure_user(123456789)
    
    # Update balance
    new_balance = await db.update_wallet_balance(123456789, 5000)
    assert new_balance == 5000
    
    # Verify transaction recorded
    transactions = await db.get_wallet_transactions(123456789)
    assert len(transactions) == 1
    assert transactions[0]['amount_cents'] == 5000
```

---

## Part 12: Deployment Architecture

### File Structure for Deployment

```
/opt/apex-core/
├── bot.py
├── config.json              # Filled with real values
├── config/
│   └── payments.json        # Filled with real values
├── apex_core/
├── cogs/
├── apex_core.db             # Auto-created on first run
├── transcripts/             # Auto-created for local storage
├── .venv/                   # Python virtual environment
└── systemd service file at /etc/systemd/system/apex-core.service
```

### systemd Service File

```ini
[Unit]
Description=Apex Core Discord Bot
After=network.target

[Service]
Type=simple
User=apex
WorkingDirectory=/opt/apex-core
ExecStart=/opt/apex-core/.venv/bin/python bot.py
Restart=on-failure
RestartSec=10

Environment="CONFIG_PATH=/opt/apex-core/config.json"
Environment="DISCORD_TOKEN=xxxx"
Environment="TRANSCRIPT_STORAGE_TYPE=local"

[Install]
WantedBy=multi-user.target
```

### Docker Deployment (if applicable)

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN mkdir -p /app/transcripts

ENV CONFIG_PATH=/config/config.json
ENV TRANSCRIPT_LOCAL_PATH=/app/transcripts

CMD ["python", "bot.py"]
```

---

## Part 13: Compliance & Audit

### Data Retention

- **Transaction ledger**: Permanent (audit trail)
- **Transcripts**: Per policy (archive or delete)
- **Tickets**: Archive after closure
- **Orders**: Permanent (purchase history)
- **Users**: Permanent (until deletion request)

### GDPR Considerations

- User deletion requires cascade deletes
- Data portability: export transaction history
- Right to be forgotten: clear from wallet_transactions

### Audit Requirements

All financial transactions logged to:
- `wallet_transactions` table (immutable)
- `logging_channels.payments` (Discord)
- `logging_channels.audit` (Discord)

---

## SUMMARY

**Apex Core** is architected as a **microservices-capable bot** with:

✅ Proper separation of concerns (cogs)  
✅ Database versioning for schema evolution  
✅ Thread-safe concurrency with locks  
✅ Comprehensive logging and audit trails  
✅ Optional S3 cloud storage  
✅ Security via role-based access control  
✅ Extensive test coverage  
✅ Production-ready error handling  

---

**End of Technical Audit**
