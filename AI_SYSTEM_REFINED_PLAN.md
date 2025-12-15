# AI Support System - Refined Plan

**Date:** 2025-12-14  
**Status:** Planning - Refining Based on Requirements

---

## 🎯 THREE-TIER SYSTEM

### **FREE TIER: Gemini 2.5 Flash-Lite**
- **Model:** `gemini-2.5-flash-lite` (Google)
- **Limits:** 5-10 questions/day (configurable, recommend 10)
- **Features:**
  - ✅ General Q&A (e.g., "What's the best gun in COD Mobile?")
  - ✅ Product info (read-only from database)
  - ✅ Bot command help
  - ✅ General knowledge questions
  - ✅ Product recommendations
- **Cost to You:** $0 (Free Tier: 1M tokens/day)
- **Price to User:** $0

### **PREMIUM TIER: Groq Llama 3.1 8B**
- **Model:** `llama-3.1-8b-instant` (Groq)
- **Limits:** 20-25 questions/day (recommend 25)
- **Features:**
  - ✅ Everything from Free
  - ✅ Access to own order history
  - ✅ Access to own account info (balance, VIP tier)
  - ✅ General knowledge questions (more allowed)
  - ✅ Live search capability
  - ✅ Blazing fast responses (~200ms)
  - ✅ Personalized recommendations
- **Cost to You:** ~$0.00052 per 1K tokens (very cheap!)
- **Price to User:** $5-8/month

### **ULTRA TIER: Gemini 2.5 Flash**
- **Model:** `gemini-2.5-flash` (Google) - Text + Images
- **Limits:** 50-100 questions/day (recommend 100) + 50 images/month
- **Features:**
  - ✅ Everything from Premium
  - ✅ Image generation (50/month)
  - ✅ Higher question limit
  - ✅ Priority support
  - ✅ Advanced features
- **Cost to You:** ~$0.075 per 1M tokens (text) + ~$0.04/image
- **Price to User:** $10-15/month

---

## 🤔 KEY QUESTIONS ANSWERED

### **1. How Does AI Know Product Info/Prices?**

**Solution: Context Injection**

When user asks about products, the bot will:

1. **Query Database:**
   - Fetch product information
   - Get prices, descriptions, categories
   - Get stock status
   - Get review stats

2. **Build Context:**
   ```
   PRODUCTS AVAILABLE:
   - Instagram Followers: $5.99 (1000 followers)
   - YouTube Views: $3.99 (1000 views)
   - TikTok Likes: $2.99 (1000 likes)
   ...
   ```

3. **Inject into AI Prompt:**
   - Add product data to system prompt
   - AI can reference this data
   - AI can answer questions about products
   - AI can make recommendations

4. **For Paid Tiers:**
   - Also inject user's order history
   - Also inject user's account balance
   - Also inject user's VIP tier

**Example:**
```
User: "What products do you have?"
  ↓
Bot: [Queries database for all products]
  ↓
Bot: [Builds context: "Available products: Instagram Followers ($5.99), YouTube Views ($3.99)..."]
  ↓
Bot: [Sends to AI with context]
  ↓
AI: "We have Instagram Followers starting at $5.99 for 1000 followers..."
```

---

### **2. Free Tier - General Questions**

**Solution: Allow General Knowledge**

- **Free tier can ask:**
  - "What's the best gun in Call of Duty Mobile?"
  - "What's the tallest building in the world?"
  - "How do I cook pasta?"
  - General knowledge questions (5-10/day)

- **But still has access to:**
  - Product information (read-only)
  - Bot commands help
  - General FAQ

**Why this works:**
- Attracts users to try the system
- Shows value of AI
- Encourages upgrades to paid tiers
- Still limited (5-10/day) to prevent abuse

---

### **3. Paid Tiers - Better Perks**

**PREMIUM TIER ($5-8/month):**
- ✅ 20-25 questions/day (vs 5-10 free)
- ✅ Access to own order history
- ✅ Access to own account info
- ✅ General knowledge questions
- ✅ Faster responses (Groq is very fast)
- ✅ Live search capability
- ✅ Personalized recommendations

**ULTRA TIER ($10-15/month):**
- ✅ 50-100 questions/day
- ✅ Everything from Premium
- ✅ Image generation (50/month)
- ✅ Priority support
- ✅ Advanced features

**Additional Perks to Consider:**
- Early access to new features
- Exclusive AI features
- Higher priority in queue
- Custom AI personality
- Saved conversations

---

