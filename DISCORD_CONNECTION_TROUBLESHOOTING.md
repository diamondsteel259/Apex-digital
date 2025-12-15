# 🔧 Discord Connection Troubleshooting

## ❌ Error: `Temporary failure in name resolution` for `gateway.discord.gg`

This error means your VPS **cannot connect to Discord** due to network/DNS issues.

---

## 🔍 Quick Diagnosis

Run these commands to diagnose:

```bash
# Check internet connectivity
ping -c 3 8.8.8.8

# Check DNS resolution
nslookup gateway.discord.gg

# Check if Discord is reachable
curl -I https://discord.com

# Check network interface
ip addr show

# Check DNS servers
cat /etc/resolv.conf
```

---

## ✅ Solutions

### **Solution 1: Fix DNS Resolution** (Most Common)

```bash
# Edit DNS configuration
sudo nano /etc/resolv.conf
```

Add these lines:
```
nameserver 8.8.8.8
nameserver 8.8.4.4
nameserver 1.1.1.1
```

**Or use systemd-resolved:**
```bash
sudo systemd-resolve --status
sudo systemctl restart systemd-resolved
```

**Or configure NetworkManager:**
```bash
sudo nmcli connection modify "your-connection-name" ipv4.dns "8.8.8.8 8.8.4.4"
sudo nmcli connection down "your-connection-name"
sudo nmcli connection up "your-connection-name"
```

---

### **Solution 2: Check Firewall**

```bash
# Check if firewall is blocking
sudo ufw status
sudo iptables -L -n

# If firewall is active, allow outbound connections
sudo ufw allow out 443/tcp
sudo ufw allow out 80/tcp
```

---

### **Solution 3: Check Network Interface**

```bash
# Check if network is up
ip link show

# Restart network (Ubuntu/Debian)
sudo systemctl restart networking

# Or restart NetworkManager
sudo systemctl restart NetworkManager
```

---

### **Solution 4: Check VPS Provider Settings**

Some VPS providers block outbound connections by default:

1. **Check VPS Control Panel:**
   - Look for "Firewall" or "Security Groups"
   - Ensure outbound traffic is allowed
   - Check for any IP restrictions

2. **Contact VPS Support:**
   - Ask if Discord is blocked
   - Request to whitelist `gateway.discord.gg` and `discord.com`

---

### **Solution 5: Use Different DNS Provider**

```bash
# Install and use Cloudflare DNS
sudo apt update
sudo apt install -y resolvconf

# Edit resolvconf config
sudo nano /etc/resolvconf/resolv.conf.d/head
```

Add:
```
nameserver 1.1.1.1
nameserver 1.0.0.1
```

Then:
```bash
sudo resolvconf -u
```

---

### **Solution 6: Check Proxy Settings**

If you're behind a proxy:

```bash
# Check environment variables
env | grep -i proxy

# If proxy is set but not needed, unset it
unset HTTP_PROXY
unset HTTPS_PROXY
unset http_proxy
unset https_proxy
```

---

## 🧪 Test After Fix

```bash
# Test DNS
nslookup gateway.discord.gg

# Test connectivity
curl -I https://discord.com

# If both work, restart bot
pkill -f "python.*bot.py"
cd ~/Apex-digital
source venv/bin/activate
nohup python3 bot.py > bot.log 2>&1 &
tail -f bot.log
```

---

## 📋 Common VPS Provider Issues

### **Contabo:**
- Check "Firewall" in control panel
- Ensure outbound HTTPS (443) is allowed

### **DigitalOcean:**
- Check "Networking" → "Firewalls"
- Ensure outbound rules allow HTTPS

### **AWS EC2:**
- Check "Security Groups"
- Ensure outbound HTTPS (443) is allowed

### **Hetzner:**
- Check "Firewall" in Cloud Console
- Ensure outbound traffic is allowed

---

## 🆘 Still Not Working?

1. **Check VPS Provider Status:**
   - Some providers have network outages
   - Check their status page

2. **Try Different Network:**
   - Test from your local machine
   - If it works locally, it's a VPS network issue

3. **Contact VPS Support:**
   - Provide error message
   - Ask about Discord connectivity
   - Request firewall/network review

---

## ✅ Expected Behavior After Fix

Once fixed, you should see:
```
[INFO] Logged in as Apex Core#0566 (ID: ...)
[INFO] Apex Core is ready!
```

**No more DNS errors!** 🎉

