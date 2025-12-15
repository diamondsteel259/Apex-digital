# Atto Wallet System - How It Works

**Date:** 2025-12-14

---

## 🎯 HOW IT WORKS (UPDATED DESIGN)

### **Main Concept:**
- **ONE main wallet** for the bot (you control this)
- Users **deposit Atto** to the main wallet address
- Bot **tracks each user's balance** in the database
- Users can **withdraw** from their tracked balance

---

## 💰 DEPOSIT FLOW

### **Step 1: User Gets Deposit Address**
- User runs `/attodeposit` or `/attobalance`
- Bot shows: **"Send Atto to: `atto://YOUR_MAIN_WALLET_ADDRESS`"**
- Bot also shows a **unique deposit memo/ID** for tracking

### **Step 2: User Sends Atto**
- User sends Atto from their external wallet to your main wallet
- They include the memo/ID in the transaction

### **Step 3: Bot Detects Deposit**
- Bot monitors the main wallet for incoming transactions
- When deposit detected:
  - ✅ Add 10% cashback automatically
  - ✅ Update user's balance in database
  - ✅ Notify user

**Example:**
- User deposits: 100 ATTO
- Bot adds: 10 ATTO cashback (10%)
- User balance: 110 ATTO

---

## 🛒 PAYMENT FLOW

### **User Pays with Atto:**
1. User runs `/attopay <order_id>`
2. Bot asks: **"Apply 2.5% discount or cashback?"**
   - Option 1: Discount (reduce order price by 2.5%)
   - Option 2: Cashback (add 2.5% to wallet)
3. User chooses
4. Payment processed from their tracked balance
5. Discount/cashback applied

**Example:**
- Order: $100
- User chooses: **Discount**
- Price: $97.50 (2.5% off)
- User pays: 97.50 worth of Atto

**OR:**
- Order: $100
- User chooses: **Cashback**
- Price: $100
- User pays: $100 worth of Atto
- Cashback: $2.50 added to wallet

---

## 💸 WITHDRAWAL FLOW

### **User Withdraws:**
1. User runs `/attowithdraw <amount> <address>`
2. Bot checks:
   - ✅ User has enough balance
   - ✅ Address is valid
3. Bot sends Atto from **main wallet** to user's address
4. Deduct from user's tracked balance
5. Transaction logged

**Example:**
- User balance: 110 ATTO
- User withdraws: 50 ATTO to `atto://user_address`
- Bot sends: 50 ATTO from main wallet
- User balance: 60 ATTO

---

## 🔧 WHAT YOU NEED TO SET UP

### **1. Main Wallet Address**
- Create ONE Atto wallet (you control this)
- This is where ALL deposits go
- This is where withdrawals come from

### **2. Atto Node API**
- Need access to Atto node API to:
  - Monitor incoming transactions
  - Send outgoing transactions
  - Check balances

### **3. Transaction Monitoring**
- Bot needs to check main wallet for new deposits
- Can use:
  - Webhook (if Atto supports it)
  - Polling (check every X seconds)
  - Atto Explorer API

---

## 📊 DATABASE STRUCTURE

### **User Balances:**
```
atto_user_balances:
  - user_discord_id
  - balance_raw (their tracked balance)
  - total_deposited_raw
  - total_withdrawn_raw
```

### **Transactions:**
```
atto_transactions:
  - user_discord_id
  - type (deposit/withdrawal/payment)
  - amount_raw
  - transaction_hash
  - memo (for deposit tracking)
```

---

## ⚙️ CONFIGURATION

### **Environment Variables:**
```bash
# Your main wallet address (where all deposits go)
ATTO_MAIN_WALLET_ADDRESS=atto://your_main_wallet_address_here

# Atto Node API (for sending/receiving)
ATTO_NODE_API=http://localhost:8080

# Deposit monitoring (how often to check)
ATTO_DEPOSIT_CHECK_INTERVAL=30  # seconds
```

---

## 🎁 CASHBACK SYSTEM

### **Deposit Cashback:**
- **10% automatic** on all deposits
- Added immediately when deposit detected

### **Payment Cashback/Discount:**
- **2.5% user choice:**
  - **Discount:** Reduce order price
  - **Cashback:** Add to wallet balance

---

## 🔄 CURRENT vs NEW SYSTEM

### **OLD (Current):**
- Each user gets their own address ❌
- Users manage their own wallets ❌
- No deposit tracking ❌

### **NEW (What You Want):**
- One main wallet ✅
- Bot tracks all balances ✅
- Deposit monitoring ✅
- 10% deposit cashback ✅
- 2.5% payment discount/cashback ✅

---

## 🚀 IMPLEMENTATION STATUS

**Need to implement:**
1. ✅ Main wallet address (config)
2. ✅ Deposit monitoring system
3. ✅ Transaction memo/ID system
4. ✅ 10% deposit cashback
5. ✅ 2.5% payment discount/cashback choice
6. ✅ Withdrawal from main wallet

**Ready to code!** Let me know if you want me to implement this now.

