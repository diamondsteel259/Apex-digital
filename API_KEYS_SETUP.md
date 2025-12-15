# API Keys Setup Guide

**Date:** 2025-12-14

---

## 🔐 HOW TO PROVIDE API KEYS

### **Option 1: Environment Variables (Recommended)**

1. **Create/Edit `.env` file in project root:**
   ```bash
   cd ~/Apex-digital
   nano .env
   ```

2. **Add your API keys:**
   ```
   # Google Gemini API (Free & Ultra Tier)
   GEMINI_API_KEY=AIzaSyC...your-key-here...
   
   # Groq API (Premium Tier)
   GROQ_API_KEY=gsk_...your-key-here...
   ```

3. **Save and exit** (Ctrl+X, Y, Enter)

4. **Verify `.env` is in `.gitignore`:**
   ```bash
   grep .env .gitignore
   ```
   If not, add it:
   ```bash
   echo ".env" >> .gitignore
   ```

### **Option 2: Direct in Code (Temporary - NOT RECOMMENDED)**

If you need to test quickly, you can temporarily add to `cogs/ai_support.py`:
```python
GEMINI_API_KEY = "AIzaSyC...your-key-here..."
GROQ_API_KEY = "gsk_...your-key-here..."
```

**⚠️ REMOVE BEFORE COMMITTING TO GIT!**

---

## 📋 API KEYS YOU NEED

### **1. Google Gemini API Key**

**Where to get it:**
1. Go to: https://aistudio.google.com/
2. Sign in with Google account
3. Click **"Get API Key"** (top right)
4. Click **"Create API Key"**
5. Choose **"Create API key in new project"**
6. Copy the key (starts with `AIza...`)

**Models we'll use:**
- `gemini-2.5-flash-lite` - Free tier (text only, 10 general + 20 product questions/day)
- `gemini-2.5-flash` - Ultra tier (text + images, 100 general + 200 product questions/day + 50 images/month)

**⚠️ IMPORTANT:** Make sure you use these exact model names in the code!

**Free tier limits:**
- 1M tokens/day (input)
- 1M tokens/day (output)

---

### **2. Groq API Key**

**Where to get it:**
1. Go to: https://console.groq.com/
2. Sign up for free account
3. Verify email
4. Go to **"API Keys"** section
5. Click **"Create API Key"**
6. Name it: `Apex Core Bot`
7. Copy the key (starts with `gsk_...`)

**Model we'll use:**
- `llama-3.1-8b-instant` - Premium tier (fast, cheap, 50 general + 100 product questions/day)

**⚠️ IMPORTANT:** Make sure you use this exact model name in the code!

**Pricing:**
- $0.00052 per 1K tokens (very affordable!)

---

## ✅ VERIFICATION

After adding keys, the bot will:
1. Load keys from `.env` on startup
2. Test connections to APIs
3. Log any errors if keys are invalid

**Check logs:**
```bash
tail -f bot.log | grep -i "api\|gemini\|groq"
```

---

## 🔒 SECURITY CHECKLIST

- [ ] API keys stored in `.env` file
- [ ] `.env` in `.gitignore`
- [ ] Never committed to Git
- [ ] Never logged in code
- [ ] Never sent to users
- [ ] Environment variables loaded correctly

---

## 🚀 READY TO USE

Once keys are in `.env`, restart the bot:
```bash
# Stop bot (if running)
pkill -f "python.*bot.py"

# Start bot
cd ~/Apex-digital
source venv/bin/activate
nohup python3 bot.py > bot.log 2>&1 &
```

The bot will automatically load the keys! ✅

