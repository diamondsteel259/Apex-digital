# Environment Variables Template (.env)

Copy this template to create your `.env` file. Replace all placeholder values with your actual credentials.

```env
# ============================================
# DISCORD BOT CONFIGURATION
# ============================================
DISCORD_TOKEN=your_discord_bot_token_here

# ============================================
# ATTO CRYPTOCURRENCY INTEGRATION
# ============================================
# Main wallet address (where all deposits go)
# Format: atto://your_wallet_address
ATTO_MAIN_WALLET_ADDRESS=atto://your_main_wallet_address

# Atto Node API endpoint(s) - Multiple nodes for redundancy and security
# Format: Comma-separated list of node URLs
# Examples:
#   Single node: http://localhost:8080
#   Multiple nodes: https://node-1.live.core.atto.cash,https://node-2.live.core.atto.cash,https://node-3.live.core.atto.cash
# The bot will automatically failover to the next node if one fails
# Recommended: Use 2-3 nodes for best reliability
ATTO_NODE_API=http://localhost:8080

# Deposit check interval (seconds)
# How often to check for new deposits (default: 30)
ATTO_DEPOSIT_CHECK_INTERVAL=30

# ============================================
# AI SUPPORT SYSTEM
# ============================================
# Gemini API Key (for Free and Ultra tiers)
# Get from: https://makersuite.google.com/app/apikey
GEMINI_API_KEY=your_gemini_api_key_here

# Groq API Key (for Premium tier)
# Get from: https://console.groq.com/keys
GROQ_API_KEY=your_groq_api_key_here

# ============================================
# CRYPTOCURRENCY WALLETS
# ============================================
# Bitcoin wallet address
BTC_WALLET_ADDRESS=your_bitcoin_address_here

# Ethereum wallet address
ETH_WALLET_ADDRESS=your_ethereum_address_here

# Solana wallet address
SOL_WALLET_ADDRESS=your_solana_address_here

# TON (The Open Network) wallet address
TON_WALLET_ADDRESS=your_ton_address_here

# ============================================
# PAYMENT GATEWAYS
# ============================================
# Binance Pay Merchant ID
# Get from: https://merchant.binance.com/
BINANCE_PAY_ID=your_binance_pay_id_here

# PayPal email address
PAYPAL_EMAIL=your_paypal@email.com

# Stripe API Keys
# Get from: https://dashboard.stripe.com/apikeys
STRIPE_PUBLIC_KEY=pk_live_your_stripe_public_key
STRIPE_SECRET_KEY=sk_live_your_stripe_secret_key

# ============================================
# BLOCKCHAIN API KEYS (Optional)
# ============================================
# Etherscan API Key (for Ethereum TX verification)
# Get from: https://etherscan.io/apis
ETHERSCAN_API_KEY=your_etherscan_api_key_here

# ============================================
# DATABASE CONFIGURATION
# ============================================
# Database connection timeout (seconds)
DB_CONNECT_TIMEOUT=5.0

# ============================================
# TIPBOT CONFIGURATION
# ============================================
# Tipbot Bot IDs (update in cogs/tipbot_monitoring.py)
# Find bot IDs by right-clicking bot in Discord > Copy ID
# Tip.cc Bot ID: (update in code)
# CryptoJar Bot ID: (update in code)
# Gemma Bot ID: (update in code)
# Seto Chan Bot ID: (update in code)
```

---

## 📋 Setup Instructions

### **1. Discord Bot Token**
1. Go to https://discord.com/developers/applications
2. Select your bot application
3. Go to "Bot" section
4. Copy the token

### **2. Atto Node Information**
- **If running your own node:**
  - Install Atto node software
  - Default API endpoint: `http://localhost:8080`
  - See: https://atto.cash/docs

- **If using public node:**
  - Use: `https://node.atto.cash`
  - Or find public node endpoints in Atto community

- **Main Wallet Address:**
  - Create wallet using Atto wallet software
  - Format: `atto://your_address`
  - Use `/attosetup` command after bot starts to set it

### **3. AI API Keys**
- **Gemini:** https://makersuite.google.com/app/apikey
- **Groq:** https://console.groq.com/keys

### **4. Payment Gateways**
- **Binance Pay:** Register at https://merchant.binance.com/
- **PayPal:** Use your existing PayPal account email
- **Stripe:** Get keys from https://dashboard.stripe.com/apikeys

### **5. Crypto Wallets**
- Generate addresses for each network
- Use main wallet addresses (memo system handles tracking)

### **6. Tipbot IDs**
- Right-click tipbot in Discord
- Select "Copy ID" (Developer Mode must be enabled)
- Update in `cogs/tipbot_monitoring.py`:
  ```python
  TIPBOT_IDS = {
      "tip.cc": YOUR_BOT_ID_HERE,
      "cryptojar": YOUR_BOT_ID_HERE,
      "gemma": YOUR_BOT_ID_HERE,
      "seto": YOUR_BOT_ID_HERE,
  }
  ```

---

## 🔒 Security Notes

- **NEVER commit `.env` file to Git**
- Keep all API keys secret
- Rotate keys if compromised
- Use environment variables in production
- Restrict file permissions: `chmod 600 .env`

---

## ✅ Verification

After setting up, verify:
- [ ] Discord bot token is valid
- [ ] Atto node is accessible
- [ ] AI API keys work
- [ ] Payment gateways configured
- [ ] Crypto wallets have addresses
- [ ] Tipbot IDs updated in code