### **4. Question Limits Per Tier**

**Recommended:**
- **Free:** 10 questions/day (configurable)
- **Premium:** 25 questions/day
- **Ultra:** 100 questions/day

**Why:**
- Free: Enough to try, not enough to abuse
- Premium: Good value, encourages usage
- Ultra: High limit for power users

**Implementation:**
- Track questions per user per day
- Reset at midnight UTC
- Show remaining questions in response
- Block when limit reached

---

### **5. Token Usage Logging**

**What to Log:**
- User ID
- Tier (free/premium/ultra)
- Model used
- Tokens used (input + output)
- Cost (estimated)
- Timestamp
- Question asked (optional, for debugging)

**Database Table:**
```sql
CREATE TABLE ai_usage_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_discord_id INTEGER NOT NULL,
    tier TEXT NOT NULL,  -- 'free', 'premium', 'ultra'
    model TEXT NOT NULL,  -- 'gemini-flash-lite', 'groq-llama', 'gemini-flash'
    input_tokens INTEGER,
    output_tokens INTEGER,
    total_tokens INTEGER,
    estimated_cost_cents INTEGER,  -- Cost in cents
    question_preview TEXT,  -- First 100 chars
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Admin Commands:**
- `/ai usage @user` - View user's usage
- `/ai usage stats` - Overall statistics
- `/ai usage cost` - Total cost breakdown
- `/ai usage export` - Export to CSV

**Privacy:**
- Only admins can see usage
- Users can see their own usage summary
- Full logs kept private
- No sharing of user data

---

### **6. Cost Estimation**

**Per User Calculation:**
- Track tokens per user
- Calculate cost based on model pricing
- Show estimated cost to admin

**Example:**
```
User: @user123
Tier: Premium
Questions: 25/day
Avg tokens: 500/question
Total tokens: 12,500/day
Cost: $0.052 per 1K = $0.65/day = $19.50/month
```

**Admin Dashboard:**
- Total cost per day/week/month
- Cost per tier
- Cost per user (top users)
- Projected costs
- Break-even analysis

---

## 🔐 API SETUP & SECURITY

### **1. Gemini 2.5 Flash-Lite (Free Tier)**

**Setup:**
1. Go to: https://aistudio.google.com/
2. Sign in with Google account
3. Click "Get API Key"
4. Create new project or use existing
5. Copy API key
6. Store in environment variable: `GEMINI_API_KEY`

**Model:**
- `gemini-2.5-flash-lite` (for free tier)
- `gemini-2.5-flash` (for ultra tier images)

**Pricing:**
- Free: 1M tokens/day
- Paid: $0.075 per 1M tokens (input), $0.30 per 1M tokens (output)

**Security:**
- Store API key in environment variable
- Never log API key
- Never send API key to users
- Use `.env` file (add to `.gitignore`)

---

### **2. Groq Llama 3.1 8B (Premium Tier)**

**Setup:**
1. Go to: https://console.groq.com/
2. Sign up for account (free)
3. Go to "API Keys" section
4. Click "Create API Key"
5. Name it (e.g., "Apex Core Bot")
6. Copy API key (only shown once!)
7. Store in environment variable: `GROQ_API_KEY`

**Model:**
- `llama-3.1-8b-instant` (fast, affordable)
- Alternative: `llama-3.1-70b-versatile` (better quality, more expensive)

**Pricing:**
- **Llama 3.1 8B:** $0.00052 per 1K tokens (extremely cheap!)
- **Llama 3.1 70B:** $0.00059 per 1K tokens
- High rate limits (1000 requests/minute)
- **Example:** 25 questions/day × 500 tokens = 12,500 tokens = **$0.0065/day = $0.20/month per user**

**Security:**
- Store API key in environment variable
- Never log API key
- Never send API key to users
- Use `.env` file (add to `.gitignore`)

---

### **3. Gemini 2.5 Flash (Ultra Tier - Images)**

**Setup:**
- Same as Gemini Flash-Lite
- Use same API key
- Different model: `gemini-2.5-flash`

**Image Generation:**
- Use `generateContent` with image generation
- Limit: 50 images/month per user
- Cost: ~$0.04 per image

**Security:**
- Same as Gemini Flash-Lite
- Additional: Validate image requests
- Block inappropriate content

---

## 🏗️ IMPLEMENTATION ARCHITECTURE

### **How AI Gets Product Info:**

1. **Product Database Query:**
   ```python
   # When user asks about products
   products = await db.get_all_active_products()
   product_context = build_product_context(products)
   ```

2. **Context Building:**
   ```python
   def build_product_context(products):
       context = "AVAILABLE PRODUCTS:\n"
       for product in products:
           context += f"- {product['variant_name']}: ${product['price_cents']/100} ({product['description']})\n"
       return context
   ```

3. **AI Prompt:**
   ```python
   system_prompt = f"""
   You are a helpful Discord bot assistant for Apex Core.
   
   PRODUCT INFORMATION:
   {product_context}
   
   USER INFORMATION (if paid tier):
   - Balance: ${user_balance}
   - Orders: {order_count}
   - VIP Tier: {vip_tier}
   
   RULES:
   - You can reference product information above
   - You CANNOT access supplier information
   - You CANNOT access other users' data
   """
   ```

4. **Send to AI:**
   ```python
   response = await ai_client.chat(
       model=model,
       messages=[
           {"role": "system", "content": system_prompt},
           {"role": "user", "content": user_question}
       ]
   )
   ```

---

### **Question Limits:**

```python
# Check daily limit
daily_questions = await db.get_user_ai_questions_today(user_id)
limit = get_tier_limit(user_tier)  # 10, 25, or 100

