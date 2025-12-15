# 🚀 Quick Start Checklist

## ✅ Step 1: Configure .env File

Make sure your `.env` file has these **required** values:

```env
# REQUIRED - Discord Bot Token
DISCORD_TOKEN=your_discord_bot_token_here

# REQUIRED - AI Support System
GEMINI_API_KEY=your_gemini_api_key_here
GROQ_API_KEY=your_groq_api_key_here

# OPTIONAL - Atto (skip for now)
# ATTO_NODE_API=...
# ATTO_MAIN_WALLET_ADDRESS=...
```

**Note**: Atto can be configured later when you have public nodes.

---

## ✅ Step 2: Restart the Bot

```bash
# Stop the bot if running
pkill -f "python.*bot.py"

# Navigate to project directory
cd ~/Apex-digital

# Activate virtual environment
source venv/bin/activate

# Start the bot
nohup python3 bot.py > bot.log 2>&1 &

# Check if it started successfully
tail -f bot.log
```

**Look for**: `Apex Core is ready!` message

---

## ✅ Step 3: Run Setup Command

In Discord, run:
```
/setup
```

This will:
- ✅ Create/update all roles
- ✅ Create/update all categories
- ✅ Create/update all channels
- ✅ Set up permissions
- ✅ Deploy permanent messages (Welcome, Rules, FAQ, Privacy, etc.)
- ✅ Clean up old channels/roles/categories
- ✅ Log all IDs to config.json

**Wait for**: Setup completion message

---

## ✅ Step 4: Verify Everything Works

### Test Commands:
1. **Help Command**: `/help` - Should show all features
2. **Wallet**: `/balance` - Check wallet system
3. **AI Support**: `/ai` - Test AI features (if keys configured)
4. **Products**: `/products` - Browse products
5. **Tickets**: Click "Open Ticket" button - Test ticket system

### Check Channels:
- ✅ Welcome message in `👋-welcome`
- ✅ Rules/TOS in `📜-rules-and-tos`
- ✅ Privacy policy in `🔒-privacy`
- ✅ FAQ in `❓-faq`
- ✅ Bot overview in `📢-announcements`

---

## ✅ Step 5: Monitor Logs

```bash
# Watch live logs
tail -f bot.log

# Filter for errors
tail -f bot.log | grep -i error

# Filter for specific features
tail -f bot.log | grep -i "ai\|ticket\|payment"
```

---

## ⚠️ Common Issues

### Bot won't start:
- Check `.env` file exists and has `DISCORD_TOKEN`
- Check virtual environment is activated
- Check Python dependencies: `pip install -r requirements.txt`

### Setup command fails:
- Check bot has admin permissions
- Check bot can create channels/roles
- Check logs for specific errors

### Commands not showing:
- Wait 1-2 minutes for command sync
- Try restarting the bot
- Check bot has proper permissions

---

## 📋 What's Already Implemented

✅ All core features (wallet, products, orders, tickets)
✅ AI Support System (3 tiers)
✅ Wishlist, Product Tags, PIN Security
✅ Tips & Airdrops
✅ Payment Management
✅ Supplier Import
✅ Review System
✅ Referral System
✅ Data Deletion
✅ Privacy Policy & TOS
✅ Enhanced Help Command
✅ Multi-node Atto (ready when you have nodes)

---

## 🎯 Next Steps After Setup

1. **Import Products**: Use `/importsupplier` or `/importcsv`
2. **Configure Payment Methods**: Use `/addpayment` (admin)
3. **Test Transactions**: Make a test purchase
4. **Set Up Atto**: When you get public node URLs, add to `.env`

---

**Status**: Ready to launch! 🚀
