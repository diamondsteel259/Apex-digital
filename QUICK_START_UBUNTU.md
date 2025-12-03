# Quick Start Guide - Ubuntu Deployment

This guide provides step-by-step instructions for deploying the Apex Digital bot on Ubuntu.

## Prerequisites Checklist

- [ ] Ubuntu 22.04 LTS or 24.04 LTS
- [ ] Python 3.9+ installed
- [ ] Discord bot created on Developer Portal
- [ ] Discord server with admin access
- [ ] Git installed

---

## 1. Clone Repository

```bash
git clone <repository-url>
cd apex-core
```

---

## 2. Create Virtual Environment

```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Verify activation (should show .venv path)
which python
```

---

## 3. Install Dependencies

### Core Dependencies (Required)

```bash
pip install -r requirements.txt
```

**Installs:**
- discord.py (2.3.0+)
- aiosqlite (0.19.0+)
- pytest, pytest-asyncio, pytest-cov

### Optional Dependencies (Recommended)

```bash
pip install -r requirements-optional.txt
```

**Installs:**
- chat-exporter (2.8.0+) - Enhanced transcript formatting
- boto3 (1.26.0+) - S3 cloud storage support

**Without optional deps:**
- Transcripts use basic HTML format (still functional)
- Storage uses local filesystem instead of S3

---

## 4. Configure Bot

### Create Configuration File

```bash
cp config.example.json config.json
nano config.json  # or use your preferred editor
```

### Required Configuration Changes

#### 4.1. Discord Bot Token

```json
"token": "YOUR_DISCORD_BOT_TOKEN_HERE"
```

Get your token from: https://discord.com/developers/applications

#### 4.2. Guild ID

```json
"guild_ids": [
    123456789012345678  // Replace with your Discord server ID
]
```

**How to get Guild ID:**
1. Enable Developer Mode in Discord (Settings → Advanced → Developer Mode)
2. Right-click your server icon → Copy ID

#### 4.3. Admin Role

```json
"role_ids": {
    "admin": 123456789012345678  // Replace with your Admin role ID
}
```

**How to get Role ID:**
1. Right-click the role in Server Settings → Roles → Copy ID

#### 4.4. VIP Tier Roles

Update all 9 role IDs in the `roles` array:

```json
"roles": [
    {
        "name": "Client",
        "role_id": 111111111111111111,  // Update this
        ...
    },
    {
        "name": "Apex VIP",
        "role_id": 222222222222222222,  // Update this
        ...
    },
    // ... update all 9 roles
]
```

#### 4.5. Ticket Categories

```json
"ticket_categories": {
    "support": 111111111111111111,  // Update with Support category ID
    "billing": 222222222222222222,  // Update with Billing category ID
    "sales": 333333333333333333     // Update with Sales category ID
}
```

**How to create categories:**
1. In Discord: Server Settings → Channels
2. Create 3 new categories: "Support Tickets", "Billing Tickets", "Sales Tickets"
3. Right-click each → Copy ID

#### 4.6. Logging Channels

```json
"logging_channels": {
    "audit": 444444444444444444,           // Replace with #audit channel ID
    "payments": 555555555555555555,         // Replace with #payments channel ID
    "tickets": 666666666666666666,          // Replace with #tickets channel ID
    "errors": 777777777777777777,           // Replace with #errors channel ID
    "order_logs": 888888888888888888,       // Replace with #orders channel ID
    "transcript_archive": 999999999999999999 // Replace with #transcripts channel ID
}
```

**Create these channels in Discord:**
- #audit - Financial operations log
- #payments - Payment confirmations
- #tickets - Ticket activity
- #errors - Error messages
- #orders - Order processing
- #transcripts - Archived transcripts

---

## 5. Discord Server Setup

### 5.1. Create Required Roles

Create these roles in your Discord server:

| Role Name | Purpose | Discount |
|-----------|---------|----------|
| Admin | Bot administrators | N/A |
| Client | First purchase | 0% |
| Apex VIP | $50+ spent | 1.5% |
| Apex Elite | $100+ spent | 2.5% |
| Apex Legend | $500+ spent | 3.75% |
| Apex Sovereign | $1000+ spent | 5% |
| Apex Donor | Manual assignment | 0.25% |
| Legendary Donor | Manual assignment | 1.5% |
| Apex Insider | Manual assignment | 0.5% |
| Apex Zenith | All other ranks | 7.5% |

### 5.2. Create Required Channels

Create these text channels:
- #orders
- #payments
- #audit
- #tickets
- #errors
- #transcripts

### 5.3. Create Ticket Categories

Create these categories:
- Support Tickets
- Billing Tickets
- Sales Tickets

### 5.4. Set Bot Permissions

