# Atto Node Setup Guide

## 📚 What is an Atto Node?

An Atto node is a server that runs the Atto blockchain software. It allows you to:
- Monitor transactions on the Atto network
- Send and receive Atto transactions
- Query account balances
- Process deposits automatically

---

## 🚀 Setting Up Your Own Node

### **Option 1: Run Your Own Node (Recommended for Production)**

1. **Download Atto Node Software**
   - Visit: https://atto.cash/docs
   - Download the node software for your OS
   - Follow installation instructions

2. **Configure Node**
   - Default API endpoint: `http://localhost:8080`
   - Configure firewall to allow connections
   - Set up SSL if using HTTPS

3. **Start Node**
   ```bash
   # Example (adjust for your OS)
   ./atto-node --api-port 8080
   ```

4. **Verify Node is Running**
   ```bash
   curl http://localhost:8080/health
   ```

5. **Update .env**
   ```env
   ATTO_NODE_API=http://localhost:8080
   ```

---

### **Option 2: Use Public Node (Quick Start)**

1. **Find Public Node**
   - Check Atto community Discord/Telegram
   - Look for public node endpoints
   - Example: `https://node.atto.cash`

2. **Update .env**
   ```env
   ATTO_NODE_API=https://node.atto.cash
   ```

**⚠️ Note:** Public nodes may have rate limits and are less secure. Use your own node for production.

---

## 🔑 Main Wallet Address

### **Creating a Wallet**

1. **Using Atto Wallet Software**
   - Download wallet from https://atto.cash
   - Create new wallet
   - Copy address (format: `atto://your_address`)

2. **Using Node API**
   - Use node API to generate addresses
   - Store private key securely

3. **Set in Bot**
   - Use `/attosetup` command after bot starts
   - Or set in `.env` as `ATTO_MAIN_WALLET_ADDRESS`

---

## 📡 Node API Endpoints

The bot uses these endpoints:

- `GET /account/balance?address={address}` - Get balance
- `GET /account/history?address={address}` - Get transaction history
- `POST /accounts/{address}/send` - Send transaction
- `GET /health` - Health check

---

## 🔧 Configuration

### **Environment Variables**

```env
# Main wallet address (where deposits go)
ATTO_MAIN_WALLET_ADDRESS=atto://your_address

# Node API endpoint
ATTO_NODE_API=http://localhost:8080

# Deposit check interval (seconds)
ATTO_DEPOSIT_CHECK_INTERVAL=30
```

### **Bot Command**

After bot starts, use:
```
/attosetup address:atto://your_address
```

---

## 🛠️ Troubleshooting

### **Node Not Responding**
- Check if node is running
- Verify firewall settings
- Check node logs for errors

### **Cannot Connect to Node**
- Verify `ATTO_NODE_API` in `.env`
- Test with `curl http://localhost:8080/health`
- Check network connectivity

### **Deposits Not Detected**
- Verify main wallet address is set
- Check deposit monitoring task is running
- Review bot logs for errors

---

## 📖 Additional Resources

- **Atto Documentation:** https://atto.cash/docs
- **Atto Integration Guide:** https://atto.cash/docs/integration
- **Node Setup:** https://atto.cash/docs/node-setup

---

## ✅ Verification Checklist

- [ ] Node is running and accessible
- [ ] API endpoint is correct
- [ ] Main wallet address is set
- [ ] Deposit monitoring is active
- [ ] Test deposit works
- [ ] Cashback is credited correctly

