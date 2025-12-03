# SetupCog Error Recovery Implementation

## Overview

This document describes the comprehensive error recovery and rollback functionality implemented for the SetupCog in the Apex Core Discord bot. The system ensures that failed setup operations are properly rolled back, preventing orphaned data and inconsistent states.

## Architecture

### Core Components

#### 1. RollbackInfo Dataclass
```python
@dataclass
class RollbackInfo:
    """Information needed for rollback operations."""
    operation_type: str
    panel_type: str
    channel_id: Optional[int] = None
    message_id: Optional[int] = None
    panel_id: Optional[int] = None
    guild_id: Optional[int] = None
    user_id: Optional[int] = None
    timestamp: datetime = None
```

**Purpose**: Tracks each operation that can be rolled back, including all necessary context for cleanup.

**Operation Types**:
- `message_sent`: Discord message was sent (can be deleted)
- `panel_created`: Database panel record was created (can be removed)
- `panel_updated`: Database panel record was updated (log for manual cleanup)

#### 2. WizardState Dataclass
```python
@dataclass
class WizardState:
    """State tracking for multi-step setup wizard."""
    user_id: int
    guild_id: int
    panel_types: List[str]
    current_index: int
    completed_panels: List[str]
    rollback_stack: List[RollbackInfo]
    started_at: datetime
```

**Purpose**: Tracks the complete state of multi-step setup operations with rollback capability.

#### 3. SetupOperationError Exception
```python
class SetupOperationError(Exception):
    """Custom exception for setup operation failures."""
    def __init__(self, message: str, rollback_info: Optional[RollbackInfo] = None):
        super().__init__(message)
        self.rollback_info = rollback_info
```

**Purpose**: Provides structured error handling with optional rollback information.

### Error Recovery Methods

#### 1. Atomic Operations Context Manager
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

**Purpose**: Ensures atomic execution of multi-step operations with automatic rollback on failure.

#### 2. Rollback Execution
```python
async def _execute_rollback_stack(self, rollback_stack: List[RollbackInfo], reason: str) -> None:
    """Execute a stack of rollback operations."""
    async with self._rollback_lock:
        for rollback_info in reversed(rollback_stack):
            try:
                await self._rollback_single_operation(rollback_info)
                logger.info(f"Rolled back {rollback_info.operation_type} for {rollback_info.panel_type}")
            except Exception as e:
                logger.error(f"Failed to rollback {rollback_info.operation_type}: {e}")
        
        # Log the rollback operation
        if rollback_stack:
            await self._log_rollback_operation(rollback_stack, reason)
```

**Purpose**: Executes rollback operations in reverse order (LIFO) with comprehensive logging.

#### 3. Prerequisite Validation
```python
async def _validate_operation_prerequisites(self, guild: discord.Guild, channel: discord.TextChannel) -> None:
    """Validate that all prerequisites are met for setup operations."""
    if not guild.me.guild_permissions.manage_channels:
        raise SetupOperationError("Bot needs 'Manage Channels' permission")

    if not channel.permissions_for(guild.me).send_messages:
        raise SetupOperationError(f"Bot cannot send messages in {channel.mention}")
    
    if not channel.permissions_for(guild.me).embed_links:
        raise SetupOperationError(f"Bot cannot embed links in {channel.mention}")

    # Test database connection
    try:
        await self.bot.db.get_deployments(guild.id)
    except Exception as e:
        raise SetupOperationError(f"Database connection failed: {e}")
```

**Purpose**: Validates all requirements before starting operations to prevent partial failures.

### State Management

#### 1. Automatic Cleanup
```python
async def _cleanup_expired_states(self) -> None:
    """Clean up expired wizard states."""
    while True:
        try:
            await asyncio.sleep(300)  # Check every 5 minutes
            current_time = datetime.now(timezone.utc)
            expired_users = []

            for user_id, state in self.user_states.items():
                # Expire after 30 minutes of inactivity
                if (current_time - state.started_at).total_seconds() > 1800:
                    expired_users.append(user_id)

            for user_id in expired_users:
                await self._cleanup_wizard_state(user_id, "Session expired")

        except Exception as e:
            logger.error(f"Error in cleanup task: {e}")
```

