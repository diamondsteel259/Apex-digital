# 🚀 Complete Setup Checklist

## ✅ What's Already Done

- ✅ Terms of Service updated (G2G-style with account bans and transaction facilitation)
- ✅ Atto swap feature implemented and documented in `/help`
- ✅ Tipbot monitoring system ready (needs bot IDs configured)
- ✅ All features implemented and documented

---

## 📋 What You Need to Do Now

### **1. Configure `.env` File** ⚠️ REQUIRED

Your `.env` file should contain:

```env
# Discord Bot Token (REQUIRED)
DISCORD_TOKEN=your_discord_bot_token_here

# Atto Integration (OPTIONAL - Skip for now if no nodes)
ATTO_MAIN_WALLET_ADDRESS=atto://your_main_wallet_address
ATTO_NODE_API=http://localhost:8080
ATTO_DEPOSIT_CHECK_INTERVAL=30

# AI Support (REQUIRED if using AI features)
GEMINI_API_KEY=your_gemini_api_key_here
GROQ_API_KEY=your_groq_api_key_here

# Crypto Wallets (OPTIONAL)
BTC_WALLET_ADDRESS=your_bitcoin_address_here
ETH_WALLET_ADDRESS=your_ethereum_address_here
SOL_WALLET_ADDRESS=your_solana_address_here
TON_WALLET_ADDRESS=your_ton_address_here

# Payment Gateways (OPTIONAL)
BINANCE_PAY_ID=your_binance_pay_id_here
PAYPAL_EMAIL=your_paypal@email.com
STRIPE_PUBLIC_KEY=pk_live_your_stripe_public_key
STRIPE_SECRET_KEY=sk_live_your_stripe_secret_key

# Blockchain APIs (OPTIONAL)
ETHERSCAN_API_KEY=your_etherscan_api_key_here
```

**Note:** Only add what you need. Atto can be skipped for now if you don't have nodes.

---

### **2. Configure Tipbot IDs** ⚠️ REQUIRED FOR TIPBOT MONITORING

**Location:** `cogs/tipbot_monitoring.py` (lines 22-27)

**How to Get Bot IDs:**
1. Enable Developer Mode in Discord (Settings > Advanced > Developer Mode)
2. Right-click the tipbot in your server
3. Click "Copy ID"
4. Update the code:

```python
TIPBOT_IDS = {
    "tip.cc": YOUR_TIPCC_BOT_ID_HERE,      # e.g., 123456789012345678
    "cryptojar": YOUR_CRYPTOJAR_BOT_ID,    # e.g., 987654321098765432
    "gemma": YOUR_GEMMA_BOT_ID,            # e.g., 456789012345678901
    "seto": YOUR_SETO_BOT_ID,               # e.g., 234567890123456789
}
```

**After updating:**
- Restart the bot for changes to take effect
- The bot will monitor messages from these tipbots in ticket channels
- Payments will be automatically verified and orders fulfilled

---

### **3. How Swapping Works** ✅ ALREADY DOCUMENTED

The swap feature is **fully documented** in the `/help` command under the **"💎 Atto"** category.

**How It Works:**
1. User has USD wallet balance (from purchases, tips, etc.)
2. User runs `/attoswap <amount>` (e.g., `/attoswap 50`)
3. Bot:
   - Checks user's wallet balance
   - Fetches current Atto price from XT.com
   - Converts USD amount to Atto at market rate
   - Deducts USD from wallet balance
   - Adds Atto to user's Atto balance
   - Logs the swap transaction

**Benefits:**
- ✅ Instant conversion at market rate
- ✅ Enables instant withdrawal (Atto can be withdrawn immediately)
- ✅ No fees
- ✅ Real-time price from XT.com exchange

**Documentation in Help:**
- Main help menu mentions Atto integration
- `/help` → "💎 Atto" button → Shows detailed swap info
- Command: `/attoswap <amount>` - Convert wallet to Atto

---

### **4. Restart the Bot** ⚠️ REQUIRED

After making any changes:

```bash
# Stop the bot
pkill -f "python.*bot.py"

# Navigate to directory
cd ~/Apex-digital

# Activate virtual environment
source venv/bin/activate

# Start the bot
nohup python3 bot.py > bot.log 2>&1 &

# View logs
tail -f bot.log
```

---

### **5. Run `/setup` Command** ⚠️ REQUIRED

After restarting:
1. Go to your Discord server
2. Run `/setup` command
3. This will:
   - Deploy updated Terms of Service
   - Clean up old channels/roles/categories
   - Reorganize everything properly
   - Create all new channels for features
   - Set up all panels and permanent messages

---

## 📚 Feature Documentation Status

### ✅ Fully Documented in `/help`:
- ✅ **Shopping** - Product browsing, purchasing, cart
- ✅ **Wallet** - Balance, deposits, withdrawals
- ✅ **Atto** - Deposit, balance, swap, pay, withdraw, price
- ✅ **AI Support** - All tiers, limits, features
- ✅ **Support** - Tickets, refunds, help
- ✅ **VIP & Rewards** - Tiers, referrals, benefits
- ✅ **Security** - PIN system, what's protected
- ✅ **Payments** - All payment methods
- ✅ **Gifts** - Gift codes, sending gifts

### ✅ Swapping Feature:
- ✅ Documented in main help menu
- ✅ Detailed explanation in "💎 Atto" section
- ✅ Command: `/attoswap <amount>`
- ✅ Explains benefits (instant withdrawal)
- ✅ Shows exchange rate info

---

## 🔍 Verification Checklist

After setup, verify:

- [ ] Bot is online and responding
- [ ] `/help` command works and shows all categories
- [ ] `/attoswap` command is visible and works
- [ ] Terms of Service panel is visible in `📜-rules-and-tos` channel
- [ ] Privacy Policy panel is visible in `🔒-privacy` channel
- [ ] All channels are organized correctly
- [ ] All roles are assigned correctly
- [ ] Tipbot IDs are configured (if using tipbots)
- [ ] Atto node is configured (if using Atto)
- [ ] AI API keys are set (if using AI features)

---

## 🆘 Troubleshooting

### Bot Not Starting?
- Check `.env` file exists and has `DISCORD_TOKEN`
- Check virtual environment is activated
- Check logs: `tail -f bot.log`

### Tipbot Monitoring Not Working?
- Verify tipbot IDs are correct in `cogs/tipbot_monitoring.py`
- Check bot has permission to read messages in ticket channels
- Restart bot after updating tipbot IDs

### Atto Features Not Working?
- Verify `ATTO_NODE_API` is set in `.env`
- Check node is accessible (if using local node)
- Atto features will show errors if node unavailable (this is expected)

### Swapping Not Working?
- Check user has wallet balance
- Check Atto price API is accessible (XT.com)
- Check logs for errors: `tail -f bot.log | grep -i atto`

---

## 📝 Summary

**What You Need to Do:**
1. ✅ Update `.env` with your API keys and tokens
2. ✅ Configure tipbot IDs in `cogs/tipbot_monitoring.py` (if using tipbots)
3. ✅ Restart the bot
4. ✅ Run `/setup` in Discord
5. ✅ Verify everything works

**What's Already Done:**
- ✅ All features implemented
- ✅ All features documented in `/help`
- ✅ Swapping feature fully working and documented
- ✅ Terms of Service updated (G2G-style)
- ✅ Everything ready to go!

---

**You're all set!** 🎉 Just configure the `.env` file and tipbot IDs, then restart and run `/setup`!

