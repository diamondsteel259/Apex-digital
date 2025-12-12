# Setup Command Architecture Review (SetupCog)

This document is a **code-level architecture review** of the setup system: the interactive setup wizard, the full server provisioning workflow, and how panels/roles/channels/config are created, validated, persisted, and rolled back.

> Primary implementation: `cogs/setup.py` (class `SetupCog`)

## File/Module Index (code references)

- **Setup wizard + provisioning + rollback**: `cogs/setup.py`
  - Entry points: `SetupCog.setup` (prefix), `SetupCog.setup_slash` (slash) (`cogs/setup.py:2434+`, `:2487+`)
  - Selection router: `SetupCog._handle_setup_selection` (`cogs/setup.py:1963+`)
  - Modern UI: `ChannelSelectView`, `ConfirmationView`, `_show_deployment_confirmation`, `_execute_deployment_with_progress` (`cogs/setup.py:256+`, `:2205+`, `:2287+`)
  - Deployment: `_deploy_panel` + `_validate_panel_deployment` (`cogs/setup.py:917+`, `:1069+`)
  - Rollback: `RollbackInfo`, `_execute_rollback_stack`, `_rollback_single_operation` (`cogs/setup.py:21+`, `:488+`, `:501+`)
  - Sessions: `SetupSession`, `_save_session_to_db`, `_restore_sessions_on_startup`, `_cleanup_setup_session` (`cogs/setup.py:43+`, `:822+`, `:853+`, `:725+`)
  - Full server provisioning: `_start_full_server_setup`, `_execute_full_server_provisioning`, `_provision_*` (`cogs/setup.py:1490+`, `:1547+`, `:1698+`)

- **Server blueprint (roles/categories/channels/overwrites)**: `apex_core/server_blueprint.py`
  - `get_apex_core_blueprint()` defines the entire structure.

- **Database schema + panel records + session persistence**: `apex_core/database.py`
  - Table `permanent_messages` (migration v11): `Database._migration_v11` (`apex_core/database.py:2542+`)
  - Table `setup_sessions` (migration v13): `Database._migration_v13` (`apex_core/database.py:2593+`)
  - Panel accessors: `deploy_panel`, `get_deployments`, `find_panel`, `update_panel`, `remove_panel` (`apex_core/database.py:2633+`, `:2671+`, `:2757+`, etc.)
  - Transactions: `Database.transaction()` (`apex_core/database.py:2782+`)

- **Persistent UI components referenced by setup panels**:
  - Product panel view: `cogs/storefront.py` (`CategorySelectView`, `CategorySelect`) — persistent view with `custom_id` (`cogs/storefront.py:298+`)
  - Support panel view: `cogs/ticket_management.py` (`TicketPanelView`) — persistent view with `custom_id` (`cogs/ticket_management.py:38+`)

- **Config persistence utilities**:
  - `apex_core/config.py` (dataclasses + parsing, incl. `setup_settings`, `category_ids`, `channel_ids`)
  - `apex_core/config_writer.py` (`ConfigWriter` for atomic writes + backups)

---

## 1) Setup Command Flow

### 1.1 Entry Points (slash vs prefix)

#### Slash: `/setup`
- Handler: `SetupCog.setup_slash` (`cogs/setup.py:2487+`)
- Constraints:
  - `@app_commands.guild_only()` — must be run in a guild.
  - Admin-gated via `_is_admin()` which checks whether the user has the configured admin role id (`bot.config.role_ids.admin`).
- UX:
  - All bot replies are **ephemeral** (`interaction.response.defer(ephemeral=True, ...)`, then `followup.send(..., ephemeral=True)`).
- Pre-validation:
  - Calls `_precompute_eligible_channels(guild)` early to surface permission problems before showing the menu.

#### Prefix: `!setup`
- Handler: `SetupCog.setup` (`cogs/setup.py:2434+`)
- Constraints:
  - Must be in a guild.
  - Admin-gated via `_is_admin()` (same role-id based check).
