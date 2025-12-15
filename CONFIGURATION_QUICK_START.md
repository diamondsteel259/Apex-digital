# Apex Core - Configuration Quick Start Guide

This guide helps you set up Apex Core bot configuration quickly and correctly.

## 📋 Prerequisites

- Python 3.11+
- Discord bot token
- Discord server with admin access
- Basic understanding of JSON and environment variables

---

## 🚀 Quick Setup (5 minutes)

### Step 1: Environment Variables

```bash
# Copy the example file
cp .env.example .env

# Edit with your values
nano .env  # or use your preferred editor

# Set secure permissions
chmod 600 .env
```

**Minimum Required:**
- `DISCORD_TOKEN` - Your Discord bot token

**Recommended:**
- `GEMINI_API_KEY` - For AI support features
- `ATTO_MAIN_WALLET_ADDRESS` - For cryptocurrency payments

### Step 2: Main Configuration

```bash
# Copy the example file
cp config.example.json config.json

# Edit with your values
nano config.json

# Set secure permissions
chmod 600 config.json
```

**Replace These Placeholders:**
- `YOUR_DISCORD_BOT_TOKEN_HERE` (or use DISCORD_TOKEN env var instead)
- `123456789012345678` - Guild IDs (your Discord server IDs)
- `123456789012345678` - Role IDs (from your Discord server)
- Channel IDs in `logging_channels` section
- Category IDs in `category_ids` section

### Step 3: Payment Configuration (Optional)

```bash
# Create config directory if needed
mkdir -p config

# Copy the example file
cp config/payments.json.example config/payments.json

# Edit with your values
nano config/payments.json

# Set secure permissions
chmod 600 config/payments.json
```

**Replace These Placeholders:**
- `YOUR_BINANCE_PAY_ID` - Your Binance Pay merchant ID
- `YOUR_ATTO_ADDRESS` - Your Atto wallet address
- `your-paypal@example.com` - Your PayPal email
- Cryptocurrency wallet addresses

### Step 4: Validate Configuration

```bash
# Run the validation script
python3 scripts/validate_config.py
```

**Expected Output:**
- ✅ Green checkmarks for correctly configured items
- ⚠️ Yellow warnings for placeholders or recommendations
- ❌ Red errors for critical issues (fix these!)

### Step 5: Install Dependencies & Start Bot

```bash
# Install dependencies
pip install -r requirements.txt

# Optional: Install enhanced features
pip install -r requirements-optional.txt

# Start the bot
python3 bot.py
```

---

## 🔍 Finding Discord IDs

You need various IDs from your Discord server. Here's how to get them:

### Enable Developer Mode

1. Open Discord
2. Go to User Settings → Advanced
3. Enable "Developer Mode"

### Get Server (Guild) ID

1. Right-click your server name
2. Click "Copy Server ID"
3. Paste into `guild_ids` in config.json

### Get Role IDs

1. Go to Server Settings → Roles
2. Right-click a role
3. Click "Copy Role ID"
4. Paste into `role_ids` in config.json

### Get Channel IDs

1. Right-click a channel
2. Click "Copy Channel ID"
3. Paste into `logging_channels` or `channel_ids` in config.json

### Get Category IDs

1. Right-click a category (folder)
2. Click "Copy Category ID"
3. Paste into `category_ids` in config.json

---

## 🔐 Security Checklist

Before deploying to production:

- [ ] Set file permissions: `chmod 600 .env config.json config/payments.json`
- [ ] Verify `.env` is in `.gitignore` (it already is!)
- [ ] Never commit real credentials to version control
- [ ] Use environment variables for tokens (preferred over config files)
- [ ] Enable 2FA on all service accounts (Discord, Stripe, etc.)
- [ ] Keep backup of credentials in secure password manager
- [ ] Rotate API keys regularly (every 90 days recommended)

---

## 🧪 Testing Your Configuration

### Test Discord Connection

```bash
# Start the bot and watch for connection message
python3 bot.py
# Look for: "Logged in as YourBot (ID: ...)"
```

### Test Configuration Validation

```bash
# Should pass without errors
python3 scripts/validate_config.py

# Check specific sections
python3 scripts/validate_config.py --env-only
```

### Test Environment Variables

```bash
# Verify environment variable is loaded
python3 -c "from dotenv import load_dotenv; import os; load_dotenv(); print('Token:', 'SET' if os.getenv('DISCORD_TOKEN') else 'NOT SET')"
```

---

## ❓ Common Issues & Solutions

### Issue: Bot won't start - "Invalid token"

**Solution:**
1. Check token format: Should be `xxxx.yyyy.zzzz` (three parts separated by dots)
2. Verify token in Discord Developer Portal
3. Make sure DISCORD_TOKEN env var doesn't have quotes or extra spaces
4. Try regenerating token in Discord Developer Portal

### Issue: Configuration validation fails

**Solution:**
1. Read the error messages carefully
2. Check for placeholder values (YOUR_*, 123456789012345678)
3. Verify all required fields are present
4. Run `python3 scripts/validate_config.py` for detailed errors

### Issue: Bot connects but commands don't work

**Solution:**
1. Check guild_ids includes your server
2. Verify bot has necessary permissions in Discord
3. Wait a few minutes for command sync
4. Check bot logs for errors

### Issue: Placeholder values detected

**Solution:**
1. Edit config.json and replace all `YOUR_*` values
2. Replace all `123456789012345678` with real Discord IDs
3. Run validation again: `python3 scripts/validate_config.py`

---

## 📚 Additional Resources

- **Full Audit Report:** `CONFIG_DEPS_AUDIT_REPORT.md`
- **Fixes Applied:** `CONFIG_DEPS_FIXES_SUMMARY.md`
- **Environment Template:** `ENV_TEMPLATE.md`
- **Main README:** `README.md`
- **Scripts Documentation:** `scripts/README.md`

---

## 🆘 Getting Help

If you're stuck:

1. ✅ Run `python3 scripts/validate_config.py` - it often identifies the issue
2. ✅ Check bot logs for error messages
3. ✅ Review configuration examples carefully
4. ✅ Verify all placeholders are replaced
5. ✅ Check file permissions are set correctly

---

## 🎯 Next Steps After Setup

Once your bot is running:

1. **Test Core Features:**
   - Create a test ticket
   - Test payment methods
   - Verify logging channels work
   - Check role assignments

2. **Configure Advanced Features:**
   - AI support system (if using Gemini/Groq)
   - Atto cryptocurrency integration
   - Payment gateways (Stripe, PayPal, etc.)
   - Refund system

3. **Set Up Monitoring:**
   - Watch error logs channel
   - Monitor audit logs
   - Set up external health checks

4. **Plan for Production:**
   - Set up systemd service (see `apex-core.service`)
   - Configure automatic backups
   - Document your specific configuration
   - Train staff on bot usage

---

**Estimated Setup Time:**
- Basic configuration: 5-10 minutes
- Full configuration with payments: 20-30 minutes
- Testing and validation: 10-15 minutes

**Total:** ~45 minutes for complete setup

---

Good luck with your Apex Core bot! 🚀