Invite bot with Administrator permission (recommended):

```
https://discord.com/api/oauth2/authorize?client_id=YOUR_BOT_CLIENT_ID&permissions=8&scope=bot%20applications.commands
```

**OR** grant these specific permissions:
- Manage Roles
- Manage Channels
- Send Messages
- Embed Links
- Attach Files
- Read Message History
- Add Reactions
- Use Slash Commands
- Manage Messages

---

## 6. Run the Bot

### Start Bot

```bash
# Ensure virtual environment is active
source .venv/bin/activate

# Run bot
python bot.py
```

### Expected Output

```
[2025-12-03 12:00:00] INFO: Bot starting...
[2025-12-03 12:00:01] INFO: Database connection established
[2025-12-03 12:00:01] INFO: Database schema migration complete. Final version: 11
[2025-12-03 12:00:02] INFO: Loading cogs...
[2025-12-03 12:00:02] INFO: Loaded cog: StorefrontCog
[2025-12-03 12:00:02] INFO: Loaded cog: WalletCog
[2025-12-03 12:00:02] INFO: Loaded cog: OrdersCog
... (more cogs)
[2025-12-03 12:00:03] INFO: Bot is ready!
[2025-12-03 12:00:03] INFO: Logged in as YourBot#1234
```

---

## 7. Initial Setup Commands

Once bot is online, run these commands in Discord:

### 7.1. Create Storefront Panel

```
!setup_store
```

This creates a persistent message with product browsing buttons.

### 7.2. Create Ticket Panel

```
!setup_tickets
```

This creates a persistent message with ticket creation buttons:
- General Support
- Refund Support

---

## 8. Add Products

### Option 1: Use Excel Template

1. Open `templates/products_template.xlsx`
2. Add your products
3. Export as CSV
4. In Discord: `/import_products` and attach CSV file

### Option 2: Manual Database Entry

```bash
python -c "
import asyncio
from apex_core.database import Database

async def add_product():
    db = Database('bot.db')
    await db.connect()
    
    product_id = await db.create_product(
        main_category='Instagram',
        sub_category='Followers',
        service_name='Instagram Followers',
        variant_name='1000 Followers',
        price_cents=999,  # $9.99
        start_time='0-5min',
        duration='Instant',
        refill_period='30 days',
        additional_info='High quality, non-drop',
        is_active=True
    )
    
    print(f'Created product ID: {product_id}')
    await db.close()

asyncio.run(add_product())
"
```

---

## 9. Test the Bot

### 9.1. Test Commands

```
/balance          # Check wallet balance
/profile          # View profile
/shop             # Browse products (use button instead)
```

### 9.2. Test Wallet

1. User runs: `/balance`
2. Admin runs: `!deposit @user 1000` (gives $10.00)
3. User confirms: `/balance` (should show $10.00)

### 9.3. Test Purchase

1. User clicks storefront panel
2. Selects category → sub-category → product
3. Clicks "Pay with Wallet"
4. Verify:
   - Balance deducted
   - Order logged in #orders
   - VIP role assigned if threshold met
   - Referral cashback tracked (if applicable)

### 9.4. Test Tickets

1. User clicks ticket panel → General Support
2. Verify channel created: `ticket-username-QA`
3. Test auto-close (optional, wait 48h or modify code for testing)

### 9.5. Test Refunds

1. User runs: `/submitrefund` in order ticket
2. Staff runs: `!refund-approve @user`
3. Verify wallet credited with refund minus handling fee

### 9.6. Test Referrals

1. User A runs: `/invite` (gets referral code)
2. User B runs: `/setref <UserA_Discord_ID>`
3. User B makes purchase
4. Verify User A gets 0.5% cashback
5. Admin runs: `!sendref-cashb` to process cashback

---

## 10. Production Deployment

### 10.1. Run as Background Service

Using systemd (recommended):

```bash
# Edit service file with your paths
sudo nano /etc/systemd/system/apex-core.service

# Enable service
sudo systemctl enable apex-core

# Start service
sudo systemctl start apex-core

# Check status
sudo systemctl status apex-core

# View logs
sudo journalctl -u apex-core -f
```

### 10.2. Environment Variables (Optional)

Create `.env` file for sensitive config:

```bash
# .env
DISCORD_TOKEN=your_bot_token_here
CONFIG_PATH=/path/to/config.json
TRANSCRIPT_STORAGE_TYPE=s3
S3_BUCKET=your-bucket-name
S3_REGION=us-east-1
S3_ACCESS_KEY=your-access-key
S3_SECRET_KEY=your-secret-key
```

Load in bot:

```bash
# Install python-dotenv
pip install python-dotenv

# Load in bot.py
from dotenv import load_dotenv
load_dotenv()
```

### 10.3. Database Backups