**Purpose**: Automatically cleans up abandoned wizard sessions to prevent resource leaks.

#### 2. Manual Cleanup Commands
- `!setup-cleanup`: Interactive menu for cleaning up failed operations
- `!setup-status`: Shows current setup status and active sessions

### Enhanced Panel Deployment

The `_deploy_panel` method now includes comprehensive error recovery:

1. **Prerequisite Validation**: Checks permissions and database connectivity
2. **Step-by-Step Tracking**: Each operation is tracked for rollback
3. **Atomic Execution**: All steps must succeed or all are rolled back
4. **Comprehensive Logging**: All actions and rollbacks are logged to audit channel

### Rollback Operations

#### Message Cleanup
- Fetches and deletes Discord messages created during failed operations
- Handles `NotFound` and `Forbidden` exceptions gracefully

#### Database Cleanup
- Removes panel records created during failed operations
- Logs update operations for manual review

#### Audit Logging
- Detailed rollback information sent to audit channel
- Includes operation type, panel type, timestamp, and reason

## Error Scenarios Handled

### 1. Permission Errors
- Bot lacks required permissions
- Channel access restrictions
- Missing embed links permission

### 2. Network/API Errors
- Discord API failures
- Database connection issues
- Message sending failures

### 3. Validation Errors
- Invalid channel names/IDs
- Missing guild context
- Invalid panel types

### 4. State Management Errors
- Expired wizard sessions
- Concurrent setup attempts
- Orphaned panel records

## Testing and Validation

### Data Structure Tests
- RollbackInfo creation and validation
- WizardState management
- SetupOperationError handling
- Rollback stack operations

### Error Scenario Tests
- Permission error handling
- Database error handling
- Rollback info attachment
- State validation

## Benefits

### 1. Data Consistency
- No orphaned Discord messages
- No orphaned database records
- Consistent system state

### 2. User Experience
- Clear error messages
- Automatic cleanup on failures
- Recovery options for administrators

### 3. Maintainability
- Comprehensive logging
- Structured error handling
- Easy debugging with audit trails

### 4. Reliability
- Automatic timeout handling
- Graceful degradation
- Resource cleanup

## Usage Examples

### Basic Setup with Error Recovery
```python
# The atomic context manager handles all rollback automatically
async with self._atomic_operation(f"deploy_panel_{panel_type}") as rollback_stack:
    # Step 1: Send message (tracked for rollback)
    message = await channel.send(embed=embed, view=view)
    rollback_stack.append(RollbackInfo(
        operation_type="message_sent",
        panel_type=panel_type,
        channel_id=channel.id,
        message_id=message.id,
        guild_id=guild.id,
        user_id=user_id,
    ))
    
    # Step 2: Database operations (tracked for rollback)
    panel_id = await self.bot.db.deploy_panel(...)
    rollback_stack.append(RollbackInfo(
        operation_type="panel_created",
        panel_type=panel_type,
        panel_id=panel_id,
        guild_id=guild.id,
        user_id=user_id,
    ))
    
    # If any step fails, all previous steps are automatically rolled back
```

### Manual Cleanup
```
!setup-cleanup
# Interactive menu with options:
# 1. Clean Expired States
# 2. Clean All States  
# 3. Clean Orphaned Panels
# 4. Full Cleanup
```

### Status Monitoring
```
!setup-status
# Shows:
# - Active setup sessions
# - Recent deployments
# - System status
```

## Implementation Notes

### Thread Safety
- Rollback operations use `asyncio.Lock` to prevent race conditions
- State management is protected during cleanup operations

### Performance
- Automatic cleanup runs every 5 minutes
- Rollback operations are batched for efficiency
- Minimal overhead during normal operations

### Extensibility
- Easy to add new rollback operation types
- Modular design allows for easy testing
- Consistent error handling patterns throughout

This comprehensive error recovery system ensures that the SetupCog provides a robust, reliable setup experience with automatic cleanup and clear error reporting.