- UX:
  - Posts the setup menu as a normal message in the channel.
  - After the menu is posted, **all subsequent interactions are component interactions**, so responses can still be ephemeral.

#### Other related admin commands
- `!setup-cleanup` (`cogs/setup.py:2574+`): cleanup wizard states / sessions and orphaned panels.
- `!setup-status` (`cogs/setup.py:2629+`): show active sessions and recent deployments.

### 1.2 High-level setup wizard steps

The setup wizard is primarily driven by **a dropdown selection** and then a **per-panel channel selection + confirmation + deploy** loop.

#### Step A — Load the setup wizard UI
1. Load current deployments via `bot.db.get_deployments(guild_id)`.
2. Build an embed showing deployment status per panel type.
3. Present `SetupMenuView` which contains `SetupMenuSelect` (dropdown).

#### Step B — Handle menu selection
- Handler: `SetupCog._handle_setup_selection(interaction, selection)` (`cogs/setup.py:1963+`)
- Selection routing:
  - `full_server` → `_start_full_server_setup()` (infrastructure + panels)
  - `dry_run` → `_start_dry_run()` (preview only)
  - `products|support|help|reviews|all` → start a setup session and begin the panel deployment loop

#### Step C — Create/replace SetupSession
When a panel or multi-panel setup is chosen, `_handle_setup_selection`:
1. Calls `_precompute_eligible_channels(guild)` to gather channels where the bot can post panels.
2. Creates `SetupSession(guild_id, user_id, panel_types, ...)` and stores it in:
   - `SetupCog.setup_sessions[(guild_id, user_id)]`
3. Saves the session to DB via `_save_session_to_db(session)`.
4. Starts the first panel deployment using the **modern flow**: `_start_panel_deployment_slash(interaction, first_panel, session)`.

### 1.3 Modern UI interactions (ChannelSelect + Confirmation)

#### Channel selection
- View: `ChannelSelectView(panel_type, user_id, session)` (`cogs/setup.py:256+`)
- Component: `discord.ui.ChannelSelect(channel_types=[text])`
- Validations:
  - Only the invoker (`interaction.user.id`) can interact.
  - Enforces selected channel is a `discord.TextChannel`.

> Note: The message says “Only channels where the bot has required permissions are shown”, but `ChannelSelectView` itself does not filter; eligibility filtering is handled elsewhere (see limitations).

#### Confirmation
- View: `ConfirmationView(panel_type, channel, user_id, session, existing_panel)` (`cogs/setup.py:325+`)
- Buttons:
  - Confirm: defers (`interaction.response.defer(ephemeral=True, thinking=True)`) then calls `_execute_deployment_with_progress(...)`
  - Cancel: sends an ephemeral cancellation message
- Timeout:
  - 3 minutes; on timeout it attempts to notify via `original_interaction.followup.send(...)`.

#### Progress updates
- Function: `_execute_deployment_with_progress(...)` (`cogs/setup.py:2287+`)
- Steps:
  1. Validate prerequisites (`_validate_operation_prerequisites`)
  2. “Generate panel content” (informational only)
  3. Deploy (`_deploy_panel`)
  4. If more panels in the session, show next `ChannelSelectView`; else complete and cleanup session.

### 1.4 Legacy/modal interactions (ChannelInputModal)

There is a modal-based channel input path:
- Modal: `ChannelInputModal(panel_type, session)` (`cogs/setup.py:209+`)
- Handler: `_process_channel_input(interaction, channel_input, panel_type, session)` (`cogs/setup.py:2067+`)

However:
- `_handle_setup_selection` currently always starts with `_start_panel_deployment_slash` (modern channel selector).
- The modal flow is still reachable via `ContinueSetupView` → `ContinueSetupButton` which opens `ChannelInputModal` (`cogs/setup.py:166+`).