if daily_questions >= limit:
    return "You've reached your daily limit. Upgrade to get more!"
```

---

### **Token Usage Logging:**

```python
# After AI response
await db.log_ai_usage(
    user_id=user_id,
    tier=user_tier,
    model=model_used,
    input_tokens=response.usage.input_tokens,
    output_tokens=response.usage.output_tokens,
    cost_cents=calculate_cost(response.usage, model_used)
)
```

---

## 📊 COST BREAKDOWN

### **Per User Costs:**

**Free Tier:**
- 10 questions/day
- ~200 tokens/question
- 2,000 tokens/day
- **Cost: $0** (within free tier)

**Premium Tier:**
- 25 questions/day
- ~500 tokens/question (more complex)
- 12,500 tokens/day
- Groq: $0.052 per 1K = **$0.65/day = $19.50/month**

**Ultra Tier:**
- 100 questions/day
- ~500 tokens/question
- 50,000 tokens/day
- Gemini: $0.075 per 1M = **$3.75/day = $112.50/month**
- Plus 50 images: 50 × $0.04 = **$2/month**
- **Total: ~$115/month**

### **Revenue vs Costs:**

**If 100 Premium users at $6/month:**
- Revenue: $600/month
- Costs: $1,950/month (100 × $19.50)
- **Loss: -$1,350/month** ❌

**If 100 Premium users at $8/month:**
- Revenue: $800/month
- Costs: $1,950/month
- **Loss: -$1,150/month** ❌

**Problem:** Costs are too high!

---

## 💡 COST OPTIMIZATION

### **Option 1: Reduce Question Limits**
- Premium: 15 questions/day (vs 25)
- Ultra: 50 questions/day (vs 100)
- **Savings: ~40%**

### **Option 2: Use Cheaper Models**
- Premium: Use Gemini Flash-Lite instead of Groq
- **Savings: ~80%** (Gemini free tier covers most)

### **Option 3: Hybrid Approach** ⭐ RECOMMENDED
- **Free:** Gemini Flash-Lite (10/day) - $0
- **Premium:** Gemini Flash-Lite (25/day) - $0-5/month
- **Ultra:** Gemini Flash (50/day + 50 images) - $10-15/month

**Why:**
- Gemini free tier covers most usage
- Only pay for heavy users
- Much more profitable

---

## ✅ REFINED RECOMMENDATION

### **FREE TIER:**
- Model: Gemini 2.5 Flash-Lite
- Limits: 10 questions/day
- Features: General Q&A + Product info
- Cost: $0
- Price: $0

### **PREMIUM TIER:**
- Model: Gemini 2.5 Flash-Lite (or Groq if needed)
- Limits: 25 questions/day
- Features: Everything + Own data access
- Cost: $0-5/month
- Price: $5-8/month

### **ULTRA TIER:**
- Model: Gemini 2.5 Flash
- Limits: 50 questions/day + 50 images/month
- Features: Everything + Images
- Cost: $10-15/month
- Price: $10-15/month

**This is much more profitable!** ✅

---

## 🚀 NEXT STEPS

1. **Confirm pricing model** (hybrid vs original)
2. **Get API keys** (I'll provide instructions)
3. **Implement system** (8-11 hours)
4. **Test thoroughly**
5. **Launch!**

**Ready to proceed?** 🎯

