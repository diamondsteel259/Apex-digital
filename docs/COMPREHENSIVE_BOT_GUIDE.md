# Apex Core Comprehensive Bot Guide
_A single source of truth for administrators, operators, and developers working on the Apex Core Discord bot._

> This guide consolidates every deployment, configuration, feature, and troubleshooting workflow into a single reference. Use it alongside the in-repo documents (README.md, QUICK_START_UBUNTU.md, DOCUMENTATION_INDEX.md, etc.) for deep dives.

## Table of Contents
1. [Overview](#1-overview)
2. [Ubuntu Deployment Guide](#2-ubuntu-deployment-guide-step-by-step)
3. [Configuration Guide](#3-configuration-guide)
4. [Features & Usage Guide](#4-features--usage-guide)
5. [How to Customize & Change Things](#5-how-to-customize--change-things)
6. [Architecture & Code Structure](#6-architecture--code-structure)
7. [Admin Commands Reference](#7-admin-commands-reference)
8. [Troubleshooting & Common Issues](#8-troubleshooting--common-issues)
9. [Best Practices & Security](#9-best-practices--security)
10. [Quick Start Checklist](#10-quick-start-checklist)

---

## 1. Overview

### 1.1 What the Apex Core bot does
Apex Core is a full-stack commerce, support, and automation bot built on top of Discord.py 2.x. It powers digital storefronts, automated ticketing, VIP/achievement tiers, referrals, refunds, reviews, and server provisioning around a single SQLite database. The bot focuses on:
- **Self-serve storefronts** with multi-level dropdown browsing.
- **Automated wallet and payment orchestration** with ledgers, cooldowns, and audit logging.
- **Lifecycle automation** for tickets, refunds, warranty reminders, transcripts, and setup flows.
- **Persistent configuration + infrastructure** via atomic config writes, session persistence, and a full server blueprint.

### 1.2 Key features & capabilities
- **Product Storefront**: Category -> sub-category -> product flows, inline price quotes, and confirmation modals.
- **Shopping & Checkout**: Atomic `purchase_product` calls guarantee wallet + order integrity and provide in-channel payment instructions.
- **Wallet System**: `/deposit`, `/balance`, `/addbalance`, `/transactions`, and ledger-backed credits/debits with VIP role handling.
- **Logistics Automation**: Auto ticket closure, HTML transcripts (chat-exporter), refund workflows, referral cashbacks, and warranty reminders.
- **Setup Wizard**: `/setup` slash command and legacy `!setup` text command deploy storefront/support/help/review panels or provision entire servers via blueprints.
- **Server Infrastructure Provisioning**: `apex_core/server_blueprint.py` defines roles, categories, channels, overwrites, and logging destinations.
- **Config Persistence**: Atomic `ConfigWriter`, timestamped backups, runtime reloads, and per-section update helpers.
- **Security & Auditability**: Rate limits, financial cooldowns, role-gated commands, audit embeds, and complete ledger trails.

### 1.3 Prerequisites & requirements
| Requirement | Details | Why it matters |
| --- | --- | --- |
| **Operating System** | Ubuntu 22.04 LTS or newer (tested on 24.04) | Matches systemd service, package commands, and E2E test reports |
| **Python** | 3.11+ (project currently ships with 3.12-compatible dependencies) | Discord.py 2.x + asyncio features require 3.11+ |
| **Git** | `sudo apt install git` | Needed to clone and update the repository |
| **Build Essentials** | `build-essential`, `libffi-dev`, `python3-dev` (optional but recommended) | Required for compiling optional dependencies like chat-exporter |
| **SQLite** | Bundled with Python; ensure filesystem permissions allow creating `apex_core.db` | Database migrations run automatically at startup |
| **Discord Resources** | Bot token, application ID, guild IDs, channel & role IDs, OAuth scopes (`bot applications.commands`) | Without correct IDs the bot cannot connect or deploy panels |
| **Network** | Outbound TCP 443 | Discord’s gateway and REST API |
| **Optional Enhancements** | `chat-exporter` (HTML transcripts), `boto3` (S3 transcript archival) | Enable premium transcript and storage flows |

> ℹ️ Keep a secure location (such as a password manager or secrets store) for the Discord token, config.json backups, and environment files used by systemd.

---

## 2. Ubuntu Deployment Guide (Step-by-step)
These steps assume a clean Ubuntu VM with sudo access. Commands prefixed with `$` run as your deploy user; those prefixed with `#` require sudo.

### Step 1 – Prepare the OS
```bash
# update packages and reboot if the kernel changes
sudo apt update && sudo apt upgrade -y

# install core dependencies
sudo apt install -y python3 python3-venv python3-pip git unzip
```
Optional but recommended:
```bash
sudo apt install -y build-essential libffi-dev python3-dev
```

### Step 2 – Create directories & clone the repository
```bash
mkdir -p ~/apps && cd ~/apps
git clone <your-repo-url> apex-core
cd apex-core
```
> Replace `<your-repo-url>` with the Git remote you were provided.

### Step 3 – Create and activate a Python virtual environment
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip wheel
```
You should now see `(.venv)` in your shell prompt. Use `deactivate` when finished.

### Step 4 – Install dependencies
```bash
pip install -r requirements.txt
# Optional enhancements
pip install -r requirements-optional.txt  # chat-exporter, boto3, etc.
```

### Step 5 – Prepare configuration files
```bash
cp config.example.json config.json
cp config/payments.example.json config/payments.json
```
Edit both files with your token, guild IDs, role IDs, logging channels, payment methods, etc. (See [Section 3](#3-configuration-guide) for every field.)

### Step 6 – Initialize directories for logs & transcripts
```bash
mkdir -p logs transcripts config_backups
```
The bot auto-writes logs to `logs/` (when enabled) and stores transcripts locally unless S3 is configured.

### Step 7 – Create the SQLite database & run migrations
The database is created automatically, but you can prime it before the first bot start:
```bash
python - <<'PY'
import asyncio
from apex_core import Database

async def bootstrap():
    db = Database('apex_core.db')
    await db.connect()
    await db.close()

asyncio.run(bootstrap())
PY
```
This runs all migrations up to schema v13 (users, orders, wallet_transactions, refunds, referrals, permanent_messages, setup_sessions, etc.).

### Step 8 – Smoke-test locally
```bash
python bot.py
```
Expected output (truncated):
```
INFO:apex_core.database:Current database schema version: 13
INFO:apex_core.database:Database schema migration complete. Final version: 13
INFO:discord.client:Logging in using static token
INFO:discord.client:Connected to Gateway
INFO:apex_core.logger:Apex Core is ready!
```
Press `Ctrl+C` to stop after confirming it logs in successfully.

### Step 9 – Optional validation scripts
Run the automated verifiers before production:
```bash
./verify_deployment.sh     # dependency + config sanity checks
pytest                     # 95 tests / 80%+ coverage
```

### Step 10 – Create a dedicated system user (recommended)
```bash
sudo useradd -r -s /bin/false apexcore
sudo chown -R apexcore:apexcore ~/apps/apex-core
```

### Step 11 – Create a systemd environment file
```bash
sudo mkdir -p /etc/apex-core
cat <<'EOF' | sudo tee /etc/apex-core/environment
DISCORD_TOKEN=your_bot_token
CONFIG_PATH=/opt/apex-core/config.json
PYTHONUNBUFFERED=1
EOF
sudo chmod 600 /etc/apex-core/environment
```
> Replace `/opt/apex-core` with the actual deployment path. The bot also reads `config.json` for the token, but overriding via environment keeps secrets out of Git.

### Step 12 – Install the systemd service
1. Copy the repository to `/opt` (or your production path) if you ran the above steps under your user:
   ```bash
   sudo rsync -a ~/apps/apex-core/ /opt/apex-core/
   sudo chown -R apexcore:apexcore /opt/apex-core
   ```
2. Review `apex-core.service` in the repo and adjust paths if needed:
   ```ini
   [Service]
   User=apexcore
   WorkingDirectory=/opt/apex-core
   EnvironmentFile=/etc/apex-core/environment
   ExecStart=/opt/apex-core/.venv/bin/python bot.py
   Restart=on-failure
   ```
3. Install and enable the unit:
   ```bash
   sudo cp apex-core.service /etc/systemd/system/apex-core.service
   sudo systemctl daemon-reload
   sudo systemctl enable --now apex-core.service
   ```

### Step 13 – Verify and monitor
```bash
sudo systemctl status apex-core.service --no-pager
sudo journalctl -u apex-core.service -f
```
Sample status output:
```
● apex-core.service - Apex Core Discord Bot
     Loaded: loaded (/etc/systemd/system/apex-core.service)
     Active: active (running) since Wed 2025-12-10 12:34:56 UTC; 5s ago
   Main PID: 4210 (python)
        CPU: 1.234s   Memory: 98.0M
```
For long-term monitoring, forward `journalctl` to your log aggregator or tail `logs/error.log` for stack traces.

### Deployment troubleshooting
- **Service keeps restarting**: Run `sudo -u apexcore /opt/apex-core/.venv/bin/python bot.py` manually to see raw exceptions (missing token, bad config, DB permissions).
- **`sqlite3.OperationalError: database is locked`**: Ensure only one bot process is running and that the service user owns `apex_core.db`.
- **Slash commands missing**: The bot syncs per guild during startup. Confirm `config.guild_ids` matches the actual servers and the bot has the `applications.commands` scope invited.
- **System clock issues**: Discord rejects connections with severely skewed clocks. Use `timedatectl status` and `sudo systemctl restart systemd-timesyncd` if needed.

---

## 3. Configuration Guide
All configuration lives under `/home/engine/project/config*` in development (or `/opt/apex-core` in production). The bot reads two JSON files plus optional environment overrides.

### 3.1 Files at a glance
| File | Purpose |
| --- | --- |
| `config.json` | Core runtime settings (token, guilds, roles, panels, rate limits, logging, etc.) |
| `config/payments.json` | Extended payment settings (rich methods, confirmation template, refund policy) |
| `config_backups/` | Auto-created directory where `ConfigWriter` stores timestamped backups before each write |
| Environment variables | `DISCORD_TOKEN`, `CONFIG_PATH`, `TRANSCRIPT_STORAGE_TYPE`, `S3_*` for secrets |

### 3.2 `config.json` reference
| Section | Key Fields | Description | Required? |
| --- | --- | --- | --- |
| **Identity** | `token`, `bot_prefix`, `guild_ids[]` | Discord bot token, text prefix (default `!`), guilds to sync slash commands to | Yes |
| **role_ids** | `admin` | Discord role ID trusted to run admin commands | Yes |
| **roles[]`** | `name`, `role_id`, `assignment_mode`, `unlock_condition`, `discount_percent`, `benefits`, `tier_priority` | Defines achievement/VIP tiers. Assignment modes: `automatic_spend`, `automatic_first_purchase`, `automatic_all_ranks`, `manual` | Optional but recommended |
| **ticket_categories** | `support`, `billing`, `sales` | Category IDs where tickets and deposit channels are created | Yes (support + billing) |
| **operating_hours** | `start_hour_utc`, `end_hour_utc` | 24h integers used in embeds and automated notices | Yes |
| **payment_methods[]** | `name`, `instructions`, `emoji`, `metadata` | Legacy inline payment methods when `config/payments.json` is absent | Optional (superseded by payments file) |
| **logging_channels** | `audit`, `payments`, `tickets`, `errors`, `order_logs`, `transcript_archive` | Targets for audit embeds, payment confirmations, ticket logs, error routing, manual order logs, transcript archive | Audit & errors strongly recommended |
| **refund_settings** | `enabled`, `max_days`, `handling_fee_percent` | Controls refund workflows in `refund_management` cog | Optional |
| **rate_limits** | Named after commands (`balance`, `wallet_payment`, etc.) with `cooldown`, `max_uses`, `per` | Maps to `RateLimitRule` for slash commands; `per` supports `user`, `guild`, etc. | Optional |
| **financial_cooldowns** | `wallet_payment`, `submitrefund`, etc. -> seconds | Enforces server-side cooldowns for high-risk commands | Optional |
| **category_ids / channel_ids** | Arbitrary mapping of blueprint-friendly names to IDs | Used when provisioning or logging needs to reference pre-existing infrastructure | Optional |
| **setup_settings** | `session_timeout_minutes`, `default_mode` (`modern` or `legacy`) | Controls `/setup` + legacy wizard persistence and UI preference | Optional |

### 3.3 Role tiers as achievements / badges
Example from `config.example.json`:
| Role | Assignment Mode | Unlock condition | Discount | Notes |
| --- | --- | --- | --- | --- |
| Apex Client | `automatic_first_purchase` | First successful order | 0% | Baseline client badge |
| Apex VIP | `automatic_spend` | $50 (5,000 cents) lifetime | 1.5% | Awarded automatically via `process_post_purchase` |
| Apex Elite / Legend / Sovereign / Zenith | `automatic_spend` / `automatic_all_ranks` | Higher spend thresholds | 2.5–7.5% | Serve as achievements and marketing badges |
| Apex Donor / Legendary Donor / Apex Insider | `manual` | Staff awarded | 0.25–0.5% | Use `/assign_role` + `/remove_role` commands |

### 3.4 Logging & ticket infrastructure
- `ticket_categories.support` → Support ticket creation / general help.
- `ticket_categories.billing` → Wallet deposit tickets.
- `ticket_categories.sales` → Optional channel for sales-only tickets.
- `logging_channels.audit` → Rollback + setup embeds.
- `logging_channels.order_logs` → Manual order confirmations.
- `logging_channels.transcript_archive` → Optional transcript drop when chat-exporter is installed.

### 3.5 Rate limits, cooldowns, and timeouts
- **`rate_limits`** protect slash commands on Discord’s side. Example:
  ```json
  "rate_limits": {
    "wallet_payment": {"cooldown": 300, "max_uses": 3, "per": "user"}
  }
  ```
- **`financial_cooldowns`** enforce server-side throttles via `FinancialCooldownManager` (cleared with `!cooldown-reset`).
- **`setup_settings.session_timeout_minutes`** controls how long `/setup` sessions persist in the DB before cleanup (default 30).

### 3.6 Payments configuration
`config/payments.json` houses:
```json
{
  "payment_methods": [
    {
      "name": "Wallet",
      "instructions": "Reply with \"Wallet\" to pay from balance",
      "emoji": "💰",
      "metadata": {"is_enabled": true}
    }
  ],
  "order_confirmation_template": "Order {order_id} confirmed for {service_name} - {variant_name} ...",
  "refund_policy": "Refunds accepted within 3 days with proof"
}
```
Use this file when you want rich metadata (links, warnings, wallet sufficiency) shown in the storefront payment embed.

### 3.7 Retrieving Discord IDs quickly
1. **Enable Developer Mode** in Discord → User Settings → Advanced → toggle *Developer Mode*.
2. **Guild/server ID**: Right-click the server icon → *Copy Server ID*.
3. **Channel ID**: Right-click channel → *Copy Channel ID*.
4. **Role ID**: Server Settings → Roles → right-click role → *Copy Role ID*.
5. **User ID**: Right-click the user anywhere → *Copy User ID*.
6. **Bot token**: Discord Developer Portal → *Bot* tab → *Reset Token* → copy (never commit to Git).

### 3.8 Reloading config without downtime
Use `apex_core.config_writer.ConfigWriter` to atomically patch sections and hot-reload the bot:
```python
import asyncio
from apex_core.config_writer import ConfigWriter

async def update_logging(bot):
    writer = ConfigWriter("config.json")
    await writer.set_logging_channels({
        "audit": 123456789012345678,
        "errors": 987654321098765432,
    }, bot=bot)

# schedule inside a cog or run via python - <<'PY'
```
`ConfigWriter` writes to `config.json.tmp`, renames it atomically, creates a timestamped backup in `config_backups/`, and (optionally) reloads `bot.config` immediately.

### 3.9 Configuration troubleshooting
- **JSON errors**: Run `python -m json.tool config.json` to validate after editing.
- **Missing admin role**: Logs will show `Admin role is missing or misconfigured` when running `/setup`, `/addbalance`, etc. Double-check `role_ids.admin`.
- **Incorrect ticket categories**: `/deposit` or support buttons fail with “category is not configured correctly.” Ensure the channel ID belongs to a category the bot can create channels under.
- **Token leaks**: Never store tokens in Git. Use environment variables or deployment secrets.

---

## 4. Features & Usage Guide
Each subsection explains the user experience, admin levers, and built-in error handling.

### 4.1 Storefront Feature (Browsing products)
- **User experience**: Users interact with the Products panel deployed via `/setup`/`!setup`. It shows an embed with a dropdown labeled *“Select Category (Scroll down for more)”* and `◀️ / ▶️` pagination buttons when more than 25 categories exist.
- **Flow**: Category → Sub-category → Product selection (each step uses its own `discord.ui.View`). Once a product is picked, the bot fetches live pricing from the database and displays payment options.
- **Data source**: `self.bot.db.get_distinct_main_categories()` and related DAO methods inside `cogs/storefront.py`.
- **UI description**:
  > 🖼️ A gold-accented embed titled “Apex Core Storefront” with buttons stacked under the dropdown to navigate categories. Selecting a category opens an ephemeral sub-category dropdown to keep channels clean.
- **Error handling**: If no categories exist, the dropdown shows “No categories available.” Exceptions while building the view are logged and surfaced as ephemeral errors.

### 4.2 Shopping & Cart (Checkout pipeline)
- **Pseudo-cart**: Apex Core processes one product at a time to keep transactions atomic. Once a user selects a product, a modal (`PurchaseConfirmModal`) asks them to type `CONFIRM`, effectively acting as a cart confirmation step.
- **Currency handling**: Prices are stored in cents (`price_cents`) and formatted via `format_usd`. Discounts (VIP tiers, manual promotions) are applied before payment instructions.
- **Payment instructions**: The `_build_payment_embed` function dynamically lists wallet sufficiency, Binance Pay IDs, PayPal links, crypto wallets, etc., pulling metadata from `config/payments.json`.
- **Admin oversight**: Staff monitor `logging_channels.payments` or `order_logs` for manual confirmations and can use `/manual_complete` to reconcile off-platform orders.
- **Failure modes**: If wallet balance or price changed mid-purchase, the modal is rejected with “Price has changed since you started this purchase.”

### 4.3 Wallet System
- **User commands**: `/deposit` opens a private deposit ticket in the billing category. `/balance` shows available funds + lifetime spend (admins can specify another member). `/transactions` provides paginated ledgers.
- **Admin commands**: `/addbalance` credits users (with audit logging + DM). Manual payouts or penalties can be logged via `/manual_complete` or refund commands.
- **UI description**:
  > 🖼️ Deposit tickets contain an embed titled “Wallet Deposit Ticket” that lists operating hours and each payment method as a button or external link. Users are pinged alongside `@Admin` when the channel spins up.
- **Safeguards**: All wallet mutations happen inside `Database.transaction()` to ensure ledger entries, wallet balances, and role promotions stay in sync. Rate limit + financial cooldown decorators protect `/deposit`, `/balance`, `/wallet_payment`, etc.

### 4.4 Reviews System
- **Panel**: Deploy the `reviews` panel via `/setup` to educate users on how to share experiences, earn `@Apex Insider`, and qualify for discounts.
- **Content**: Sections cover how to write reviews, rating scales, proof recommendations, and guidelines (“No profanity or spam”).
- **Submission workflow**: The default copy references a `/review` command; if you have not implemented a custom review cog yet, edit the panel text via `cogs/setup.py::_create_reviews_panel` to direct users to a ticket or form of your choice.
- **Admin actions**: Reward eligible reviewers with `/assign_role` (e.g., Apex Insider) and optionally a wallet bonus using `/addbalance`.
- **Error handling**: Panel validation (`_validate_reviews_panel`) checks for the word “review” in the embed title and for at least one button labeled “Write Review” or “View Reviews.”

### 4.5 Tickets & Support
- **Entry points**: Support + refund buttons on the `support` panel, `/deposit` for billing, `/submitrefund` for the refund cog, and legacy ticket commands.
- **Automation**:
  - Auto warnings after 48h inactivity and auto-closing after 49h.
  - HTML transcripts generated via chat-exporter (optional) and DM’d/logged.
  - Warranty notifications sent every 6 hours by `NotificationsCog` and manual `/test-warranty-notification` command.
- **Lifecycle**: Tickets live in `tickets` table with statuses, priorities, assigned staff, and optional `order_id` linkage.
- **Error handling**: `_validate_operation_prerequisites` ensures the bot has `Manage Channels`, `Send Messages`, and `Embed Links` before deploying support panels.

### 4.6 Referrals
- **User commands**:
  - `/invite` – shows referral code (Discord user ID) and stats.
  - `/invites` – deeper analytics + list of top referrals.
  - `/setref <code>` – link to a referrer (only once per user).
  - `/profile [member]` – includes referral stats and wallet snapshot.
- **Rewards**: Referrers earn 0.5% cashback tracked in `referrals` table. Admins can pay out pending cashbacks with `!sendref-cashb` and use `!referral-blacklist` to block abuse.
- **Error handling**: Input validation prevents self-referrals, invalid IDs, or multiple assignments.

### 4.7 Achievements & Badges (VIP roles)
- **Automatic promotions**: After each purchase (manual or storefront), `process_post_purchase` + `handle_vip_promotion` evaluate spend thresholds and assign the correct role(s).
- **Manual badges**: `/assign_role` and `/remove_role` manage manual tiers such as Apex Donor.
- **Config-driven**: Update `roles[]` in config.json to add new badges or adjust discounts. Gains are logged in audit channels and DM’d to the user.

### 4.8 Setup Command & Server Provisioning
- **Slash command**: `/setup` (guild-only) opens an interactive UI:
  1. Permission + eligible channel validation.
  2. Channel select (modern slash mode) or modal input (legacy `!setup`).
  3. Deployment confirmation summarising what will happen.
  4. Step-by-step progress updates (validation → generation → deployment).
- **Panel types**: `products`, `support`, `help`, `reviews`, or “All of the above.”
- **Full server setup**: Optionally run “🏗️ Full server setup” to provision roles, categories, channels, permission overwrites, auto-deploy panels, and log every action. Rollbacks remove roles/channels if anything fails.
- **Session persistence**: The `setup_sessions` table stores in-flight sessions so the wizard survives restarts. `Config.setup_settings.session_timeout_minutes` controls the expiry.
- **Dry-run mode**: Preview changes without deploying to catch permission issues (logged in the audit channel).

### 4.9 Admin Panel (command toolkit)
While there is no single GUI, Apex Core’s “admin panel” is the combination of:
- Wallet controls (`/addbalance`, `/manual_complete`).
- Order maintenance (`/order-status`, `/renew-warranty`, `/warranty-expiry`).
- Product management (`/import_products`, `!setup_store`).
- Ticket/support provisioning (`!setup_tickets`, `/test-warranty-notification`).
- Cooldown governance (`!cooldown-check`, `!cooldown-reset`, `!financial-commands`).
- Refund approvals (`!refund-approve`, `!refund-reject`, `!pending-refunds`).
Each command emits embeds with context (who triggered it, what changed) and writes to the relevant logging channels.

---

## 5. How to Customize & Change Things

### 5.1 Add new products to the storefront
1. Open `templates/products_template.xlsx` (or regenerate via `python create_template.py`).
2. Fill the **Products** sheet following `docs/products_template.md`.
3. Export as CSV.
4. Upload with `/import_products csv_file:<attachment>` (admin-only). The command reports how many rows were inserted/updated/skipped and lists validation errors inline.
5. Redeploy the storefront panel (`/setup` → products) if you want the embed copy to show “Last updated” timestamps.

### 5.2 Create new categories
- New categories/sub-categories are created implicitly when products use new values.
- To highlight them in Discord, edit `_create_product_panel` (for custom copy) or simply redeploy the panel to show the database-backed options.

### 5.3 Modify prices & currency handling
- Update `price_cents` via CSV import or custom admin tooling.
- `format_usd` handles USD formatting; if you need multi-currency support, extend `apex_core/utils/currency.py` and the embeds that call it. All downstream flows store cents integers, so conversions should happen at the edge.

### 5.4 Set up new roles & permissions
- Add a new role definition inside `roles[]` in `config.json` (see Section 3).
- Run a quick script with `ConfigWriter.set_role_ids` if you only need to update IDs while the bot is live.
- Use `/assign_role` or `/remove_role` for manual badges; automatic tiers update on purchase.

### 5.5 Create custom channels & categories
- Use the full server setup option in `/setup` to provision blueprint channels automatically.
- To add custom channels beyond the blueprint, create them manually in Discord and update `config.channel_ids` / `category_ids` so logging and future provisioning can target them.
- Call `await SetupCog._log_provisioned_ids(...)` (or rerun `/setup` full server) to persist IDs via `ConfigWriter`.

### 5.6 Configure ticket categories
- Update `ticket_categories.support/billing/sales` in `config.json`.
- Restart or use `ConfigWriter` to reload.
- Ensure the bot’s role has `Manage Channels` on the category and that “Allow anyone to create invites” is disabled if you want the bot to handle invites.

### 5.7 Modify panel layouts & content
- Edit these helper methods in `cogs/setup.py`:
  - `_create_product_panel`
  - `_create_support_panel`
  - `_create_help_panel`
  - `_create_reviews_panel`
- Keep button custom IDs stable if you rely on existing callbacks.
- Use `/setup dry-run` to preview before deploying.

### 5.8 Adjust timeouts, limits, and cooldowns
- **Slash command rate limits**: `config.json → rate_limits`.
- **Financial cooldowns**: `config.json → financial_cooldowns` (seconds). Use `!cooldown-reset` to clear specific users.
- **View timeouts**: Each view in `cogs/setup.py`, `cogs/storefront.py`, etc., sets a `timeout` parameter—adjust as needed.
- **Session timeouts**: `setup_settings.session_timeout_minutes`.

### 5.9 Add new features (developers)
1. Create a new cog file under `cogs/` with a `setup(bot)` function.
2. Register slash commands with `@app_commands.command` and prefix commands with `@commands.command`.
3. Import shared helpers from `apex_core.utils.*`, `rate_limiter`, `financial_cooldown_manager`, etc.
4. Add unit tests under `tests/` and run `pytest`.
5. Update documentation and, if needed, the blueprint/config templates.

### 5.10 Modify existing commands safely
- Slash commands: after editing, restart the bot so `self.tree.sync` runs per guild.
- Prefix commands: no additional sync needed.
- Always consider rate limits, permission checks, and audit logging when changing admin commands.
- Update `README.md` or this guide if behavior or parameters change.

---

## 6. Architecture & Code Structure

### 6.1 Repository layout
```
apex-core/
├── bot.py                # Entrypoint
├── apex_core/            # Core modules (config, database, utils, ...)
├── cogs/                 # Discord cogs (storefront, wallet, setup, etc.)
├── config/               # Payment config templates
├── docs/                 # Documentation (this file + payment guide)
├── templates/            # Excel templates (products)
├── tests/                # Pytest suites (unit + integration)
└── scripts (.sh/.py)     # Deployment + verification helpers
```

### 6.2 Runtime entrypoint (`bot.py`)
- Reads config (`load_config`), optional payments, and environment overrides.
- Validates Discord token format for early failure.
- Instantiates `ApexCoreBot`, which wires `Database`, `TranscriptStorage`, logger integration, and automatic cog loading.
- Syncs slash commands per guild listed in `config.guild_ids`.

### 6.3 Core modules
| Module | Responsibility |
| --- | --- |
| `apex_core/config.py` | Dataclasses + validators for every config section |
| `apex_core/database.py` | Async SQLite wrapper with transaction helper, 13 migrations, DAO methods for every feature |
| `apex_core/config_writer.py` | Atomic config updates + runtime reload |
| `apex_core/rate_limiter.py` | Decorators + helper for per-command rate limits |
| `apex_core/financial_cooldown_manager.py` | Global manager for financial cooldowns + cleanup |
| `apex_core/server_blueprint.py` | Dataclasses describing full server setup (roles, categories, channels, panel types) |
| `apex_core/storage.py` | Transcript storage abstraction (local folder or S3) |
| `apex_core/utils/` | Currency formatting, embed builders, VIP logic, timestamp helpers, and shared Discord utilities |

### 6.4 Cogs overview
| Cog | File | Highlights |
| --- | --- | --- |
| Storefront | `cogs/storefront.py` | Cascading dropdowns, purchase confirmation modal, payment embed |
| Wallet | `cogs/wallet.py` | Deposit tickets, balance lookup, admin crediting |
| Manual Orders | `cogs/manual_orders.py` | Manual fulfillment, manual role assignment/removal |
| Orders | `cogs/orders.py` | Order history, transaction history, warranty tools |
| Product Import | `cogs/product_import.py` | CSV importer with validation + async file parsing |
| Notifications | `cogs/notifications.py` | Warranty reminder loop + manual test command |
| Ticket Management | `cogs/ticket_management.py` | Ticket panels, auto-closing, transcripts |
| Refund Management | `cogs/refund_management.py` | `/submitrefund`, manual approval/rejection commands |
| Referrals | `cogs/referrals.py` | Referral stats, linking, cashback payout |
| Financial Cooldowns | `cogs/financial_cooldown_management.py` | Admin tooling for cooldown introspection |
| Setup | `cogs/setup.py` | Slash + prefix setup wizard, full server provisioning, rollback stack |

### 6.5 Database schema (summary)
| Table | Purpose | Key columns / relationships |
| --- | --- | --- |
| `users` | Wallet + profile metadata | `discord_id`, balances, manual roles |
| `products` | Storefront catalog | `main_category`, `variant_name`, `price_cents`, `role_id`, `is_active` |
| `discounts` | User/VIP/product-specific discounts | Foreign keys to `users` and `products` |
| `tickets` | Support & deposit tickets | `channel_id`, `status`, `type`, `order_id`, `assigned_staff_id`, timestamps |
| `orders` | Purchase & manual order history | `user_discord_id`, `product_id`, `price_paid_cents`, status, warranty columns |
| `wallet_transactions` | Ledger for every credit/debit | `amount_cents`, `balance_after_cents`, `transaction_type`, `order_id`, `ticket_id` |
| `transcripts` | Transcript metadata | Path/URL + ticket linkage |
| `ticket_counter` | Running counter for ticket numbers |
| `refunds` | Refund requests & states | `user_discord_id`, `status`, attachments |
| `referrals` | Referral pairs + spend stats | `referrer_user_id`, `referred_user_id`, `cashback` |
| `permanent_messages` | Panel deployments | `panel_type`, `channel_id`, `message_id`, `guild_id` |
| `setup_sessions` | Persisted `/setup` wizards | `guild_id`, `user_id`, `panel_types`, `current_index`, serialized payload |

### 6.6 Commands, views, and modals
- Slash commands live in cogs with `@app_commands.command` and are synced per guild.
- Prefix commands remain available for legacy workflows or CLI-like admin tools.
- UI interactions rely on `discord.ui.View`/`Select`/`Button` classes with timeouts and `on_timeout` handlers that disable controls + send follow-up notices.
- Modals like `PurchaseConfirmModal` offer lightweight confirmation forms to avoid accidental purchases.

### 6.7 Migrations workflow
1. Increment `Database.target_schema_version`.
2. Add a new `_migration_vN` method that executes SQL (and checks column existence before altering).
3. Register it inside the `migrations` dict in `_apply_pending_migrations`.
4. On startup, the bot applies pending migrations sequentially and records them in `schema_migrations`.

### 6.8 Testing
- Run `pytest` for unit + integration coverage.
- Use `tests/integration/*.py` for end-to-end flows (purchase, referral, refund).
- The coverage configuration excludes Discord-specific modules to keep enforcement focused on deterministic logic.

---

## 7. Admin Commands Reference
All commands below require the configured admin role unless otherwise noted.

### 7.1 Slash commands (admin-only)
| Command | Parameters | What it does / Expected output | Permission checks |
| --- | --- | --- | --- |
| `/addbalance` | `member`, `amount` (USD), `reason`, `notify_user?` | Credits a wallet, logs a ledger entry, DMs the user (if allowed). Output: Embed titled “Wallet Credit Applied” showing new balance and lifetime spend. | Admin role, bot needs `Send Messages` in invocation channel |
| `/manual_complete` | `user`, `amount`, `product_name`, `notes` | Records a manual order, updates lifetime spend, triggers VIP promotions, DMs customer, logs to `order_logs`. Output: “Manual Order Completed” embed. | Admin role |
| `/assign_role` | `user`, `role_name` (must match manual role) | Adds manual achievement roles, persists to DB, DMs the user about benefits. | Admin role |
| `/remove_role` | `user`, `role_name` | Removes roles + DB records and notifies the user. | Admin role |
| `/import_products` | `csv_file` attachment | Parses CSV, upserts products, reports inserted/updated counts and validation errors. | Admin role, `Attach Files` permission |
| `/order-status` | `order_id`, `status` choice | Updates `orders.status`, posts “Order #X Status Updated” embed. | Admin role |
| `/renew-warranty` | `order_id`, `days` | Sets new expiry, increments renewal count, posts embed with new date. | Admin role |
| `/warranty-expiry` | `days?` (default 7) | Lists upcoming expirations, DM summary, posts embed. | Admin role |
| `/test-warranty-notification` | none | Manually runs the warranty reminder loop and reports success/failure. | Admin role |
| `/setup` | interactive | Launches setup wizard (panels, full server provisioning, dry-run). Output: menu embed + progress edits. | Admin role + bot needs Manage Channels/Embeds |

> Commands such as `/balance`, `/orders`, `/transactions` are available to everyone, but specifying another member triggers the admin permission check internally.

### 7.2 Prefix commands
| Command | Purpose & expected output | Notes |
| --- | --- | --- |
| `!setup` | Legacy modal-based setup wizard for panels. Outputs multi-step embeds + status updates. | Requires admin role + channel permissions |
| `!setup-cleanup` | Cancels and rolls back any in-flight setup sessions/states. | Useful after partial deployments |
| `!setup-status` | Shows which panels are deployed + message IDs. | Reads from `permanent_messages` |
| `!setup_store` | Re-deploys just the storefront panel (shortcut). | Admin role |
| `!setup_tickets` | Re-deploys support/refund buttons panel. | Admin role |
| `!cooldown-check [@member]` (`!cc`) | Lists active financial cooldowns for yourself or another user. | Requires admin role via `cog_check` |
| `!cooldown-reset @member command_name` (`!cr`) | Clears a specific financial cooldown and logs to audit channel. | Admin |
| `!cooldown-cleanup` | Removes expired cooldown entries from memory. | Admin |
| `!financial-commands` (`!fc`) | Prints the known high-risk commands and their cooldown durations. | Admin |
| `!referral-blacklist @member` | Flags a user so their referral earnings stop accumulating + optional DM. | Admin |
| `!sendref-cashb [@member]` | Pays out pending referral cashback (all or single user) and logs the ledger entries. | Admin |
| `!refund-approve ticket_id amount reason` (aliases `refund_approve`) | Approves a refund request, logs payout instructions, updates DB. | Admin, requires refund cog configuration |
| `!refund-reject ticket_id reason` (aliases `refund_reject`) | Rejects a refund with embed sent to user and ticket. | Admin |
| `!pending-refunds` | Lists outstanding refund tickets with statuses for staff triage. | Admin |

> Need cron-style reminders about commands? Run `!financial-commands` to dump the sensitive command list and share it with staff.

---

## 8. Troubleshooting & Common Issues

### 8.1 Bot will not start
- Verify `config.json` exists and contains a valid token; errors appear as `ValueError: Token must be provided`.
- Ensure the service user can read/write `apex_core.db` and `config.json`.
- Check for missing dependencies (`ModuleNotFoundError: chat_exporter`) and either install optional packages or disable optional features.

### 8.2 Database connection or migration errors
- `sqlite3.OperationalError: unable to open database file` → Confirm the working directory and relative path when running via systemd.
- `Database connection timed out` → Look for lingering `apex_core.db-journal` files and remove them if the bot is stopped.
- If a migration fails mid-run, the bot stops; inspect logs, fix the schema (or delete the partially created objects), and restart.

### 8.3 Permission errors (panels, tickets, setup)
- Check the bot role has **Manage Channels**, **Send Messages**, **Embed Links**, and **Manage Roles** (for VIP promotions).
- When `/setup` reports “Channel not eligible,” run `/setup → Dry-run` to see the full permission diff.
- Make sure target channels are text channels (setup disallows voice/forums).

### 8.4 Panel deployment failures
- Run `!setup-status` to see stale entries and `!setup-cleanup` to remove them.
- Ensure `logging_channels.audit` is configured; detailed error embeds appear there with actionable tips.
- Use dry-run mode before redeploying large batches.

### 8.5 Message or embed rendering issues
- Discord enforces a 6000-character embed limit. If you heavily customise panel copy, keep fields concise.
- For button-heavy panels, confirm you stay within 25 component limit per message.

### 8.6 Commands not responding
- Slash commands require re-syncing when `config.guild_ids` changes; restart the bot after edits.
- If Discord gateway events stop, check `intents.members = True` and `intents.message_content = True` in `bot.py`.

### 8.7 Where to find logs
- **Runtime logs**: `journalctl -u apex-core.service -f` or `logs/*.log` if you configured file logging.
- **Setup/audit logs**: `logging_channels.audit` on Discord (embeds summarise deployments, rollbacks, cooldown resets, etc.).
- **Error details**: `logging_channels.errors` if configured; otherwise check `systemd` logs.

### 8.8 Reporting bugs or requesting help
- Collect: the failing command, guild ID, channel ID, relevant log excerpt, and config snippets (redacted tokens).
- Reference documents: `SETUP_ERROR_RECOVERY.md` for setup-specific issues, `RATE_LIMITING.md` for cooldown anomalies, `UBUNTU_E2E_TEST_REPORT.md` for environment assumptions.

---

## 9. Best Practices & Security
- **Never commit secrets**: `config.json`, `config/payments.json`, `apex_core.db`, and `.env` files are already gitignored—keep it that way.
- **Use least privilege**: Create an `@Apex Bot` role with only the permissions it needs (Manage Channels/Roles, Send Messages, Embed Links, Attach Files, Read Message History).
- **Back up data**: Snapshot `apex_core.db`, `config.json`, and `config_backups/` regularly. Store backups off-box.
- **Monitor logs**: Forward systemd logs to your SIEM, especially for financial commands.
- **Rate limiting**: Keep `rate_limits` and `financial_cooldowns` strict to prevent abuse.
- **Keep dependencies updated**: Re-run `pip install -r requirements.txt` after pulling new releases.
- **Validate before deploying**: Use `./verify_deployment.sh`, dry-run setup mode, and `pytest` on staging boxes before production changes.
- **Environment segregation**: Use different Discord applications/tokens for staging vs. production to avoid accidental cross-posting.

---

## 10. Quick Start Checklist
1. ✅ **Confirm prerequisites** (Ubuntu updated, Python 3.11+, git installed).
2. ✅ **Clone repository + create `.venv`** (`python3 -m venv .venv && source .venv/bin/activate`).
3. ✅ **Install dependencies** (`pip install -r requirements.txt`).
4. ✅ **Copy and edit configs** (`config.json`, `config/payments.json`, environment file for systemd).
5. ✅ **Run DB migrations** (`python bot.py` once or the bootstrap snippet).
6. ✅ **Smoke test locally** (watch for “Apex Core is ready!” in logs).
7. ✅ **Deploy systemd service** (`apex-core.service` + `journalctl -u apex-core.service -f`).
8. ✅ **Run `/setup`** to deploy storefront/support/help/review panels or full server provisioning.
9. ✅ **Test core workflows**: `/deposit`, storefront purchase, `/orders`, referral command, refund submission.
10. ✅ **Document & monitor**: Update internal runbooks, keep `DOCUMENTATION_INDEX.md` handy, and monitor audit/error channels.

### Where to go next
- Need a deeper dive into system setup? Read `QUICK_START_UBUNTU.md`.
- Want extensive deployment metrics? Check `UBUNTU_E2E_TEST_REPORT.md` and `DEPLOYMENT_SUMMARY.md`.
- Looking for rate limiting or setup recovery specifics? See `RATE_LIMITING.md` and `SETUP_ERROR_RECOVERY.md`.

> With this checklist and guide, you should be able to deploy, operate, and extend the Apex Core bot safely in any environment.
