# Apex Digital Discord Bot - Comprehensive Report

## Executive Summary

**Apex Digital** is a comprehensive Discord bot designed for automated product distribution, e-commerce, customer support, and community management. The bot provides a complete storefront system with payment processing, ticket management, wallet system, VIP tiers, supplier integration, and extensive automation features.

**Technology Stack:**
- Python 3.11+ with discord.py 2.3.0+
- SQLite database with async operations (aiosqlite)
- Modular cog-based architecture
- RESTful API integration for supplier services

---

## 1. Core Functionality

### 1.1 Product Storefront System

The bot operates a multi-level product browsing system:

**Navigation Flow:**
1. **Main Categories** → User selects a product category
2. **Sub-Categories** → User selects a specific sub-category
3. **Products** → User views products with pagination (10 per page)
4. **Product Selection** → User selects a product variant
5. **Ticket Creation** → Opens support ticket for purchase

**Features:**
- **Pagination**: Products displayed in pages of 10 items
- **Filtering**: Users can filter products by quantity (e.g., "1000", "5000")
- **Stock Management**: Real-time stock tracking (In Stock, Low Stock, Out of Stock)
- **Product Customization**: Modal forms for products requiring custom details (URLs, usernames, instructions)
- **Supplier Integration**: Automatic product import from 5+ supplier APIs with markup application

**Product Information Displayed:**
- Product name/variant
- Price (with VIP discounts applied)
- Stock status
- Start time, duration, refill period
- Additional information
- Customization requirements

---

### 1.2 Payment System

**Payment Methods:**
- **Wallet System**: Internal balance for users
- **External Payment Methods**: Configurable payment methods (Crypto, PayPal, etc.)
- **Dynamic Payment Management**: Admins can add/edit/remove payment methods on-the-fly

**Payment Flow:**
1. User selects product and opens ticket
2. Payment options displayed in ticket channel
3. User can pay via:
   - Wallet (if sufficient balance)
   - External payment method (instructions provided)
4. Admin confirms payment
5. Order processed and delivered

**Features:**
- **Promo Codes**: Discount codes with usage limits and expiration
- **VIP Discounts**: Automatic discount application based on user tier
- **Referral Cashback**: Automatic cashback for referrals
- **Transaction Logging**: Complete audit trail of all transactions

---

### 1.3 Wallet System

**Functionality:**
- Users can deposit funds to their wallet
- Balance tracking with transaction history
- Wallet-to-wallet transfers (tip feature)
- Airdrop system for distributing funds to multiple users
- Automatic balance updates after purchases

**Commands:**
- `/deposit` - View deposit instructions
- `/balance` - Check current wallet balance
- `/transactions` - View transaction history
- `/tip @user amount [message]` - Tip another user
- `/airdrop amount max_claims [expires_hours] [message]` - Create airdrop
- `/claimairdrop code:XXXX` - Claim an airdrop
- `/airdropinfo code:XXXX` - View airdrop information

**Admin Commands:**
- `/addbalance @user amount` - Add funds to user wallet
- `/removebalance @user amount` - Remove funds from user wallet

---

### 1.4 Ticket System

**Ticket Types:**
- **Support Tickets**: General support and inquiries
- **Order Tickets**: Product purchase requests
- **Refund Tickets**: Refund requests

**Ticket Lifecycle:**
1. User opens ticket via button or command
2. Private channel created for user and staff
3. Payment options displayed (if order ticket)
4. Admin processes order/payment
5. Order status updates sent to user
6. Ticket auto-closes after inactivity (configurable)
7. Transcript saved on closure

**Features:**
- **Auto-Closure**: Tickets close after inactivity period
- **Inactivity Warnings**: Users notified before auto-closure
- **Transcripts**: HTML transcripts saved on closure
- **Status Tracking**: Order status updates (Pending, Processing, Completed, Cancelled, Refunded)
- **Customization Support**: Collects product-specific details before ticket creation