Set up daily backups:

```bash
# Add to crontab
crontab -e

# Add this line for daily backup at 3 AM
0 3 * * * cp /path/to/bot.db /path/to/backups/bot_$(date +\%Y\%m\%d).db
```

### 10.4. Log Rotation

```bash
sudo nano /etc/logrotate.d/apex-bot

# Add this configuration:
/path/to/apex-core/logs/*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    create 0644 your_user your_user
}
```

---

## 11. Monitoring & Maintenance

### Check Bot Status

```bash
# If using systemd
sudo systemctl status apex-core

# View logs
tail -f logs/bot.log

# Check error logs
tail -f logs/error.log
```

### Common Issues

#### Bot Not Responding
- Check bot is online in Discord
- Verify token is correct
- Check slash commands synced (can take 1 hour)

#### Database Errors
- Check file permissions
- Verify disk space available
- Check foreign_keys pragma enabled

#### Permission Errors
- Verify bot has Administrator or required permissions
- Check role hierarchy (bot role must be above managed roles)

#### Rate Limiting Errors
- Check rate_limits in config.json
- Review audit channel for bypass logs
- Adjust cooldowns if needed

---

## 12. Updating the Bot

```bash
# Pull latest changes
git pull

# Activate virtual environment
source .venv/bin/activate

# Update dependencies
pip install -r requirements.txt --upgrade
pip install -r requirements-optional.txt --upgrade

# Run database migrations (automatic on start)
python bot.py

# If using systemd
sudo systemctl restart apex-core
```

---

## 13. Security Best Practices

- ✅ Never commit config.json to version control
- ✅ Use environment variables for sensitive data
- ✅ Regularly update Python packages
- ✅ Monitor audit channel for suspicious activity
- ✅ Backup database daily
- ✅ Use strong Discord bot token (regenerate if exposed)
- ✅ Limit admin role access
- ✅ Review rate limits for your use case
- ✅ Enable 2FA on Discord account

---

## 14. Support & Resources

### Documentation

- `README.md` - Comprehensive feature documentation
- `RATE_LIMITING.md` - Rate limiting system guide
- `SETUP_ERROR_RECOVERY.md` - Error recovery and rollback
- `UBUNTU_E2E_TEST_REPORT.md` - Full test execution report

### Discord Developer Resources

- Developer Portal: https://discord.com/developers/applications
- discord.py Documentation: https://discordpy.readthedocs.io/
- Discord API Server: https://discord.gg/discord-api

### Troubleshooting

1. Check logs/bot.log for errors
2. Verify configuration in config.json
3. Test with simple commands first
4. Check Discord bot permissions
5. Review GitHub issues (if open source)

---

## Quick Command Reference

### Admin Commands

```
!setup_store              # Create storefront panel
!setup_tickets            # Create ticket support panel
!deposit @user <amount>   # Credit user wallet (cents)
!manual_complete @user <product_name> <price>  # Manual order
!refund-approve @user     # Approve refund
!refund-reject @user      # Reject refund
!pending-refunds          # List pending refunds
!referral-blacklist @user # Blacklist user from cashback
!sendref-cashb            # Process all pending cashback
!sendref-cashb @user      # Process cashback for user
```

### User Commands

```
/balance      # Check wallet balance
/deposit      # Request wallet deposit
/orders       # View order history
/profile      # View profile with stats
/invite       # Get referral code
/invites      # View referral stats
/setref       # Link to referrer
/submitrefund # Submit refund request
```

---

## Success Checklist

- [ ] Bot online and responding
- [ ] All configuration complete
- [ ] All required channels created
- [ ] All required roles created
- [ ] Ticket categories set up
- [ ] Storefront panel created (`!setup_store`)
- [ ] Ticket panel created (`!setup_tickets`)
- [ ] Products imported
- [ ] Test wallet deposit successful
- [ ] Test purchase successful
- [ ] Test ticket creation successful
- [ ] Test refund flow successful
- [ ] Test referral system successful
- [ ] Logging channels receiving logs
- [ ] Database backups configured
- [ ] Bot running as service (optional)

---

## Next Steps

Once setup is complete:

1. **Announce to your community** - Let users know the bot is live
2. **Monitor initial usage** - Watch for any issues
3. **Gather feedback** - Ask users about their experience
4. **Fine-tune settings** - Adjust rate limits, prices, etc.
5. **Expand products** - Add more products as needed
6. **Scale as needed** - Monitor performance and upgrade hosting if needed

---

**Setup Complete!** 🎉

Your Apex Digital bot is now fully deployed and ready for production use on Ubuntu.

For detailed testing results, see: `UBUNTU_E2E_TEST_REPORT.md`

---

*Last Updated: December 3, 2025*
