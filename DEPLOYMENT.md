# Deployment Guide for Apex-digital Discord Bot

This guide details the steps to deploy the Apex-digital bot in a production environment.

## Prerequisites

-   **Operating System**: Ubuntu 20.04 LTS or newer (recommended).
-   **Python**: Version 3.10 or higher.
-   **Discord Application**: A created application in the [Discord Developer Portal](https://discord.com/developers/applications) with a Bot Token.

## 1. System Setup

### Install System Dependencies
Update your package list and install Python and virtualenv:

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git
```

### Clone the Repository
Clone the bot code to your server (e.g., `/opt/apex-bot` or your home directory).

## 2. Application Setup

### Create Virtual Environment
It is best practice to run the bot in an isolated environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Install Python Dependencies
Install the required libraries:

```bash
pip install -r requirements.txt
```

If you plan to use **S3 storage** for transcripts or **chat-exporter** for nicer logs:

```bash
pip install -r requirements-optional.txt
```

## 3. Configuration

### Main Configuration
1.  Copy the example config:
    ```bash
    cp config.example.json config.json
    ```
2.  Edit `config.json` with your specific settings:
    -   **guild_ids**: The ID(s) of the server(s) where the bot will run.
    -   **role_ids**: IDs for Admin and Client roles.
    -   **ticket_categories**: Category IDs for ticket channels.
    -   **logging_channels**: Channel IDs for logs.

### Payments Configuration
1.  Create the directory if it doesn't exist:
    ```bash
    mkdir -p config
    ```
2.  Create `config/payments.json` (you can base this on existing structure or documentation). This file defines payment methods and templates.

### Environment Variables
Create a `.env` file in the project root to store secrets. This keeps sensitive data out of `config.json`.

```bash
# Required
DISCORD_TOKEN=your_actual_bot_token_here
CONFIG_PATH=config.json

# Optional: Database Tuning
DB_CONNECT_TIMEOUT=10.0

# Optional: S3 Storage (for transcripts)
TRANSCRIPT_STORAGE_TYPE=s3
S3_BUCKET=your-bucket-name
S3_REGION=us-east-1
S3_ACCESS_KEY=your-access-key
S3_SECRET_KEY=your-secret-key
```

## 4. Running the Bot

### Manual Start
To test the bot, run it directly:

```bash
python3 bot.py
```

### Production Service (Systemd)
For 24/7 uptime, use the included systemd service file.

1.  Edit `apex-core.service` to match your paths and user:
    -   Update `User=engine` to your system user (e.g., `User=ubuntu`).
    -   Update `WorkingDirectory` and `ExecStart` paths.
2.  Install the service:
    ```bash
    sudo cp apex-core.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable apex-core
    sudo systemctl start apex-core
    ```
3.  Check status:
    ```bash
    sudo systemctl status apex-core
    ```

## 5. Troubleshooting

-   **Database Locks**: If the bot crashes and fails to restart with database errors, ensure no other process is accessing `apex_core.db`.
-   **Missing Permissions**: Ensure the bot role in Discord has `Administrator` permissions or specific permissions for:
    -   Managing Channels (creating ticket channels).
    -   Managing Roles (assigning roles).
    -   Sending Messages/Embeds.
-   **Intents**: In the Discord Developer Portal, under the **Bot** tab, ensure **Message Content Intent** and **Server Members Intent** are enabled.

## 6. Maintenance

-   **Backups**: Regularly backup `apex_core.db` and the `config/` directory.
-   **Logs**: Check `logs/` directory or `journalctl -u apex-core` for runtime logs.
