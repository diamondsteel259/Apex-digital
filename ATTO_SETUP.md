# Atto Integration Setup

**Date:** 2025-12-14

---

## 🎯 FEATURES IMPLEMENTED

### **1. Atto Balance Management**
- `/attobalance` - Check your Atto balance
- Auto-creates wallet address if needed
- Shows balance in USD

### **2. Swap to Atto (Instant Withdrawal)**
- `/attoswap <amount>` - Swap wallet balance to Atto
- Instant conversion (no waiting)
- Can be withdrawn immediately

### **3. Pay with Atto (10% Cashback)**
- `/attopay <order_id>` - Pay for order with Atto
- **10% cashback** automatically added to wallet
- Instant payment processing

### **4. Withdraw Atto**
- `/attowithdraw <address> <amount>` - Withdraw to external address
- Instant withdrawals (Atto is feeless and fast)

### **5. Price Check**
- `/attoprice` - Check current Atto price from XT.com

---

## 🔧 CONFIGURATION

### **Environment Variables**

Add to `.env` file:

```bash
# Atto Node API (for balance/transaction queries)
ATTO_NODE_API=http://localhost:8080

# Atto Wallet API (for creating addresses)
ATTO_WALLET_API=http://localhost:8080
```

**Note:** If you're using a hosted Atto node, replace `localhost:8080` with your node URL.

---

## 📋 ATTO API SETUP

### **Option 1: Use Public Node (Recommended for Testing)**

You can use a public Atto node for testing. Check Atto documentation for public node URLs.

### **Option 2: Run Your Own Node**

Follow the [Atto Integration Guide](https://atto.cash/docs/integration) to set up:
- Historical Node (for full ledger)
- Wallet Server (for wallet operations)
- Work Server (for PoW computation)

**Default Ports:**
- `8080` - REST Interface
- `8081` - Health & Metrics
- `8082` - Node P2P

---

## 💰 PRICING API

The bot uses **XT.com API** to get Atto price:
- Endpoint: `https://api.xt.com/api/v1/ticker/price?symbol=ATTO_USDT`
- Updates automatically
- No API key required

---

## 🎁 CASHBACK SYSTEM

**How it works:**
1. User pays for order with Atto using `/attopay`
2. 10% cashback is calculated automatically
3. Cashback is added to user's wallet balance (in USD)
4. User can use cashback for future purchases

**Example:**
- Order: $100
- Pay with Atto: $100 worth of Atto
- Cashback: $10 added to wallet
- Total saved: $10

---

## 🔄 SWAP SYSTEM

**How it works:**
1. User has wallet balance (e.g., $50)
2. Uses `/attoswap 50` to convert to Atto
3. $50 deducted from wallet
4. Equivalent Atto added to Atto balance
5. Atto can be withdrawn instantly

**Benefits:**
- Instant withdrawal (no approval needed)
- Feeless transactions
- Fast confirmations (< 1 second)

---

## 📊 DATABASE

**New Tables:**
- `atto_wallets` - User Atto wallet addresses and balances
- `atto_transactions` - Transaction history
- `atto_swaps` - Swap history

**User Columns Added:**
- `atto_cashback_enabled` - Enable/disable cashback
- `atto_cashback_percent` - Cashback percentage (default 10%)

---

## ✅ READY TO USE

After adding API endpoints to `.env` and restarting the bot:

1. **Check balance:** `/attobalance`
2. **Swap funds:** `/attoswap 50`
3. **Pay with Atto:** `/attopay <order_id>`
4. **Withdraw:** `/attowithdraw atto://... 50`

---

**All features are implemented and ready!** 🚀