In practice this creates a **mixed UX** unless the legacy path is fully removed or re-enabled as an explicit mode.

### 1.5 Error handling patterns

#### SetupOperationError
- Custom exception: `SetupOperationError` (`cogs/setup.py:82+`)
- Supports categorized error types (`permission`, `database`, `validation`, etc.) and a user-facing formatter `format_for_user()`.

#### Where errors are surfaced
- Slash entry point (`setup_slash`) catches `SetupOperationError` and generic exceptions.
- Deploy flow (`_execute_deployment_with_progress`) catches `SetupOperationError` and generic exceptions and edits the original ephemeral response.
- Channel input flow (`_process_channel_input`) catches and sends followup messages.

---

## 2) Server Configuration (Full Server Setup)

Full server setup uses a blueprint defined in `apex_core/server_blueprint.py:get_apex_core_blueprint()`.

### 2.1 Categories and channels created

**Naming conventions**:
- Categories: emoji + uppercase (e.g. `📦 PRODUCTS`)
- Channels: lowercase, hyphen-separated when needed (e.g. `audit-log`)

#### Category: `📦 PRODUCTS`
- Purpose: storefront / product catalog
- Channels:
  - `#products` (text)
    - Topic: "🛍️ Browse our product catalog and open tickets to purchase"
    - Panel deployed: **products**

#### Category: `🛟 SUPPORT`
- Purpose: user support entrypoint + staff-only ticket coordination
- Channels:
  - `#support` (text)
    - Topic: "🛟 Need help? Click buttons below to open a ticket"
    - Panel deployed: **support**
  - `#tickets` (text)
    - Topic: "📋 Active support tickets - Staff only"
    - No panel deployed (acts as a staff-only coordination channel)

#### Category: `📋 INFORMATION`
- Purpose: read-only guidance / docs / announcements
- Channels:
  - `#help` (text)
    - Topic: "❓ How to use Apex Core - Read this first!"
    - Panel deployed: **help**
  - `#reviews` (text)
    - Topic: "⭐ Share your experience and earn rewards"
    - Panel deployed: **reviews**
  - `#announcements` (text)
    - Topic: "📢 Important updates and announcements"
    - No panel deployed

#### Category: `📊 LOGS`
- Purpose: staff-only operational logging
- Channels:
  - `#audit-log` (text) — system audit logs and setup actions
  - `#payment-log` (text) — payment confirmations and transactions
  - `#error-log` (text) — system errors/exceptions

### 2.2 Channel organization hierarchy

Blueprint hierarchy is:

```
📦 PRODUCTS
  └─ #products

🛟 SUPPORT
  ├─ #support
  └─ #tickets

📋 INFORMATION
  ├─ #help
  ├─ #reviews
  └─ #announcements

📊 LOGS
  ├─ #audit-log
  ├─ #payment-log
  └─ #error-log
```

### 2.3 What each channel is used for

| Channel | Type | Intended use | Panel type |
|---|---:|---|---|
| `#products` | text | Storefront entrypoint; product catalog UI | `products` |
| `#support` | text | Ticket creation entrypoint (General Support / Refund) | `support` |
| `#tickets` | text | Staff-only coordination / tracking | none |
| `#help` | text | General documentation/how-to | `help` |
| `#reviews` | text | Review guidance + potentially review actions | `reviews` |
| `#announcements` | text | Staff announcements | none |
| `#audit-log` | text | Setup/audit logs (bot writes) | none |
| `#payment-log` | text | Payment logs (bot writes) | none |
| `#error-log` | text | Error logs (bot writes) | none |

### 2.4 Idempotency / reuse behavior

Full server setup is designed to be **idempotent**:
- `_provision_role`, `_provision_category`, `_provision_channel` first check for existing resources by name and reuse them if found.
- Each provision call returns `(resource, is_new)` and the audit summary distinguishes **created vs reused**.

---

## 3) Roles & Permissions

