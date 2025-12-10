# Apex Core: `!setup` Command Documentation

## Table of Contents
1. [Overview](#overview)
2. [Command Syntax](#command-syntax)
3. [What It Does](#what-it-does)
4. [Panel Types](#panel-types)
5. [Prerequisites](#prerequisites)
6. [Step-by-Step Workflow](#step-by-step-workflow)
7. [Architecture & Implementation](#architecture--implementation)
8. [Database Schema](#database-schema)
9. [Error Handling & Rollback](#error-handling--rollback)
10. [Related Commands](#related-commands)
11. [Code Quality Assessment](#code-quality-assessment)
12. [Known Issues & Limitations](#known-issues--limitations)
13. [Recommendations](#recommendations)

---

## Overview

The `!setup` command is an **interactive setup wizard** for deploying Discord panels (embeds with interactive components) for the Apex Core bot. It provides a menu-driven interface for administrators to deploy storefront panels, support buttons, help guides, and review system information to specific channels.

**Location**: `/cogs/setup.py` (1229 lines)  
**Main Class**: `SetupCog`  
**Command Type**: Text command (prefix-based, not slash command)

---

## Command Syntax

```
!setup
```

**Parameters**: None (interactive wizard)

**Permissions Required**:
- User must have the admin role configured in `config.json` (`role_ids.admin`)
- Bot must have the following permissions:
  - `Manage Channels`
  - `Send Messages` (in target channel)
  - `Embed Links` (in target channel)

**Where It Works**: Guild/server only (not DMs)

---

## What It Does

The `!setup` command allows administrators to:

1. **Deploy interactive panels** to Discord channels
2. **Update existing panels** (replaces old message with new one)
3. **Track deployments** in the database for persistence
4. **Choose between 4 panel types** (or deploy all at once)
5. **Select target channels** via text input modal
6. **View current deployment status** before making changes
7. **Automatically rollback** failed operations

### What Gets Created

When you deploy a panel:
- ✅ A Discord message with an embed
- ✅ Interactive UI components (buttons, dropdowns)
- ✅ A database record linking the panel to the channel/message
- ✅ An audit log entry (if audit channel configured)

### What Gets Saved to Database

The `permanent_messages` table stores:
- `id` - Auto-incrementing panel ID
- `type` - Panel type (products/support/help/reviews)
- `message_id` - Discord message ID
- `channel_id` - Discord channel ID
- `guild_id` - Discord guild/server ID
- `title` - Panel title
- `description` - Panel description
- `created_by_staff_id` - Discord user ID of admin who deployed it
- `created_at` - Timestamp of creation
- `updated_at` - Timestamp of last update

---

## Panel Types

### 1. Product Catalog Panel (storefront)

**Value**: `products`  
**Emoji**: 🛍️  
**Title**: "Apex Core: Products"

**What it does**:
- Shows a dropdown menu with product categories from database
- Users can browse products by category
- Paginated if more than 25 categories exist
- Uses `CategorySelectView` from `cogs/storefront.py`

**Requirements**:
- Database must have at least one product with a main category
- Calls: `await self.bot.db.get_distinct_main_categories()`

**Visual Components**:
- Embed with title and description
- Category dropdown (max 25 per page)
- Previous/Next buttons (if paginated)

---

### 2. Support & Refund Buttons

**Value**: `support`  
**Emoji**: 🛟  
**Title**: "Support Options"

**What it does**:
- Provides two buttons for ticket creation:
  1. **General Support** - Opens general support ticket
  2. **Refund Support** - Opens refund request ticket
- Uses `TicketPanelView` from `cogs/ticket_management.py`

**Requirements**:
- `ticket_categories.support` must be configured in config.json
- Bot must have permission to create channels in that category

**Visual Components**:
- Embed with two fields explaining each option
- Two buttons (primary and danger style)

---

### 3. Help Guide

**Value**: `help`  
**Emoji**: ❓  
**Title**: "How to Use Apex Core"

**What it does**:
- Static informational embed
- Explains how to use the bot's features
- No interactive components

**Content Sections**:
1. How to Browse Products
2. How to Make Purchases
3. How to Use Your Wallet
4. How to Open Tickets
5. How to Request Refunds
6. How to Invite Friends (referrals)
7. Need Help? section

**Requirements**: None (static content)

---

### 4. Review System Guide

**Value**: `reviews`  
**Emoji**: ⭐  
**Title**: "Share Your Experience"

**What it does**:
- Static informational embed
- Explains the review system and rewards
- No interactive components

**Content Sections**:
1. How to Leave a Review
2. Rating System (1-5 stars)
3. Write Your Feedback (character limits)
4. Optional Photo Proof
5. Earn Rewards (@Apex Insider role + 0.5% discount)
6. What Gets Approved?
7. Guidelines (profanity, spam, respect)
8. Submit Your Review Today!

**Requirements**: None (static content)

---

## Prerequisites

### Configuration Requirements

The bot's `config.json` must have:

```json
{
  "role_ids": {
    "admin": 123456789012345678  // Admin role ID
  },
  "logging_channels": {
    "audit": 444444444444444444  // Optional: for audit logs
  },
  "ticket_categories": {
    "support": 111111111111111111  // Required for support panel
  }
}
```

### Bot Permissions

The bot must have these permissions in the guild:
- `Manage Channels` (checked by `_validate_operation_prerequisites`)
- `Send Messages` in target channel
- `Embed Links` in target channel

### Database Connection

The bot must be connected to the SQLite database:
- Database path: `apex_core.db` (default)
- Table: `permanent_messages` must exist (created by migrations)

### User Requirements

The user running `!setup` must:
- Have the admin role configured in `role_ids.admin`
- Be a member of the guild (not a bot)

---

## Step-by-Step Workflow

### Initial Command Execution

```
User types: !setup
```

1. **Permission Check**
   - Bot verifies user has admin role (`self._is_admin()`)
   - If not admin → "Only admins can use this command."

2. **Fetch Current Deployments**
   - Queries database: `await self.bot.db.get_deployments(ctx.guild.id)`
   - Creates status embed showing which panels are deployed

3. **Show Setup Menu**
   - Embed displays:
     - Current deployment status for each panel type
     - Options for what to deploy
   - View displays dropdown with 5 options:
     1. Product Catalog Panel (storefront)
     2. Support & Refund Buttons
     3. Help Guide
     4. Review System Guide
     5. All of the above

### User Selects Option

```
User selects from dropdown: e.g., "Product Catalog Panel (storefront)"
```

4. **Handle Selection** (`_handle_setup_selection`)
   - Cleans up any existing wizard state for this user
   - Creates new `WizardState` object:
     ```python
     WizardState(
         user_id=interaction.user.id,
         guild_id=interaction.guild.id,
         panel_types=["products"],  # or multiple if "all" selected
         current_index=0,
         completed_panels=[],
         rollback_stack=[],
         started_at=datetime.now(timezone.utc)
     )
     ```
   - Stores state in `self.user_states` dict (in-memory)
   - Shows channel input modal

### Channel Input Modal

```
Modal appears: "Deploy Products Panel"
Input field: "Channel name or #mention"
```

5. **User Enters Channel Name** (e.g., "products" or "#products")

6. **Process Channel Input** (`_process_channel_input`)
   - Validates session hasn't expired
   - Strips "#" prefix if present
   - Searches guild channels by name or ID:
     ```python
     for ch in interaction.guild.text_channels:
         if ch.name.lower() == channel_input.lower() or str(ch.id) == channel_input:
             channel = ch
             break
     ```
   - If not found → "❌ Channel `{channel_input}` not found. Please try again."

7. **Validate Prerequisites**
   - Checks bot permissions in target channel
   - Validates database connection
   - If validation fails → Shows error, does NOT deploy

### Panel Deployment

8. **Deploy Panel** (`_deploy_panel`)
   - Wraps in atomic operation context manager
   - Creates rollback stack for potential recovery

   **Step 8.1**: Create embed and view
   ```python
   if panel_type == "products":
       embed, view = await self._create_product_panel()
   elif panel_type == "support":
       embed, view = await self._create_support_panel()
   # ... etc
   ```

   **Step 8.2**: Send message to channel
   ```python
   message = await channel.send(embed=embed, view=view)
   ```
   - Adds `RollbackInfo` to stack:
     ```python
     RollbackInfo(
         operation_type="message_sent",
         panel_type=panel_type,
         channel_id=channel.id,
         message_id=message.id,
         guild_id=guild.id,
         user_id=user_id
     )
     ```

   **Step 8.3**: Database operations
   - Check if panel already exists in this channel:
     ```python
     existing = await self.bot.db.get_panel_by_type_and_channel(
         panel_type, channel.id, guild.id
     )
     ```
   - If exists → Update message ID: `await self.bot.db.update_panel(existing["id"], message.id)`
   - If new → Create record: `await self.bot.db.deploy_panel(...)`
   - Adds database operation to rollback stack

   **Step 8.4**: Log to audit channel
   - Creates embed with deployment details
   - Sends to `logging_channels.audit` if configured

   **Step 8.5**: Clear rollback stack (success)
   - If everything succeeded, clears rollback stack
   - Rollback is only executed if exception occurs

### Multi-Panel Deployment

9. **Continue to Next Panel** (if "all" was selected)
   - Updates wizard state: `state.current_index += 1`
   - Adds completed panel to `state.completed_panels`
   - Shows success message with button: "Continue: Setup {next_panel} Panel"
   - If user clicks button → Shows new channel input modal
   - Repeats steps 5-8 for next panel

10. **Completion**
    - When all panels deployed → "🎉 All panels deployed successfully!"
    - Cleans up wizard state: `await self._cleanup_wizard_state(user_id, reason)`
    - Removes user from `self.user_states` dict

---

## Architecture & Implementation

### Key Classes & Dataclasses

#### `SetupCog` (Main Cog)

**Attributes**:
- `self.bot` - Reference to bot instance
- `self.user_states` - Dict mapping user_id to WizardState (in-memory state)
- `self._rollback_lock` - AsyncIO lock for rollback operations

**Key Methods**:
- `setup()` - Main command handler
- `_handle_setup_selection()` - Processes dropdown selection
- `_process_channel_input()` - Handles channel name input
- `_deploy_panel()` - Deploys a single panel (atomic operation)
- `_create_product_panel()` - Creates products panel embed/view
- `_create_support_panel()` - Creates support panel embed/view
- `_create_help_panel()` - Creates help panel embed
- `_create_reviews_panel()` - Creates reviews panel embed
- `_validate_operation_prerequisites()` - Checks permissions and DB connection
- `_execute_rollback_stack()` - Executes rollback operations
- `_rollback_single_operation()` - Rolls back one operation
- `_log_audit()` - Logs to audit channel
- `_cleanup_wizard_state()` - Cleans up expired/completed sessions
- `_cleanup_expired_states()` - Background task to clean expired sessions (every 5 min)

**Lifecycle Task**:
```python
self.bot.loop.create_task(self._cleanup_expired_states())
```
- Runs every 5 minutes
- Expires wizard states older than 30 minutes
- Executes rollbacks for incomplete operations

---

#### `WizardState` (Dataclass)

Tracks multi-step setup wizard progress:

```python
@dataclass
class WizardState:
    user_id: int               # Discord user ID
    guild_id: int              # Discord guild ID
    panel_types: List[str]     # Queue of panels to deploy
    current_index: int         # Current position in queue
    completed_panels: List[str] # Successfully deployed panels
    rollback_stack: List[RollbackInfo]  # Operations to rollback on failure
    started_at: datetime       # Session start time (for expiration)
```

**Storage**: In-memory only (`self.user_states` dict)  
**Expiration**: 30 minutes of inactivity  
**Persistence**: ❌ NOT persisted to database (lost on bot restart)

---

#### `RollbackInfo` (Dataclass)

Tracks individual operations for rollback:

```python
@dataclass
class RollbackInfo:
    operation_type: str         # "message_sent", "panel_created", "panel_updated"
    panel_type: str             # Panel type identifier
    channel_id: Optional[int]   # Discord channel ID (for message deletion)
    message_id: Optional[int]   # Discord message ID (for deletion)
    panel_id: Optional[int]     # Database panel ID (for DB operations)
    guild_id: Optional[int]     # Discord guild ID
    user_id: Optional[int]      # Discord user ID
    timestamp: datetime         # When operation occurred
```

**Rollback Operations**:

1. **`message_sent`**: Deletes the Discord message
   ```python
   channel = self.bot.get_channel(rollback_info.channel_id)
   message = await channel.fetch_message(rollback_info.message_id)
   await message.delete()
   ```

2. **`panel_created`**: Removes database record
   ```python
   await self.bot.db.remove_panel(rollback_info.panel_id)
   ```

3. **`panel_updated`**: ⚠️ Cannot fully rollback
   - Just logs that rollback occurred
   - Old message ID is not stored, so can't restore previous message
   - **Limitation**: Manual cleanup may be needed

---

#### `SetupOperationError` (Custom Exception)

```python
class SetupOperationError(Exception):
    def __init__(self, message: str, rollback_info: Optional[RollbackInfo] = None):
        super().__init__(message)
        self.rollback_info = rollback_info
```

Used for:
- Permission errors
- Database connection failures
- Unknown panel types
- Channel access issues

---

### Discord UI Components

#### `SetupMenuView` & `SetupMenuSelect`

**Purpose**: Initial setup menu with 5 options  
**Timeout**: 300 seconds (5 minutes)  
**Component**: Dropdown select menu

**Options**:
1. "Product Catalog Panel (storefront)" → `value="products"`
2. "Support & Refund Buttons" → `value="support"`
3. "Help Guide" → `value="help"`
4. "Review System Guide" → `value="reviews"`
5. "All of the above" → `value="all"`

**Callback**: `cog._handle_setup_selection(interaction, selection)`

---

#### `ChannelInputModal`

**Purpose**: Collect channel name/mention from user  
**Title**: "Deploy {panel_type.title()} Panel"

**Fields**:
- `channel_input` (TextInput):
  - Label: "Channel name or #mention"
  - Placeholder: "e.g., products or #products"
  - Required: Yes
  - Max length: 100 characters

**on_submit**: `cog._process_channel_input(interaction, channel_input.value, panel_type)`

---

#### `ContinueSetupView` & `ContinueSetupButton`

**Purpose**: Allow user to continue multi-panel setup  
**Label**: "Continue: Setup {panel_type.title()} Panel"  
**Style**: Primary (blue)  
**Emoji**: ▶️  
**Timeout**: 300 seconds

**Callback**: Opens new `ChannelInputModal` for next panel

**User Validation**: Only the original user can click the button

---

#### `DeploymentSelectView` (Currently unused in main workflow)

**Purpose**: Show deployment management menu  
**Buttons**:
1. "Deploy New" 🚀
2. "Update" ✏️
3. "Remove" 🗑️
4. "Done" ✅

**Note**: These buttons reference `PanelTypeModal` which asks for panel type text input, but this flow is not integrated into the main `!setup` command workflow.

---

### Atomic Operations & Context Manager

```python
@asynccontextmanager
async def _atomic_operation(self, operation_name: str):
    """Context manager for atomic operations with automatic rollback."""
    rollback_stack: List[RollbackInfo] = []
    try:
        yield rollback_stack
    except Exception as e:
        logger.error(f"Atomic operation '{operation_name}' failed: {e}")
        await self._execute_rollback_stack(rollback_stack, f"Failed operation: {operation_name}")
        raise
```

**Usage**:
```python
async with self._atomic_operation(f"deploy_panel_{panel_type}") as rollback_stack:
    # Step 1: Send message
    message = await channel.send(embed=embed, view=view)
    rollback_stack.append(RollbackInfo(...))
    
    # Step 2: Database operation
    panel_id = await self.bot.db.deploy_panel(...)
    rollback_stack.append(RollbackInfo(...))
    
    # If exception occurs anywhere, all operations are rolled back
    # If successful, clear rollback_stack
    rollback_stack.clear()
```

**Benefits**:
- ✅ Automatic cleanup on failure
- ✅ Transactional semantics (all-or-nothing)
- ✅ Prevents orphaned messages or database records

**Limitations**:
- ⚠️ Rollback is best-effort (network failures may prevent cleanup)
- ⚠️ Update operations can't fully rollback (old message ID not stored)

---

## Database Schema

### `permanent_messages` Table

Created by database migrations (schema version 12).

**Columns**:

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PRIMARY KEY | Auto-incrementing panel ID |
| `type` | TEXT NOT NULL | Panel type (products/support/help/reviews) |
| `message_id` | INTEGER NOT NULL | Discord message ID |
| `channel_id` | INTEGER NOT NULL | Discord channel ID |
| `guild_id` | INTEGER NOT NULL | Discord guild/server ID |
| `title` | TEXT NOT NULL | Panel title |
| `description` | TEXT | Panel description |
| `created_by_staff_id` | INTEGER | Discord user ID of admin who deployed |
| `created_at` | TIMESTAMP | Creation timestamp (default CURRENT_TIMESTAMP) |
| `updated_at` | TIMESTAMP | Last update timestamp |

**Indexes**: None explicitly defined (consider adding for query performance)

**Foreign Keys**: None (could add for referential integrity)

---

### Database Methods

#### `deploy_panel()`

```python
async def deploy_panel(
    self,
    panel_type: str,
    message_id: int,
    channel_id: int,
    guild_id: int,
    title: str,
    description: str,
    created_by_staff_id: int,
) -> int:
```

**Purpose**: Insert new panel record  
**Returns**: Database ID (lastrowid)

---

#### `get_deployments()`

```python
async def get_deployments(self, guild_id: int) -> list[dict]:
```

**Purpose**: Get all panels for a guild  
**Query**: `SELECT ... FROM permanent_messages WHERE guild_id = ? ORDER BY type, created_at`  
**Returns**: List of dict records

---

#### `get_panel_by_type_and_channel()`

```python
async def get_panel_by_type_and_channel(
    self, panel_type: str, channel_id: int, guild_id: int
) -> Optional[dict]:
```

**Purpose**: Find existing panel in specific channel  
**Use Case**: Check if updating or creating new panel  
**Returns**: Panel dict or None

---

#### `update_panel()`

```python
async def update_panel(self, panel_id: int, message_id: int) -> None:
```

**Purpose**: Update message_id and updated_at timestamp  
**Use Case**: When redeploying to same channel

---

#### `remove_panel()`

```python
async def remove_panel(self, panel_id: int) -> None:
```

**Purpose**: Delete panel record  
**Use Case**: Cleanup orphaned panels

---

#### `find_panel()`

```python
async def find_panel(self, panel_type: str, guild_id: int) -> Optional[dict]:
```

**Purpose**: Find first panel of type in guild (used by cleanup/status commands)  
**Returns**: Panel dict or None

---

## Error Handling & Rollback

### Validation Errors

#### Permission Errors

```python
if not guild.me.guild_permissions.manage_channels:
    raise SetupOperationError("Bot needs 'Manage Channels' permission")

if not channel.permissions_for(guild.me).send_messages:
    raise SetupOperationError(f"Bot cannot send messages in {channel.mention}")

if not channel.permissions_for(guild.me).embed_links:
    raise SetupOperationError(f"Bot cannot embed links in {channel.mention}")
```

**User Message**: "❌ {error_message}"  
**Action**: Does NOT deploy panel

---

#### Database Connection Errors

```python
try:
    await self.bot.db.get_deployments(guild.id)
except Exception as e:
    raise SetupOperationError(f"Database connection failed: {e}")
```

**User Message**: "❌ Database connection failed: {details}"  
**Action**: Does NOT deploy panel

---

### Deployment Errors

#### Channel Not Found

```python
if not channel:
    await interaction.followup.send(
        f"❌ Channel `{channel_input}` not found. Please try again.",
        ephemeral=True,
    )
```

**Action**: User can try again with correct channel name

---

#### Rollback on Failure

When any exception occurs during `_deploy_panel()`:

```python
except SetupOperationError as e:
    error_msg = f"❌ Failed to deploy {panel_type} panel"
    if "permission" in str(e).lower():
        error_msg += f": {str(e)}"
    else:
        error_msg += ". The operation has been rolled back."
    
    await interaction.followup.send(error_msg, ephemeral=True)
    logger.error(f"Setup operation failed for user {interaction.user.id}: {e}")
```

**Rollback Actions**:
1. Delete sent Discord message (if exists)
2. Remove database panel record (if created)
3. Log rollback to audit channel
4. Show error to user

---

### Audit Logging

#### Rollback Log

```python
embed = create_embed(
    title="🔄 Setup Rollback Executed",
    description=f"**Reason:** {reason}\n**Operations Rolled Back:** {len(rollback_stack)}",
    color=discord.Color.orange(),
)

for i, rollback_info in enumerate(rollback_stack[:5], 1):
    embed.add_field(
        name=f"{i}. {rollback_info.operation_type}",
        value=f"Panel: {rollback_info.panel_type}\nTime: {rollback_info.timestamp}",
        inline=False,
    )
```

**Sent to**: `logging_channels.audit` (if configured)

---

#### Success Log

```python
embed = create_embed(
    title="🔧 Setup Action",
    description=f"**Action:** Panel Deployed\n**Details:** ...",
    color=discord.Color.blurple(),
)
```

**Sent to**: `logging_channels.audit` (if configured)

---

## Related Commands

### `!setup-cleanup`

**Purpose**: Clean up orphaned panels and expired wizard states

**Options** (via dropdown):
1. **Clean Expired States** - Removes wizard states older than 30 minutes
2. **Clean All States** - Forcibly ends all active wizard sessions
3. **Clean Orphaned Panels** - Removes panels with deleted channels/messages
4. **Full Cleanup** - All of the above

**Permissions**: Admin only

**Code**:
```python
@commands.command(name="setup-cleanup")
async def setup_cleanup(self, ctx: commands.Context) -> None:
```

**Orphaned Panel Detection**:
- Checks if channel exists: `guild.get_channel(deployment["channel_id"])`
- Checks if message exists: `await channel.fetch_message(deployment["message_id"])`
- If missing → Deletes from database

---

### `!setup-status`

**Purpose**: Show current setup status and active sessions

**Displays**:
- Active wizard sessions (user, progress, next panel)
- Recent deployments (last 5 panels)
- Database connection status

**Permissions**: Admin only

**Code**:
```python
@commands.command(name="setup-status")
async def setup_status(self, ctx: commands.Context) -> None:
```

**Example Output**:
```
📊 Setup Status Report

Active Setup Sessions:
• JohnDoe#1234: 2/4 (Next: help)
• JaneSmith#5678: 1/1 (Next: Complete)

Recent Deployments:
• Products: #products (message_id)
• Support: #support (message_id)
• Help: #info (message_id)
```

---

## Code Quality Assessment

### ✅ Strengths

1. **Well-structured code**: Clear separation of concerns, modular methods
2. **Comprehensive error handling**: Try-catch blocks, validation checks
3. **Rollback mechanism**: Atomic operations with automatic cleanup
4. **Audit logging**: Tracks all setup actions
5. **Type hints**: Good use of type annotations
6. **Dataclasses**: Clean state management with WizardState and RollbackInfo
7. **Async/await**: Proper async code patterns
8. **User-friendly**: Interactive UI with clear instructions
9. **Background cleanup**: Automatic expiration of old sessions
10. **Documentation**: Docstrings on most methods

---

### ⚠️ Areas for Improvement

#### 1. Missing Tests
**Issue**: No test coverage for setup command  
**Impact**: High - Core functionality untested  
**Risk**: Regressions, bugs in edge cases

#### 2. State Persistence
**Issue**: Wizard state only in memory, lost on bot restart  
**Impact**: Medium - Users lose progress if bot restarts mid-setup  
**Risk**: Poor user experience during deployments/updates

#### 3. Channel Input Method
**Issue**: Text-based channel input instead of dropdown  
**Impact**: Medium - More error-prone, users can typo channel names  
**Risk**: Frustration, multiple attempts needed

#### 4. Rollback Limitations
**Issue**: Panel updates can't fully rollback (old message ID not stored)  
**Impact**: Low - Only affects update operations  
**Risk**: Manual cleanup needed in rare cases

#### 5. No Confirmation Dialogs
**Issue**: No confirmation before deploying/updating panels  
**Impact**: Low - Accidental deployments possible  
**Risk**: Admin confusion, accidental overwrites

#### 6. Duplicate Prevention
**Issue**: Can deploy same panel type to multiple channels  
**Impact**: Low - May be intentional design  
**Risk**: Confusion about which panel is "active"

#### 7. Error Message Specificity
**Issue**: Some errors just say "failed" without details  
**Impact**: Low - Makes debugging harder  
**Risk**: Admin frustration, support burden

#### 8. No Dry-Run Mode
**Issue**: Can't preview what will be deployed  
**Impact**: Low - Would be nice for testing  
**Risk**: None, just convenience feature

---

### 🐛 Potential Bugs

#### 1. Permission Check Timing

**Location**: `_validate_operation_prerequisites()` called AFTER user selects channel  
**Issue**: User can select a channel without knowing if bot has permissions  
**Impact**: User goes through modal only to get permission error  
**Fix**: Pre-check permissions or show only valid channels

---

#### 2. State Management Race Condition

**Location**: `self.user_states` dictionary  
**Issue**: No locking when accessing/modifying user states  
**Impact**: Rare - Could have issues if same user triggers setup twice simultaneously  
**Fix**: Add asyncio.Lock per user or use thread-safe data structure

---

#### 3. Rollback Lock Scope

**Location**: `self._rollback_lock` is cog-wide  
**Issue**: All rollback operations are serialized globally  
**Impact**: Low - Could slow down multiple simultaneous failed deployments  
**Fix**: Use per-user or per-guild locks instead

---

#### 4. Database Transaction Handling

**Location**: `_deploy_panel()` method  
**Issue**: Message is sent BEFORE database transaction commits  
**Impact**: If database commit fails, message exists but no database record  
**Risk**: Orphaned messages that aren't tracked  
**Fix**: Use database transactions properly (begin, commit, rollback)

---

#### 5. View Timeout Handling

**Location**: All View classes  
**Issue**: Timeout is 300 seconds, but no indication to user  
**Impact**: View becomes unresponsive after 5 minutes  
**Risk**: User confusion, must run command again  
**Fix**: Add timeout message or increase timeout

---

## Known Issues & Limitations

### 1. No Slash Command Support

**Description**: Only supports text commands (`!setup`), not slash commands (`/setup`)  
**Impact**: Less discoverable, not compatible with modern Discord UX  
**Workaround**: None - must use `!setup`

---

### 2. Wizard State Not Persisted

**Description**: In-memory state lost if bot restarts  
**Impact**: Users lose progress mid-deployment  
**Workaround**: Complete setup in one session

---

### 3. Text-Based Channel Selection

**Description**: User must type channel name instead of selecting from dropdown  
**Impact**: More error-prone  
**Workaround**: Ensure correct channel name or use channel ID

---

### 4. Update Rollback Incomplete

**Description**: When updating existing panel, old message ID is not stored for rollback  
**Impact**: Can't restore previous message if update fails  
**Workaround**: Manual cleanup required

---

### 5. No Multi-Guild State Isolation

**Description**: Wizard state keyed only by user_id, not (user_id, guild_id)  
**Impact**: User can only run setup in one guild at a time  
**Workaround**: Complete setup in one guild before starting in another

---

### 6. Session Expiration Fixed at 30 Minutes

**Description**: No configuration option for session timeout  
**Impact**: Long deployments may timeout  
**Workaround**: None - complete within 30 minutes

---

### 7. No Panel Validation

**Description**: Doesn't verify panels are working after deployment  
**Impact**: Silent failures if views don't register  
**Workaround**: Manually test panels after deployment

---

### 8. No Bulk Operations

**Description**: Can't deploy/remove multiple panels at once efficiently  
**Impact**: Must deploy each panel individually (unless "all" is selected)  
**Workaround**: Use "All of the above" option

---

## Recommendations

### High Priority

#### 1. Add Test Coverage

**Why**: Core functionality should be tested  
**Suggested Tests**:
- Test successful panel deployment
- Test rollback on failure
- Test permission validation
- Test channel resolution
- Test state expiration
- Mock database and Discord API

**Example**:
```python
@pytest.mark.asyncio
async def test_deploy_product_panel_success(mock_bot, mock_guild, mock_channel):
    cog = SetupCog(mock_bot)
    success = await cog._deploy_panel("products", mock_channel, mock_guild, 123)
    assert success == True
    mock_bot.db.deploy_panel.assert_called_once()
```

---

#### 2. Add Slash Command Support

**Why**: Modern Discord UX, better discoverability  
**Implementation**:
```python
@app_commands.command(name="setup", description="Interactive setup wizard for Apex Core panels")
@app_commands.default_permissions(administrator=True)
async def setup_slash(self, interaction: discord.Interaction) -> None:
    # Same logic as text command
```

---

#### 3. Use Channel Dropdown Instead of Text Input

**Why**: Less error-prone, better UX  
**Implementation**:
```python
class ChannelSelectModal(discord.ui.Modal):
    channel_select = discord.ui.ChannelSelect(
        placeholder="Select a channel...",
        channel_types=[discord.ChannelType.text]
    )
```

**Note**: Discord modals don't support select menus yet, so this would need to be a separate message with a select menu instead of a modal.

---

### Medium Priority

#### 4. Persist Wizard State to Database

**Why**: Survive bot restarts  
**Implementation**:
- Add `setup_wizard_sessions` table
- Save state after each step
- Restore on bot startup

---

#### 5. Add Confirmation Dialogs

**Why**: Prevent accidental deployments  
**Implementation**:
```python
class ConfirmDeployView(discord.ui.View):
    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success)
    async def confirm(self, interaction, button):
        # Proceed with deployment
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction, button):
        # Cancel deployment
```

---

#### 6. Improve Error Messages

**Why**: Better debugging, better UX  
**Examples**:
- "Database connection failed: timeout after 5s" → "Database connection timed out. Please try again or contact support."
- "Failed to deploy panel" → "Failed to deploy panel: Missing permission 'Send Messages' in #channel"

---

#### 7. Add Database Transactions

**Why**: Proper atomicity for database operations  
**Implementation**:
```python
async with self.bot.db._connection.execute("BEGIN TRANSACTION"):
    # Database operations
    await self.bot.db._connection.commit()
```

---

### Low Priority

#### 8. Add Dry-Run Mode

**Why**: Preview before deploying  
**Implementation**: Add `--dry-run` flag that shows what would be deployed without actually deploying

---

#### 9. Add Panel Templates

**Why**: Easier customization  
**Implementation**: Store panel templates in database, allow admins to edit

---

#### 10. Add Deployment History

**Why**: Track changes over time  
**Implementation**: Add `deployment_history` table with version tracking

---

#### 11. Add Bulk Import/Export

**Why**: Migrate configurations between servers  
**Implementation**: JSON export/import of all panels

---

## Conclusion

The `!setup` command is a **well-architected interactive wizard** with comprehensive error handling and rollback mechanisms. It successfully abstracts the complexity of deploying Discord panels behind a user-friendly interface.

**Key Strengths**:
- ✅ Robust error handling
- ✅ Atomic operations with rollback
- ✅ Audit logging
- ✅ Clean code structure

**Key Weaknesses**:
- ❌ No test coverage
- ❌ Text-based channel input
- ❌ In-memory only wizard state

**Overall Assessment**: **Production-ready with room for improvement**

The command works correctly for its intended purpose, but would benefit from test coverage, slash command support, and better state persistence to improve reliability and user experience.

---

## Code Reference

**Main File**: `/cogs/setup.py` (1229 lines)

**Key Entry Points**:
- Line 883: `@commands.command(name="setup")`
- Line 674: `async def _handle_setup_selection()`
- Line 709: `async def _process_channel_input()`
- Line 577: `async def _deploy_panel()`

**Database Methods**: `/apex_core/database.py`
- Line 2591: `async def deploy_panel()`
- Line 2629: `async def get_deployments()`
- Line 2653: `async def get_panel_by_type_and_channel()`
- Line 2680: `async def update_panel()`
- Line 2700: `async def remove_panel()`
- Line 2715: `async def find_panel()`

**Related Files**:
- `/cogs/storefront.py` - Line 336: `CategorySelectView`
- `/cogs/ticket_management.py` - Line 38: `TicketPanelView`
- `/apex_core/config.py` - Configuration dataclasses

---

*Document created by: AI Analysis of Apex Core Bot*  
*Last updated: 2024*  
*Repository: apex-digital*
