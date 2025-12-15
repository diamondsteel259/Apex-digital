# 🔗 Multi-Node Atto Integration

## ✅ What's Been Implemented

Your bot now supports **multiple Atto nodes** with automatic failover for improved:
- **🔒 Security**: Redundancy prevents single point of failure
- **⚡ Reliability**: If one node goes down, automatically uses another
- **📊 Load Distribution**: Can distribute requests across nodes
- **🛡️ Resilience**: Better uptime even if individual nodes have issues

## 📋 How It Works

1. **Node Manager**: Automatically manages multiple node connections
2. **Health Checking**: Monitors node health every 60 seconds
3. **Automatic Failover**: If a node fails, tries the next one automatically
4. **Smart Retry**: Only retries on server errors (5xx), not client errors (4xx)

## 🔧 Configuration

### Single Node (Default)
```env
ATTO_NODE_API=http://localhost:8080
```

### Multiple Nodes (Recommended)
```env
ATTO_NODE_API=https://node-1.live.core.atto.cash,https://node-2.live.core.atto.cash,https://node-3.live.core.atto.cash
```

### From Your Screenshot
Based on the nodes you found, you could use:
```env
ATTO_NODE_API=https://node-cautious-2.live.core.atto.cash,https://node-test.live.core.atto.cash,https://node-1.live.core.atto.cash,https://node-conservative-3.live.core.atto.cash,https://node-2.live.core.atto.cash
```

**Note**: You'll need to convert the WebSocket URLs (`wss://`) to HTTP URLs (`https://`) and add port `:8080` if needed, or check the node documentation for the REST API endpoint.

## 🎯 Benefits

1. **Redundancy**: If one node is down, others handle requests
2. **Security**: Less risk if one node is compromised
3. **Performance**: Can distribute load across nodes
4. **Reliability**: Better uptime for your bot

## 📝 Example Node URLs

From the Atto documentation, nodes typically expose:
- **Port 8080**: REST API (what we use)
- **Port 8081**: Health/metrics
- **Port 8082**: WebSocket (node-to-node)

So if you see `wss://node-1.live.core.atto.cash`, try:
- `https://node-1.live.core.atto.cash:8080` (REST API)
- Or check the node's documentation for the exact REST endpoint

## 🚀 Next Steps

1. **Update `.env`** with your node URLs (comma-separated)
2. **Restart the bot** to load the new configuration
3. **Monitor logs** to see which nodes are being used
4. **Test** by making a few Atto transactions

## 📊 Monitoring

The bot logs:
- Which node is being used for each request
- Node health status
- Failover events (when switching to a different node)
- Errors if all nodes fail

Check logs with:
```bash
tail -f bot.log | grep -i "atto.*node"
```

## ⚠️ Important Notes

1. **Node URLs**: Make sure you're using the REST API endpoint (usually port 8080), not WebSocket
2. **HTTPS**: Use `https://` for public nodes, `http://` for local nodes
3. **Testing**: Test with 2-3 nodes first, then add more if needed
4. **Rate Limits**: Some public nodes may have rate limits - using multiple nodes helps distribute load

---

**Status**: ✅ Multi-node support is now active! Just update your `.env` file and restart the bot.
