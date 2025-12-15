# Next Steps Guide - What to Do Now

**Date:** 2025-12-14  
**Status:** Ready for Setup

---

## ✅ What's Already Done

1. ✅ Privacy Policy created (`content/privacy_policy.md`)
2. ✅ Terms of Service updated (`content/terms_of_service.md`)
3. ✅ Data deletion command created (`cogs/data_deletion.py`)
4. ✅ Help command enhanced
5. ✅ Bot status system fixed
6. ✅ All code changes complete

---

## 📋 What You Need to Do

### **Step 1: Create `.env` File** (If Not Already Done)

The bot needs environment variables for API keys and configuration.

```bash
cd ~/Apex-digital
nano .env
```

**Minimum Required Variables:**
```env
# Discord Bot Token (REQUIRED)
DISCORD_TOKEN=your_discord_bot_token_here

# AI Support System (Optional - if using AI features)
GEMINI_API_KEY=your_gemini_api_key_here
GROQ_API_KEY=your_groq_api_key_here

# Atto Integration (Optional - if using Atto)
ATTO_MAIN_WALLET_ADDRESS=atto://your_wallet_address
ATTO_NODE_API=http://localhost:8080
```

**Full template:** See `ENV_TEMPLATE.md` for all available options.

**Security:** 
```bash
chmod 600 .env  # Restrict file permissions
```

---

### **Step 2: Restart the Bot**

The new `data_deletion.py` cog will be automatically loaded when you restart.

```bash
# Stop the bot
pkill -f "python.*bot.py"

# Navigate to directory
cd ~/Apex-digital

# Activate virtual environment
source venv/bin/activate

# Start the bot
nohup python3 bot.py > bot.log 2>&1 &

# Check if it started successfully
tail -f bot.log
```

**Look for:**
- ✅ `Loaded extension: cogs.data_deletion`
- ✅ `Logged in as Apex Core#XXXX`
- ✅ `Apex Core is ready!`

---

### **Step 3: Run `/setup` Command**

This will deploy the Privacy Policy and Terms of Service panels.

1. Go to your Discord server
2. Run `/setup` command
3. Select "Full Server Setup" or "Deploy Panels"
4. The setup will:
   - Deploy Privacy Policy in `#🔒-privacy` channel
   - Deploy Terms of Service in `#📜-rules-and-tos` channel
   - Clean up old messages
   - Create all channels and roles

**Note:** The setup command will automatically:
- Create the privacy channel if it doesn't exist
- Deploy the privacy policy as a permanent message
- Deploy the TOS as a permanent message

---

### **Step 4: Verify Everything Works**

**Test Commands:**
1. `/help` - Should show new category buttons
2. `/deletedata confirm:DELETE` - Should show deletion request form
3. Check `#🔒-privacy` channel - Should have privacy policy message
4. Check `#📜-rules-and-tos` channel - Should have TOS message

**Check Bot Status:**
```bash
tail -f bot.log | grep -i "error\|failed\|exception"
```

---

## 🔧 Optional: Configure Additional Features

### **Atto Integration** (If Using)

1. Set up Atto node (see `ATTO_NODE_SETUP.md`)
2. Add to `.env`:
   ```env
   ATTO_MAIN_WALLET_ADDRESS=atto://your_address
   ATTO_NODE_API=http://your_node_url
   ```
3. Use `/attosetup` command to configure

### **AI Support** (If Using)

1. Get API keys:
   - Gemini: https://makersuite.google.com/app/apikey
   - Groq: https://console.groq.com/keys
2. Add to `.env`:
   ```env
   GEMINI_API_KEY=your_key
   GROQ_API_KEY=your_key
   ```

### **Payment Gateways** (If Using)

1. Configure in `config/payments.json`
2. Add API keys to `.env` if needed
3. Use `/addpayment` command to add payment methods

---

## 📊 What Gets Deployed on `/setup`

When you run `/setup`, it will:

1. **Clean Up:**
   - Delete old ticket messages
   - Remove old panels
   - Clean up duplicate roles/categories/channels

2. **Create Channels:**
   - `#🔒-privacy` - Privacy Policy
   - `#📜-rules-and-tos` - Terms of Service
   - All other channels from blueprint

3. **Deploy Panels:**
   - Privacy Policy (permanent message)
   - Terms of Service (permanent message)
   - Welcome message
   - Help panel
   - FAQ panel
   - Product catalog
   - Support panel

4. **Log IDs:**
   - All channel IDs → `config.json`
   - All category IDs → `config.json`
   - All role IDs → `config.json`

---

## ⚠️ Important Notes

1. **Bot Token:** Must be in `.env` file (not `config.json`)
2. **Restart Required:** Bot must be restarted to load new cog
3. **Setup Command:** Must be run to deploy privacy/TOS panels
4. **Permissions:** Bot needs "Manage Channels" and "Send Messages" permissions

---

## 🐛 Troubleshooting

**Bot won't start:**
```bash
# Check logs
tail -f bot.log

# Check for missing dependencies
source venv/bin/activate
pip install -r requirements.txt
```

**Cog not loading:**
```bash
# Check if file exists
ls -la cogs/data_deletion.py

# Check logs for errors
tail -f bot.log | grep -i "data_deletion\|error"
```

**Setup command fails:**
- Check bot permissions (Manage Channels, Send Messages)
- Check if channels already exist
- Check logs for specific errors

**Privacy/TOS not showing:**
- Run `/setup` again
- Check if channels were created
- Check bot permissions in those channels

---

## ✅ Checklist

Before going live:

- [ ] `.env` file created with Discord token
- [ ] Bot restarted and running
- [ ] `/setup` command executed successfully
- [ ] Privacy Policy visible in `#🔒-privacy`
- [ ] Terms of Service visible in `#📜-rules-and-tos`
- [ ] `/help` command works with new buttons
- [ ] `/deletedata` command works
- [ ] No errors in `bot.log`
- [ ] All channels created correctly
- [ ] All roles assigned correctly

---

## 🚀 You're Ready!

Once you've completed these steps:
1. ✅ Bot is running
2. ✅ Privacy and TOS are deployed
3. ✅ All commands work
4. ✅ No errors in logs

**Your bot is ready for launch!** 🎉

---

**Need Help?**
- Check `bot.log` for errors
- Review `ENV_TEMPLATE.md` for configuration
- Check `DISCORD_TOS_COMPLIANCE_REPORT.md` for compliance info