### 3.1 Roles created/managed by full server setup
Defined in `apex_core/server_blueprint.py`:

1. **Apex Staff**
   - Intended for staff/admin team
   - Permissions include (non-exhaustive):
     - `view_channel`, `send_messages`, `embed_links`, `attach_files`, `read_message_history`
     - `manage_channels`, `manage_messages`, `manage_roles`
     - `kick_members`, `ban_members`, `view_audit_log`

2. **Apex Client**
   - Intended for customers
   - Permissions include: `view_channel`, `send_messages`, `embed_links`, `attach_files`, `read_message_history`, reactions/external emojis.

3. **Apex Insider**
   - Intended for reviewer/rewards tier
   - Similar permissions to Apex Client.

### 3.2 Admin gating role (not created)
The setup command uses `_is_admin(member)` which checks membership in `bot.config.role_ids.admin`.
- This role is **not created by the blueprint**.
- Ticket creation also mentions this role (TicketManagement uses it for pinging).

### 3.3 Permission overwrites (category + channel)

Overwrites are expressed in the blueprint as a mapping of role-name → permission booleans. Implementation uses:
- `_build_role_map(guild)` and `_build_overwrites(...)` in `cogs/setup.py` (`:1854+`, `:1861+`).

#### Inheritance
- Category overwrites apply to channels unless explicitly overridden.
- Many blueprint channels redundantly re-declare `@everyone` and `Apex Staff` permissions to be explicit.

#### Notable overwrite patterns
- Public read-only channels:
  - Many channels set `@everyone: view_channel=True, send_messages=False`
- Staff-only channels:
  - `#tickets`, `📊 LOGS/*` set `@everyone: view_channel=False`
- Reviews channel:
  - Allows `Apex Client` and `Apex Staff` to send, but not `@everyone`.

### 3.4 Blueprint overwrite matrix (exact)

Below is a condensed summary of the **explicit** permission overwrites declared in `apex_core/server_blueprint.py`. Any permission not listed is left as “inherit/default”.

#### `📦 PRODUCTS` (category)
- `@everyone`: `view_channel ✅`, `send_messages ❌`, `add_reactions ✅`
- `Apex Staff`: `view_channel ✅`, `send_messages ✅`, `manage_messages ✅`

`#products` (channel)
- `@everyone`: `view_channel ✅`, `send_messages ❌`, `add_reactions ✅`
- `Apex Staff`: `view_channel ✅`, `send_messages ✅`

#### `🛟 SUPPORT` (category)
- `@everyone`: `view_channel ✅`, `send_messages ❌`
- `Apex Staff`: `view_channel ✅`, `send_messages ✅`, `manage_channels ✅`

`#support` (channel)
- `@everyone`: `view_channel ✅`, `send_messages ❌`, `add_reactions ✅`
- `Apex Staff`: `view_channel ✅`, `send_messages ✅`

`#tickets` (channel)
- `@everyone`: `view_channel ❌`
- `Apex Staff`: `view_channel ✅`, `send_messages ✅`, `manage_channels ✅`

#### `📋 INFORMATION` (category)
- `@everyone`: `view_channel ✅`, `send_messages ❌`, `add_reactions ✅`
- `Apex Staff`: `view_channel ✅`, `send_messages ✅`

`#help` (channel)
- `@everyone`: `view_channel ✅`, `send_messages ❌`
- `Apex Staff`: `view_channel ✅`, `send_messages ✅`

`#reviews` (channel)
- `@everyone`: `view_channel ✅`, `send_messages ❌`
- `Apex Client`: `view_channel ✅`, `send_messages ✅`
- `Apex Staff`: `view_channel ✅`, `send_messages ✅`

`#announcements` (channel)
- `@everyone`: `view_channel ✅`, `send_messages ❌`
- `Apex Staff`: `view_channel ✅`, `send_messages ✅`

