# VPS RDP Setup Guide - Connect and Install Discord

## ✅ What You've Already Done

From your terminal output, I can see:
- ✅ XRDP installed and enabled
- ✅ System updated
- ✅ Ready for RDP connection

---

## Step 1: Find Your Server IP Address

**On your VPS (where you just ran those commands):**
```bash
# Get your server's IP address
ip addr show | grep "inet " | grep -v 127.0.0.1

# Or simpler:
hostname -I
```

**You'll see something like:** `123.45.67.89` - **This is your server IP!**

---

## Step 2: Connect via RDP from Your PC

### On Windows:

1. **Open Remote Desktop Connection:**
   - Press `Win + R`
   - Type: `mstsc`
   - Press Enter

2. **Enter Server Details:**
   - **Computer:** `your-server-ip` (the IP you got from Step 1)
   - **Username:** `root` (or your username)
   - Click **"Connect"**

3. **Enter Password:**
   - Enter your root password (or user password)
   - Click **"OK"**

4. **Accept Certificate (if prompted):**
   - Click **"Yes"** if asked about certificate

**You should now see a Linux desktop!**

---

### On Mac:

1. **Download Microsoft Remote Desktop:**
   - From Mac App Store (free)
   - Or download from Microsoft website

2. **Add Connection:**
   - Click **"+"** → **"Add PC"**
   - **PC name:** `your-server-ip`
   - **User account:** `root` (or your username)
   - Click **"Add"**

3. **Connect:**
   - Double-click the connection
   - Enter password when prompted

---

## Step 3: Install Desktop Environment (If Not Already Installed)

**In your RDP session, open terminal and run:**

```bash
# Update system
apt update && apt upgrade -y

# Install XFCE desktop (lightweight, works great with RDP)
apt install -y xfce4 xfce4-goodies

# Install additional useful packages
apt install -y firefox chromium-browser wget curl

# Configure XRDP to use XFCE
echo "xfce4-session" > /root/.xsession

# Restart XRDP service
systemctl restart xrdp
```

**If you get disconnected, reconnect via RDP and you should see the desktop!**

---

## Step 4: Install Discord

### Option A: Discord in Browser (Easiest) ⭐ RECOMMENDED

**In your RDP session:**

1. **Open Firefox:**
   - Click Applications menu → Internet → Firefox
   - Or type `firefox` in terminal

2. **Go to Discord:**
   - Navigate to: `https://discord.com`
   - Login with your Discord account
   - Use Discord web app (works perfectly!)

**Pros:**
- ✅ No installation needed
- ✅ Always up-to-date
- ✅ Works immediately
- ✅ No dependencies

---

### Option B: Discord Desktop App

**In your RDP session terminal:**

```bash
# Download Discord .deb package
wget -O discord.deb "https://discord.com/api/download?platform=linux&format=deb"

# Install Discord
apt install -y ./discord.deb

# Launch Discord
discord
```

**Or install via snap:**
```bash
# Install snapd if not installed
apt install -y snapd

# Install Discord via snap
snap install discord

# Launch Discord
discord
```

---

## Step 5: Install Your Bot on the VPS

**In your RDP session:**

### 5.1. Open Terminal
- Press `Ctrl + Alt + T` or click Terminal icon

### 5.2. Install Prerequisites
```bash
# Update system
apt update && apt upgrade -y

# Install Python and Git
apt install -y python3 python3-pip python3-venv git

# Install build tools (for some Python packages)
apt install -y build-essential libffi-dev python3-dev
```

### 5.3. Clone Your Bot Repository
```bash
# Navigate to home directory
cd ~

# Clone your bot (replace with your repo URL)
git clone https://github.com/yourusername/Apex-digital.git
# OR upload your bot files via SFTP/SCP

cd Apex-digital
```

### 5.4. Set Up Virtual Environment
```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 5.5. Configure Bot
```bash
# Copy example config
cp config.example.json config.json

# Edit config with your settings
nano config.json
# OR use the file manager in RDP to edit with a text editor
```

**Edit `config.json` with:**
- Your Discord bot token
- Your server (guild) ID
- Role IDs
- Channel IDs

### 5.6. Run Bot
```bash
# Make sure venv is activated
source venv/bin/activate

# Run bot
python3 bot.py
```

**Or run in background:**
```bash
# Run in background
nohup python3 bot.py > bot.log 2>&1 &

# View logs
tail -f bot.log
```

---

## Step 6: Set Up Bot as System Service (Optional but Recommended)

**This keeps the bot running even if you disconnect from RDP:**

```bash
# Create systemd service file
nano /etc/systemd/system/apex-bot.service
```

**Add this content:**
```ini
[Unit]
Description=Apex Digital Discord Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/Apex-digital
Environment="PATH=/root/Apex-digital/venv/bin"
ExecStart=/root/Apex-digital/venv/bin/python3 /root/Apex-digital/bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Enable and start service:**
```bash
# Reload systemd
systemctl daemon-reload

# Enable bot to start on boot
systemctl enable apex-bot.service

# Start bot
systemctl start apex-bot.service

# Check status
systemctl status apex-bot.service

# View logs
journalctl -u apex-bot.service -f
```

---

## Troubleshooting

### Can't Connect via RDP?

1. **Check if XRDP is running:**
   ```bash
   systemctl status xrdp
   ```

2. **Check firewall:**
   ```bash
   # Allow RDP port (3389)
   ufw allow 3389/tcp
   ufw reload
   ```

3. **Check if port is listening:**
   ```bash
   netstat -tlnp | grep 3389
   ```

### Desktop Not Showing?

1. **Reinstall desktop:**
   ```bash
   apt install --reinstall xfce4 xfce4-goodies
   ```

2. **Reset XRDP config:**
   ```bash
   echo "xfce4-session" > /root/.xsession
   systemctl restart xrdp
   ```

### Discord Not Working?

1. **Use browser version** (easiest solution)
2. **Check if desktop environment is installed**
3. **Try installing via snap instead of .deb**

---

## Quick Reference Commands

```bash
# Check bot status
systemctl status apex-bot.service

# View bot logs
journalctl -u apex-bot.service -f

# Restart bot
systemctl restart apex-bot.service

# Stop bot
systemctl stop apex-bot.service

# Check if bot is running
ps aux | grep "python.*bot.py"
```

---

## Next Steps After Setup

1. ✅ Connect via RDP
2. ✅ Install desktop environment
3. ✅ Install Discord (browser or app)
4. ✅ Upload/Clone bot files
5. ✅ Configure bot
6. ✅ Run bot
7. ✅ Set up as system service
8. ✅ Test in Discord!

---

## Summary

**To connect:**
1. Get your server IP: `hostname -I`
2. Open Remote Desktop Connection on your PC
3. Enter IP and connect
4. Install desktop: `apt install -y xfce4 xfce4-goodies`
5. Use Discord in browser or install desktop app
6. Set up and run your bot!

**You're all set!** 🚀