**Commands:**
- `/ticket` - Open a support ticket
- `/closeticket` - Close current ticket
- `/refund order_id [reason]` - Request refund

---

## 2. Server Structure

### 2.1 Categories and Channels

The bot automatically sets up a professional server structure:

#### 🛍️ PRODUCTS Category
- **🛍️-products**: Main product browsing channel with interactive panels

#### 🛟 SUPPORT Category
- **🛟-support**: Support panel with ticket creation buttons

#### 📋 INFORMATION Category
- **👋-welcome**: Welcome messages for new members
- **📜-rules-and-tos**: Server rules and terms of service
- **❓-help**: Help panel with usage instructions
- **❓-faq**: Frequently asked questions
- **⭐-reviews**: Customer reviews and testimonials
- **🌟-testimonials**: User testimonials
- **📢-announcements**: Important announcements
- **📢-status-updates**: Bot and server status updates

#### 💎 VIP LOUNGE Category
- **💎-vip-lounge**: Exclusive channel for VIP members

#### 💬 COMMUNITY Category
- **💡-suggestions**: User suggestions and feedback
- **💰-tips**: Tip other users channel
- **🎁-airdrops**: Airdrop announcements and claims

#### 🔒 STAFF AREA Category (Staff Only)
- **🎫-tickets**: Active support tickets
- **📜-transcripts**: Ticket transcripts archive
- **📦-order-logs**: Order processing and fulfillment logs

#### 📊 LOGS Category (Staff Only)
- **🔍-audit-log**: System audit logs and setup actions
- **💳-payment-log**: Payment confirmations and transactions
- **⚠️-error-log**: System errors and exceptions
- **💰-wallet-log**: Wallet transaction logs

---

### 2.2 Roles System

#### Staff Roles
- **🔴 Apex Staff**: Full administrative access, can manage all bot functions

#### Client Roles
- **🔵 Apex Client**: Basic client role, access to products and support
- **👤 Client**: Standard client role

#### VIP Tiers (Automatic Assignment Based on Lifetime Spending)
1. **⭐ Apex Insider** - Entry tier
2. **💜 Apex VIP** - $100+ spent
3. **💎 Apex Elite** - $500+ spent
4. **👑 Apex Legend** - $1,000+ spent
5. **🌟 Apex Sovereign** - $2,500+ spent
6. **✨ Apex Zenith** - $5,000+ spent

#### Donor Roles
- **💝 Apex Donor**: For users who donate
- **🎖️ Legendary Donor**: For significant donors

**Role Benefits:**
- **Automatic Assignment**: VIP roles assigned based on lifetime spending
- **Discounts**: Each tier provides increasing discount percentages
- **Exclusive Access**: VIP Lounge channel access
- **Priority Support**: Higher tiers get priority in support queue

---

## 3. Commands Reference

### 3.1 User Commands

#### Product & Storefront
- `/products` - Browse available products
- `/help` - View help information

#### Wallet & Payments
- `/deposit` - Get deposit instructions
- `/balance` - Check wallet balance
- `/transactions` - View transaction history
- `/tip @user amount [message]` - Tip another user
- `/airdrop amount max_claims [expires_hours] [message]` - Create airdrop
- `/claimairdrop code:XXXX` - Claim an airdrop
- `/airdropinfo code:XXXX` - View airdrop details

#### Support & Tickets
- `/ticket` - Open a support ticket
- `/closeticket` - Close current ticket
- `/refund order_id [reason]` - Request refund

#### Reviews
- `/review product_id rating [comment]` - Submit product review
- `/myreviews` - View your submitted reviews

#### Gifts
- `/giftproduct @user product_id` - Gift a product to a user
- `/giftwallet @user amount` - Gift wallet funds to a user
- `/sendgift @user product_id [message]` - Send gift with message
- `/claimgift gift_code` - Claim a gift
- `/mygifts` - View gifts sent/received

#### Promo Codes
- `/redeem code:XXXX` - Redeem a promo code

---