#### `📊 LOGS` (category)
- `@everyone`: `view_channel ❌`
- `Apex Staff`: `view_channel ✅`, `send_messages ✅`

`#audit-log` / `#payment-log` / `#error-log` (channels)
- `@everyone`: `view_channel ❌`
- `Apex Staff`: `view_channel ✅`, `send_messages ❌`

---

## 4) Implementation Details

### 4.1 Database tables involved

#### `permanent_messages` (panels)
- Created in migration v11: `Database._migration_v11` (`apex_core/database.py:2542+`).
- Schema (key columns):
  - `id` (PK)
  - `type` (panel type string: `products|support|help|reviews`)
  - `message_id` (Discord message id, unique)
  - `channel_id`, `guild_id`
  - `title`, `description`
  - `created_by_staff_id`

Used by setup via:
- `Database.get_deployments(guild_id)`
- `Database.find_panel(panel_type, guild_id)`
- `Database.update_panel(panel_id, message_id)`
- `Database.remove_panel(panel_id)`

#### `setup_sessions` (wizard persistence)
- Created in migration v13: `Database._migration_v13` (`apex_core/database.py:2593+`).
- Schema includes:
  - `(guild_id, user_id)` unique composite key
  - `panel_types` JSON string
  - `current_index`, `completed_panels`, `progress`, `session_payload`
  - `expires_at` for cleanup

Used by setup via:
- `Database.create_setup_session(...)` (upsert)
- `Database.get_all_active_sessions()` + `cleanup_expired_sessions()`

### 4.2 Validation logic and checks

#### Guild/channel prerequisites
- `_validate_operation_prerequisites(guild, channel)` (`cogs/setup.py:639+`)
  - Requires `guild.me.guild_permissions.manage_channels`
  - Requires `send_messages` and `embed_links` in target channel
  - Performs a DB call to ensure DB is reachable

#### Eligible channel precomputation
- `_precompute_eligible_channels(guild)` (`cogs/setup.py:672+`)
  - Ensures `Manage Channels` in guild
  - Returns all text channels where bot has `send_messages` and `embed_links`

#### Post-deployment validation
- `_validate_panel_deployment(guild, channel, message, panel_type, existing_panel)` (`cogs/setup.py:1069+`)
  - Confirms the message exists and has embed/components
  - Confirms DB record matches message/channel/guild
  - Runs panel-type-specific validation:
    - `_validate_products_panel`
    - `_validate_support_panel`
    - `_validate_help_panel`
    - `_validate_reviews_panel`

### 4.3 Rollback mechanism

Rollback is tracked via `RollbackInfo` objects stored in `SetupSession.rollback_stack`.

#### RollbackInfo
- `cogs/setup.py:21+`
- Tracks:
  - `operation_type` (e.g. `message_sent`, `panel_created`, `panel_updated`, infrastructure ops)
  - `panel_type`
  - IDs for message/channel/panel/guild/user
  - `previous_message_id` to revert panel updates
  - infra rollback: `role_id`, `category_id`, `previous_overwrites`

#### Execution
- `_execute_rollback_stack(rollback_stack, reason)` (`cogs/setup.py:488+`)
  - Applies operations in reverse order.
- `_rollback_single_operation(rollback_info)` (`cogs/setup.py:501+`)
  - `message_sent`: delete the Discord message
  - `panel_created`: delete DB record
  - `panel_updated`: restore previous `message_id` in DB
  - `role_created|category_created|channel_created`: delete created Discord resources
  - `permissions_updated`: attempt to restore old overwrites

#### Observability
- `_log_rollback_operation` sends a summary embed to the configured audit channel (`bot.config.logging_channels.audit`).

### 4.4 Session management (SetupSession, locks, timeouts)

#### In-memory session model
- `SetupSession` dataclass (`cogs/setup.py:43+`)
- Key properties:
  - Keyed by `(guild_id, user_id)` so the same admin can run setup in multiple guilds concurrently.
  - `session_lock: asyncio.Lock` intended to prevent concurrent operations for the same session.

