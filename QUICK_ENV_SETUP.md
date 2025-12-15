# Quick .env File Setup

## ✅ YES, it's supposed to be empty initially!

You need to add your API keys. Here's exactly what to add:

---

## 📝 Step-by-Step

### 1. Open the file:
```bash
cd ~/Apex-digital
nano .env
```

### 2. Add these two lines (replace with YOUR actual keys):

```
GEMINI_API_KEY=AIzaSyC...your-actual-key-here...
GROQ_API_KEY=gsk_...your-actual-key-here...
```

### 3. Example (with placeholder keys):
```
GEMINI_API_KEY=AIzaSyC1234567890abcdefghijklmnopqrstuvwxyz
GROQ_API_KEY=gsk_1234567890abcdefghijklmnopqrstuvwxyz
```

### 4. Save:
- Press `Ctrl + X`
- Press `Y` (to confirm)
- Press `Enter` (to save)

---

## 🔑 Where to Get Your Keys

### **Gemini API Key:**
1. Go to: https://aistudio.google.com/
2. Sign in with Google
3. Click "Get API Key" (top right)
4. Click "Create API Key"
5. Copy the key (starts with `AIza...`)

### **Groq API Key:**
1. Go to: https://console.groq.com/
2. Sign up/login
3. Go to "API Keys" section
4. Click "Create API Key"
5. Copy the key (starts with `gsk_...`)

---

## ✅ Verify It Worked

After saving, check the file:
```bash
cat .env
```

You should see your two keys (without the `...` placeholders).

---

## ⚠️ Important

- **Never share your API keys**
- **Never commit `.env` to Git** (it's already in `.gitignore`)
- **Keep your keys secret!**

---

## 🚀 After Adding Keys

Restart the bot:
```bash
pkill -f "python.*bot.py"
cd ~/Apex-digital
source venv/bin/activate
nohup python3 bot.py > bot.log 2>&1 &
```

Check logs to verify:
```bash
tail -f bot.log | grep -i "gemini\|groq"
```

You should see:
- ✅ Gemini API initialized
- ✅ Groq API initialized

---

**That's it! The file should have exactly 2 lines with your API keys.**