### 3.2 Admin Commands

#### Product Management
- `/addproduct` - Add new product
- `/editproduct product_id` - Edit product details
- `/removeproduct product_id` - Remove product
- `/setstock product_id quantity` - Set product stock
- `/addstock product_id quantity` - Add to product stock
- `/checkstock product_id` - Check product stock
- `/stockalert` - Get low stock alerts

#### Order Management
- `/updateorderstatus order_id status [estimated_delivery] [notify_user]` - Update order status
- `/bulkupdateorders order_ids status` - Bulk update orders

#### Payment Management
- `/addpayment name type [details]` - Add payment method
- `/editpayment payment_id [name] [type] [details]` - Edit payment method
- `/removepayment payment_id` - Remove payment method
- `/listpayments` - List all payment methods
- `/togglepayment payment_id` - Enable/disable payment method

#### Wallet Management
- `/addbalance @user amount [reason]` - Add funds to user wallet
- `/removebalance @user amount [reason]` - Remove funds from user wallet

#### Supplier Management
- `/importsupplier supplier_name` - Import products from supplier
- `/listsuppliers` - List all configured suppliers
- `/supplierbalance supplier_name` - Check supplier balance

#### Review Management
- `/pendingreviews` - View pending reviews
- `/approvereview review_id` - Approve a review
- `/rejectreview review_id [reason]` - Reject a review
- `/reviewstats` - View review statistics

#### Announcements
- `/announce target message [title]` - Send announcement
- `/announcements` - View recent announcements
- `/testannouncement` - Test announcement formatting

#### Database & Backups
- `/backup` - Create database backup
- `/listbackups` - List all backups
- `/exportdata [format]` - Export data

#### Setup
- `/setup` - Interactive server setup wizard

---

## 4. Advanced Features

### 4.1 Supplier Integration

**Supported Suppliers:**
1. **NiceSMMPanel** - SMM services
2. **JustAnotherPanel** - SMM services
3. **MagicSMM** - SMM services
4. **Plati.market** - Digital products
5. **Kinguin** - Gaming products

**Features:**
- Automatic product import from supplier APIs
- Markup application (configurable per supplier)
- Auto-categorization of products
- Supplier service ID tracking
- Admin-only supplier links for easy order fulfillment
- Balance checking for suppliers

**Privacy:**
- Supplier information hidden from users
- Admin-only access to supplier order URLs
- Direct supplier links in order management (admin view)

---

### 4.2 Promo Code System

**Features:**
- Create discount codes with percentage or fixed amount
- Set usage limits (per user, total uses)
- Expiration dates
- Stackable or non-stackable codes
- Automatic application in checkout flow
- Usage tracking and statistics

**Admin Commands:**
- `/createcode code discount_type discount_value [max_uses] [expires_at]` - Create promo code
- `/listcodes` - List all promo codes
- `/codeinfo code` - View code details
- `/deactivatecode code` - Deactivate code
- `/deletecode code` - Delete code

---

### 4.3 Review System

**Features:**
- Users can submit product reviews (1-5 stars)
- Optional review comments
- Admin approval workflow
- Review statistics and analytics
- Display reviews in dedicated channel

**Workflow:**
1. User submits review via `/review`
2. Review marked as "pending"
3. Admin reviews and approves/rejects
4. Approved reviews displayed publicly
5. Review statistics tracked

---

### 4.4 Gift System

**Features:**
- Gift products to users
- Gift wallet funds
- Generate gift codes
- Claim gifts via code
- Track gifts sent/received
- Optional gift messages

**Use Cases:**
- Rewards for referrals
- Birthday gifts
- Promotional giveaways
- Customer appreciation

---

### 4.5 Announcement System

**Features:**
- Send announcements to:
  - All users (DM)
  - Specific roles
  - Specific channels
  - All servers
- Rich embed formatting
- Statistics tracking (sent, delivered, failed)
- Test announcements before sending

---

### 4.6 Automated Messages