#### Expiration
- Background task `_cleanup_expired_states()` runs every 5 minutes and expires sessions after ~30 minutes.

#### Persistence across restarts
- Startup task `_restore_sessions_on_startup()` reads DB `setup_sessions` and recreates `SetupSession` objects.
- `_save_session_to_db()` writes via `Database.create_setup_session(...)`.

### 4.5 How panels are created and managed

#### Panel creation
- `_deploy_panel(panel_type, channel, guild, user_id)` (`cogs/setup.py:917+`)
- Process:
  1. Build embed + view from `_create_*_panel`.
  2. Send the message in the target channel.
  3. Insert/update `permanent_messages` for that panel type.
  4. Validate (`_validate_panel_deployment`).

#### Panel UI components
- **Products** panel uses `CategorySelectView` from `cogs/storefront.py` (persistent components with `custom_id`).
- **Support** panel uses `TicketPanelView` from `cogs/ticket_management.py` (persistent components with `custom_id`).
- **Help** + **Reviews** panels currently return an empty `discord.ui.View()` (no interactive components).

---

## 5) Current Issues / Limitations (as of current code)

This section is intended as a starting point for follow-up fixes.

### 5.1 Panel validation failures (support/help/reviews)

#### Support panel validator incorrectly detects buttons
- Panel buttons are labeled: `"General Support"` and `"Refund Support"` (`cogs/ticket_management.py:44+`).
- Validation logic (`cogs/setup.py:_validate_support_panel`, `:1219+`) does:
  ```py
  if "support" in label:
      support_buttons_found = True
  elif "refund" in label:
      refund_buttons_found = True
  ```
- Because `"Refund Support"` contains `"support"`, the `elif` never runs, so `refund_buttons_found` remains `False`.
- Result: validation reports **"Missing refund button"** even though it exists.

#### Help panel validator does not match actual help panel
- Help panel title is `"❓ How to Use Apex Core"` (`cogs/setup.py:_create_help_panel`, `:1376+`).
- Validator expects the embed title to include the substring `"help"` and expects buttons for sections like `getting started`, `troubleshooting`, `faq` (`cogs/setup.py:_validate_help_panel`, `:1256+`).
- Current help panel returns `discord.ui.View()` with **no components**.
- Result: validation fails (missing components + title mismatch).

#### Reviews panel validator does not match actual reviews panel
- Reviews panel title is `"⭐ Share Your Experience"` (`cogs/setup.py:_create_reviews_panel`, `:1430+`).
- Validator expects `"review"` in the title and expects buttons like `"write review"` or `"view reviews"` (`cogs/setup.py:_validate_reviews_panel`, `:1289+`).
- Current reviews panel returns **no components**.
- Result: validation fails.

### 5.2 Panel deployment transaction bugs (`execute_insert`)

In `_deploy_panel`, the “create new panel record” path uses:
```py
panel_id = await tx.execute_insert(...)
```
But `Database.transaction()` currently yields a raw `aiosqlite.Connection` (`apex_core/database.py:2782+`), which **does not have `execute_insert`**.

Impact:
- New panel deployments will raise an `AttributeError` during DB insert, be caught by `_deploy_panel`, and return `False`.

### 5.3 Validation failure does not automatically rollback

If `_validate_panel_deployment(...)` returns failure, `_deploy_panel` currently:
- logs audit info
- returns `False`

It does **not** delete the just-sent message or revert the DB record immediately.
Cleanup only occurs later if/when the session rollback stack is executed (session cleanup/expiration).

### 5.4 Setup session persistence is incomplete

- `_save_session_to_db()` serializes `current_index` and `completed_panels` into `session_payload`, but it only calls `Database.create_setup_session(guild_id, user_id, panel_types, ...)`.
- `Database.create_setup_session` upserts and **resets `current_index` to 0 on conflict** (`apex_core/database.py:2840+`).
- `completed_panels` is not written to the dedicated column, and no call is made to `Database.update_setup_session`.

