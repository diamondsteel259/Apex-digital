# API Setup Guide - Step by Step

**Date:** 2025-12-14  
**Purpose:** Get API keys for AI models safely

---

## 🔐 SECURITY FIRST

**IMPORTANT:**
- ✅ Never commit API keys to Git
- ✅ Never share API keys publicly
- ✅ Store in `.env` file (already in `.gitignore`)
- ✅ Use environment variables in code
- ✅ Never log API keys

---

## 1. GOOGLE GEMINI API (Free & Ultra Tier)

### **Step 1: Get API Key**
1. Go to: **https://aistudio.google.com/**
2. Sign in with your Google account
3. Click **"Get API Key"** button (top right)
4. Click **"Create API Key"**
5. Choose:
   - **Create API key in new project** (recommended)
   - OR **Create API key in existing project**
6. Copy the API key (starts with `AIza...`)
7. **Save it immediately** - you won't see it again!

### **Step 2: Store API Key**
1. Create/edit `.env` file in project root:
   ```bash
   cd ~/Apex-digital
   nano .env
   ```

2. Add:
   ```
   GEMINI_API_KEY=AIzaSyC...your-key-here...
   ```

3. Save and exit (Ctrl+X, Y, Enter)

### **Step 3: Verify**
- Check `.gitignore` includes `.env`
- Never commit `.env` to Git

### **Models Available:**
- `gemini-2.5-flash-lite` - Free tier (fast, free)
- `gemini-2.5-flash` - Ultra tier (text + images)

### **Pricing:**
- **Free:** 1M tokens/day (input), 1M tokens/day (output)
- **Paid:** $0.075 per 1M tokens (input), $0.30 per 1M tokens (output)
- **Images:** ~$0.04 per image

---

## 2. GROQ API (Premium Tier)

### **Step 1: Get API Key**
1. Go to: **https://console.groq.com/**
2. Sign up for free account (email + password)
3. Verify your email
4. Log in
5. Go to **"API Keys"** section (left sidebar)
6. Click **"Create API Key"**
7. Name it: `Apex Core Bot`
8. Copy the API key (starts with `gsk_...`)
9. **Save it immediately** - you won't see it again!

### **Step 2: Store API Key**
1. Edit `.env` file:
   ```bash
   nano .env
   ```

2. Add:
   ```
   GROQ_API_KEY=gsk_...your-key-here...
   ```

3. Save and exit

### **Step 3: Verify**
- Check API key works (we'll test in code)

### **Models Available:**
- `llama-3.1-8b-instant` - Recommended (fast, cheap)
- `llama-3.1-70b-versatile` - Better quality (slightly more expensive)

### **Pricing:**
- **Llama 3.1 8B:** $0.00052 per 1K tokens
- **Llama 3.1 70B:** $0.00059 per 1K tokens
- **Rate Limit:** 1000 requests/minute
- **Very affordable!**

---

## 3. ENVIRONMENT VARIABLES SETUP

### **Create `.env` file:**
```bash
cd ~/Apex-digital
touch .env
nano .env
```

### **Add all keys:**
```
# Google Gemini API
GEMINI_API_KEY=AIzaSyC...your-key-here...

# Groq API
GROQ_API_KEY=gsk_...your-key-here...
```

### **Verify `.gitignore`:**
```bash
cat .gitignore | grep .env
```

Should show:
```
.env
.env.local
```

If not, add to `.gitignore`:
```bash
echo ".env" >> .gitignore
echo ".env.local" >> .gitignore
```

---

## 4. CODE INTEGRATION

### **Install Required Packages:**
```bash
pip install google-generativeai groq python-dotenv
```

### **Load Environment Variables:**
```python
from dotenv import load_dotenv
import os

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not found in environment")
```

### **Never Do This:**
```python
# ❌ BAD - Hardcoded key
api_key = "AIzaSyC..."

# ❌ BAD - In config file
api_key = config["gemini_key"]

# ✅ GOOD - Environment variable
api_key = os.getenv("GEMINI_API_KEY")
```

---

## 5. TESTING API KEYS

### **Test Gemini:**
```python
import google.generativeai as genai

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-2.5-flash-lite')
response = model.generate_content("Hello!")
print(response.text)
```

### **Test Groq:**
```python
from groq import Groq

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
response = client.chat.completions.create(
    model="llama-3.1-8b-instant",
    messages=[{"role": "user", "content": "Hello!"}]
)
print(response.choices[0].message.content)
```

---

## 6. SECURITY CHECKLIST

- [ ] API keys stored in `.env` file
- [ ] `.env` in `.gitignore`
- [ ] Never committed to Git
- [ ] Never logged in code
- [ ] Never sent to users
- [ ] Environment variables loaded correctly
- [ ] Error handling if keys missing
- [ ] Rate limiting implemented
- [ ] Usage monitoring enabled

---

## 7. MONITORING USAGE

### **Groq Dashboard:**
- Go to: https://console.groq.com/usage
- View API usage
- Monitor costs
- Set up alerts

### **Google Cloud Console:**
- Go to: https://console.cloud.google.com/
- Select your project
- View API usage
- Monitor costs
- Set up billing alerts

---

## ✅ READY TO USE

Once you have:
1. ✅ Gemini API key in `.env`
2. ✅ Groq API key in `.env`
3. ✅ Packages installed
4. ✅ Code loads environment variables

You're ready to implement the AI system! 🚀

