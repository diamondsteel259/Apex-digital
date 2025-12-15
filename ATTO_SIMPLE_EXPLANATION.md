# 🎯 ATTO WALLET - SIMPLE EXPLANATION

**How it works in plain English:**

---

## 💰 THE SYSTEM

### **ONE Main Wallet (Yours)**
- You have ONE Atto wallet address
- ALL users deposit to THIS address
- You control this wallet (private keys)

### **Database Tracking**
- Bot tracks each user's balance in database
- When user deposits 100 ATTO → Bot records: "User has 100 ATTO"
- When user pays 50 ATTO → Bot records: "User now has 50 ATTO"
- **No individual wallets for users** - just database records

---

## 📥 DEPOSIT FLOW

1. **User runs `/attodeposit`**
   - Bot shows: "Send Atto to: `atto://YOUR_MAIN_ADDRESS`"
   - Bot shows: "Include memo: `USER_123456789`" (their Discord ID)

2. **User sends Atto**
   - From their external wallet → Your main wallet
   - Includes memo: `USER_123456789`

3. **Bot detects deposit**
   - Monitors main wallet for new transactions
   - Sees memo `USER_123456789` → Knows it's for that user
   - **Adds 10% cashback automatically**
   - Updates database: User balance = deposit + 10%

**Example:**
- User deposits: 100 ATTO
- Bot adds: 10 ATTO cashback (10%)
- User balance in database: 110 ATTO

---

## 🛒 PAYMENT FLOW

1. **User runs `/attopay <order_id>`**
   - Order price: $100

2. **Bot asks: "Apply 2.5% discount or cashback?"**
   - **Option 1: Discount** → Order becomes $97.50
   - **Option 2: Cashback** → Order stays $100, but $2.50 added to wallet

3. **User chooses**
   - If discount: Pays 97.50 worth of Atto
   - If cashback: Pays 100 worth of Atto, gets $2.50 back

4. **Bot deducts from database**
   - Checks: Does user have enough balance?
   - Deducts: User balance - payment amount
   - Updates database

---

## 💸 WITHDRAWAL FLOW

1. **User runs `/attowithdraw <amount> <address>`**
   - Example: `/attowithdraw 50 atto://user_address`

2. **Bot checks:**
   - Does user have 50 ATTO in database? ✅
   - Is address valid? ✅

3. **Bot sends from YOUR main wallet**
   - Bot sends 50 ATTO from YOUR wallet to user's address
   - Deducts 50 ATTO from user's database balance
   - Logs transaction

**Example:**
- User balance: 110 ATTO (in database)
- User withdraws: 50 ATTO to `atto://their_address`
- Bot sends: 50 ATTO from YOUR main wallet
- User balance: 60 ATTO (in database)

---

## 🔧 WHAT YOU NEED

### **1. Main Wallet Address**
```
ATTO_MAIN_WALLET_ADDRESS=atto://your_wallet_address_here
```
- Create ONE Atto wallet
- This is where ALL deposits go
- This is where withdrawals come from

### **2. Atto Node API**
```
ATTO_NODE_API=http://localhost:8080
```
- To monitor deposits
- To send withdrawals
- To check balances

### **3. Deposit Monitoring**
- Bot checks main wallet every 30 seconds
- Looks for new transactions with memos
- Matches memo to user ID
- Adds balance + cashback

---

## 📊 DATABASE STRUCTURE

**User Balances:**
```
atto_user_balances:
  - user_discord_id: 123456789
  - balance_raw: "1100000000000000000000000000000" (110 ATTO in raw units)
  - total_deposited_raw: "1000000000000000000000000000000" (100 ATTO)
  - deposit_memo: "USER_123456789"
```

**Transactions:**
```
atto_transactions:
  - user_discord_id: 123456789
  - type: "deposit"
  - amount_raw: "1000000000000000000000000000000"
  - cashback_raw: "100000000000000000000000000000" (10 ATTO)
  - transaction_hash: "abc123..."
  - memo: "USER_123456789"
```

---

## 🎁 CASHBACK SYSTEM

### **Deposit Cashback: 10%**
- User deposits 100 ATTO
- Bot adds 10 ATTO automatically
- User gets 110 ATTO total

### **Payment Discount/Cashback: 2.5%**
- User chooses:
  - **Discount:** Pay less (2.5% off)
  - **Cashback:** Get money back (2.5% added to wallet)

---

## ✅ SUMMARY

**OLD System (What I built):**
- Each user gets own wallet ❌
- Users manage their own addresses ❌

**NEW System (What You Want):**
- ONE main wallet ✅
- Bot tracks balances in database ✅
- 10% deposit cashback ✅
- 2.5% payment discount/cashback ✅
- Withdrawals from main wallet ✅

**Ready to implement!** 🚀