Impact:
- Restored sessions may restart from the beginning rather than continue from where they left off.

### 5.5 Full server setup does not persist provisioned IDs into config

`SetupCog` includes `_log_provisioned_ids(...)` (`cogs/setup.py:786+`) to write IDs into `config.json` via `ConfigWriter`, but it is **not invoked** by `_execute_full_server_provisioning`.

Impact:
- After full provisioning, `config.json` may still have stale IDs in:
  - `category_ids`
  - `channel_ids`
  - `role_ids`
- Other cogs that depend on config IDs may not automatically start using the provisioned infrastructure.

### 5.6 Ticket privacy / category mismatch risk

Ticket creation in `cogs/ticket_management.py` creates ticket channels inside `bot.config.ticket_categories.support`.
- The blueprint creates a public `🛟 SUPPORT` category where `@everyone` can view channels.
- The ticket creation flow only grants the requesting member access, but does not explicitly deny `@everyone`.

Impact:
- If `ticket_categories.support` points to the public SUPPORT category, newly created ticket channels may be visible to everyone.

### 5.7 Potential bot permission conflicts in log channels

Blueprint log channels (`#audit-log`, `#payment-log`, `#error-log`) deny `send_messages` for `Apex Staff` at the channel level.
- If the bot is assigned `Apex Staff`, it may be unable to write logs.
- The setup system relies on writing to the audit channel in multiple places.

### 5.8 Timeout notifications depend on `original_interaction`

Many views implement `on_timeout()` by calling `self.original_interaction.followup.send(...)`.
- In prefix usage, `SetupMenuView.original_interaction` is set to `None` (`cogs/setup.py:2483+`), so timeouts may not notify the invoker.

### 5.9 “sqlite Row rollback error” (likely sources)

No literal `sqlite3.Row` error string is present in the repository, but the following code paths are strong candidates for the reported rollback problems:
- `_deploy_panel` uses a non-existent `execute_insert` API during a transaction (see 5.2). This can surface as a failed transaction and cascading cleanup/rollback behaviors.
- DB transaction manager uses SQL statements `BEGIN TRANSACTION` / `ROLLBACK` / `COMMIT` (`apex_core/database.py:2782+`) rather than connection-level `commit()` / `rollback()`. If nested transactions or implicit transactions occur elsewhere, SQLite can raise unexpected transaction-state errors.

---

## Suggested follow-up work (non-exhaustive)

1. Fix `_deploy_panel` DB insert path:
   - Use `Database.deploy_panel(...)` or `cursor = await tx.execute(...); cursor.lastrowid`.
2. Align validators with real panel content:
   - Fix support validator’s `if/elif` logic.
   - Either add interactive views for help/reviews or relax validation expectations.
   - Ensure help/review embed titles match validator assumptions (or vice versa).
3. Decide on **one** setup UX mode (modern vs legacy) and remove the mixed flow.
4. Make session persistence real:
   - Write `current_index` and `completed_panels` columns (use `update_setup_session`).
   - Don’t reset to `0` on upsert unless intentionally starting over.
5. Full server setup should update config values it provisions:
   - Call `_log_provisioned_ids(...)` (and possibly `ConfigWriter.set_ticket_categories`, `set_logging_channels` as needed).
6. Ensure ticket categories are private and ticket channel overwrites are explicitly set (deny `@everyone`).

---

## Appendix: Relevant config fields

From `config.example.json` and `apex_core/config.py`:
- `role_ids.admin`: admin gating + staff pinging
- `ticket_categories.support|billing|sales`: category IDs used by ticket system
- `logging_channels.audit|payments|tickets|errors`: operational log destinations
- `category_ids` / `channel_ids`: general mapping of provisioned infra IDs
- `setup_settings.session_timeout_minutes` and `setup_settings.default_mode`