**Automated Message Types:**
1. **Welcome Messages**: Sent to new members
2. **Order Status Updates**: Notify users of order status changes
3. **Payment Reminders**: Remind users of pending payments
4. **New Product Announcements**: Notify users of new products
5. **Milestone Celebrations**: Celebrate user milestones
6. **Abandoned Cart Reminders**: Remind users of incomplete purchases

**Channels:**
- Welcome messages in `👋-welcome` channel
- Order updates via DM
- Announcements in `📢-announcements` channel

---

### 4.7 Referral System

**Features:**
- Automatic referral tracking
- Cashback on referrals
- Referral leaderboard
- Automatic role assignment for top referrers
- Referral statistics

**How It Works:**
1. User shares referral link
2. New user joins via referral link
3. Referrer gets cashback when referred user makes purchase
4. Referral statistics tracked
5. Leaderboard updated

---

## 5. Security & Permissions

### 5.1 Access Control

**Admin-Only Commands:**
- All management commands require admin role
- Commands hidden from non-admins in Discord UI
- `@app_commands.default_permissions(administrator=True)` on admin commands

**Rate Limiting:**
- Per-user rate limits
- Per-channel rate limits
- Per-guild rate limits
- Configurable cooldowns
- Financial command cooldowns (separate system)

**Financial Cooldowns:**
- Separate cooldown system for financial commands
- Prevents spam and abuse
- Admin bypass available
- Configurable per command

---

### 5.2 Data Protection

**Database:**
- SQLite with async operations
- Automatic backups (daily)
- Transaction logging
- Schema versioning and migrations

**Audit Logging:**
- All admin actions logged
- Financial transactions logged
- Order status changes logged
- Error logging

---

## 6. Configuration

### 6.1 Main Configuration (`config.json`)

**Key Settings:**
- Discord bot token
- Guild IDs
- Role IDs (admin, staff, client, VIP tiers)
- Channel IDs (all channels)
- Category IDs
- Payment settings
- Operating hours
- Rate limits
- Financial cooldowns

### 6.2 Payment Configuration (`config/payments.json`)

**Settings:**
- Payment methods (name, type, instructions)
- Payment templates
- Enable/disable payment methods
- Dynamic updates (no restart required)

---

## 7. Database Schema

**Main Tables:**
- `users` - User accounts and wallet balances
- `products` - Product catalog
- `orders` - Order history
- `tickets` - Support tickets
- `wallet_transactions` - Wallet transaction log
- `promo_codes` - Promo code definitions
- `promo_code_usage` - Promo code usage tracking
- `gifts` - Gift records
- `announcements` - Announcement history
- `reviews` - Product reviews
- `suppliers` - Supplier API configurations
- `setup_sessions` - Setup wizard sessions

**Features:**
- Automatic schema migrations
- Indexes for performance
- Foreign key constraints
- Transaction support

---

## 8. Technical Architecture

### 8.1 Code Structure

**Modular Design:**
- Cog-based architecture (one feature per cog)
- Shared utilities in `apex_core/`
- Configuration management
- Database abstraction layer

**Key Modules:**
- `bot.py` - Main bot entry point
- `apex_core/database.py` - Database operations
- `apex_core/config.py` - Configuration management
- `apex_core/server_blueprint.py` - Server structure definition
- `apex_core/supplier_apis.py` - Supplier API integrations
- `apex_core/rate_limiter.py` - Rate limiting system
- `apex_core/financial_cooldown_manager.py` - Financial cooldowns
- `cogs/` - Feature modules

### 8.2 Background Tasks

**Automated Tasks:**
1. **Daily Backups**: Automatic database backups at 3 AM UTC
2. **Session Cleanup**: Cleanup expired setup wizard sessions
3. **Ticket Lifecycle**: Monitor and auto-close inactive tickets
4. **Order Processing**: Automated order status updates

---

## 9. User Experience

### 9.1 Interactive Elements

