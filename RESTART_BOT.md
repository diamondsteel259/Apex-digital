# How to Restart the Bot Properly

## ✅ Your Bot Status

**Good news:** All packages installed successfully! ✅
- python-dotenv ✅
- google-generativeai ✅  
- groq ✅

**Next:** Restart the bot to load new cogs.

---

## 🔄 Restart Steps

### **Option 1: Simple Restart (Recommended)**

```bash
cd ~/Apex-digital
pkill -f "python.*bot.py"
sleep 2
source venv/bin/activate
nohup python3 bot.py > bot.log 2>&1 &
```

### **Option 2: Check Status First**

```bash
# Check if bot is running
ps aux | grep "[p]ython.*bot.py"

# If running, stop it
pkill -f "python.*bot.py"

# Wait a moment
sleep 2

# Start fresh
cd ~/Apex-digital
source venv/bin/activate
nohup python3 bot.py > bot.log 2>&1 &

# Check logs
tail -f bot.log
```

---

## ✅ Verify New Cogs Loaded

After restart, check logs for:

```bash
tail -f bot.log | grep -i "ai_support\|wishlist\|pin_security\|affiliate\|product_tags\|gemini\|groq"
```

You should see:
- ✅ Loaded extension: cogs.ai_support
- ✅ Loaded extension: cogs.wishlist
- ✅ Loaded extension: cogs.pin_security
- ✅ Loaded extension: cogs.affiliate
- ✅ Loaded extension: cogs.product_tags
- ✅ Gemini API initialized
- ✅ Groq API initialized

---

## 🚨 If Cogs Don't Load

If you see errors, check:

```bash
# Check for syntax errors
python3 -m py_compile cogs/ai_support.py

# Check full error logs
tail -100 bot.log | grep -i "error\|exception\|traceback"
```

---

## 📋 Quick Commands

**Stop bot:**
```bash
pkill -f "python.*bot.py"
```

**Start bot:**
```bash
cd ~/Apex-digital
source venv/bin/activate
nohup python3 bot.py > bot.log 2>&1 &
```

**Watch logs:**
```bash
tail -f bot.log
```

**Check if running:**
```bash
ps aux | grep "[p]ython.*bot.py"
```

---

**After restart, the new features will be available!** 🎉