**Buttons:**
- Product selection buttons
- Payment method buttons
- Ticket action buttons
- Pagination buttons
- Filter buttons

**Modals:**
- Product customization forms
- Promo code entry
- Review submission
- Gift messages

**Select Menus:**
- Category selection
- Sub-category selection
- Product variant selection
- Payment method selection

### 9.2 Error Handling

**User-Friendly Messages:**
- Standardized error messages
- Clear instructions
- Helpful suggestions
- Error logging for debugging

---

## 10. Setup & Deployment

### 10.1 Initial Setup

**Setup Wizard (`/setup`):**
1. **Panel Setup**: Deploy individual panels (products, support, help, etc.)
2. **Full Server Setup**: Complete server provisioning
   - Creates all roles
   - Creates all categories
   - Creates all channels
   - Sets up permissions
   - Deploys all panels
   - Cleans up old duplicates

**Features:**
- Interactive menu
- Progress updates
- Error handling
- Idempotent (can run multiple times safely)

### 10.2 Deployment

**Requirements:**
- Python 3.11+
- Ubuntu 22.04+ (recommended)
- Discord bot token
- Server with admin permissions

**Process:**
1. Clone repository
2. Install dependencies (`pip install -r requirements.txt`)
3. Configure `config.json`
4. Run bot (`python3 bot.py`)
5. Run `/setup` in Discord
6. Configure payment methods
7. Import products (manual or via supplier APIs)

---

## 11. Monitoring & Maintenance

### 11.1 Logging

**Log Channels:**
- Audit log (all admin actions)
- Payment log (all transactions)
- Error log (system errors)
- Wallet log (wallet transactions)

**Terminal Logging:**
- All actions logged to `bot.log`
- Real-time monitoring with `tail -f bot.log`
- Error filtering available

### 11.2 Backups

**Automatic:**
- Daily database backups
- Config backups on changes
- 30-day retention

**Manual:**
- `/backup` command
- Export data via `/exportdata`

---

## 12. Unique Features

### 12.1 What Makes This Bot Special

1. **Complete E-Commerce Solution**: Full storefront, payment, and order management
2. **Supplier Integration**: Automatic product import from multiple suppliers
3. **VIP Tier System**: Automatic role assignment based on spending
4. **Comprehensive Automation**: Tickets, orders, messages, backups
5. **Professional UI/UX**: Emojis, embeds, interactive elements
6. **Flexible Configuration**: Dynamic payment methods, configurable everything
7. **Security First**: Rate limiting, cooldowns, audit logging
8. **Scalable Architecture**: Modular design, easy to extend

---

## 13. Future Enhancements (Potential)

- Multi-language support
- Advanced analytics dashboard
- Mobile app integration
- Web dashboard for admin
- Advanced reporting
- Integration with more payment providers
- Advanced inventory management
- Multi-currency support
- Subscription products
- Affiliate program enhancements

---

## 14. Support & Documentation

**Documentation Files:**
- `README.md` - Basic setup guide
- `DEPLOYMENT.md` - Deployment instructions
- `QUICK_START_UBUNTU.md` - Quick start for Ubuntu
- Various feature-specific documentation

**Help Resources:**
- `/help` command in Discord
- Help panel in `❓-help` channel
- FAQ in `❓-faq` channel

---

## Conclusion

The Apex Digital Discord Bot is a comprehensive, production-ready e-commerce and community management solution. It provides everything needed to run a digital product store within Discord, from product browsing to payment processing to customer support. The modular architecture, extensive automation, and professional UI make it suitable for both small and large-scale operations.

**Key Strengths:**
- Complete feature set
- Professional appearance
- High automation
- Secure and reliable
- Easy to configure
- Scalable architecture

**Ideal For:**
- Digital product stores
- SMM panel resellers
- Gaming item sellers
- Service providers
- Community marketplaces

---

*Report Generated: December 2024*
*Bot Version: Latest (with all recent features)*
*Total Commands: 50+*
*Total Cogs: 20+*
*Database Tables: 15+*

