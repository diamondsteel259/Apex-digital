"""Global constants for the Apex Core bot."""

from __future__ import annotations

# ============================================================================
# Database
# ============================================================================

DATABASE_MAX_RETRIES = 5
DATABASE_RETRY_BASE_DELAY_SECONDS = 1

# ============================================================================
# Rate Limiting
# ============================================================================

RATE_LIMIT_ALERT_THRESHOLD = 3  # violations before alerting staff
RATE_LIMIT_ALERT_WINDOW_SECONDS = 300  # 5 minutes
RATE_LIMIT_ALERT_COOLDOWN_SECONDS = 600  # 10 minutes between alerts

# ============================================================================
# Financial
# ============================================================================

DEFAULT_CASHBACK_PERCENT = 0.5  # 0.5% cashback on referrals

# ============================================================================
# Pagination
# ============================================================================

MAX_SELECT_OPTIONS = 25  # Discord limit for select menu options
STOREFRONT_PAGE_SIZE = 25

# ============================================================================
# Tickets
# ============================================================================

TICKET_CHANNEL_NAME_MAX_LENGTH = 95

# ============================================================================
# Timeouts
# ============================================================================

INTERACTION_TIMEOUT_SECONDS = 120  # Default for ephemeral views
PERSISTENT_VIEW_TIMEOUT = None  # Persistent views never timeout

# ============================================================================
# Time Conversion
# ============================================================================

SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 3600
SECONDS_PER_DAY = 86400

# ============================================================================
# Cooldowns (in seconds)
# ============================================================================

COOLDOWN_WALLET_PAYMENT = 30
COOLDOWN_SUBMIT_REFUND = 300  # 5 minutes
COOLDOWN_MANUAL_COMPLETE = 10
COOLDOWN_SET_REFERRAL = 86400  # 24 hours
COOLDOWN_REFUND_APPROVE = 5
COOLDOWN_REFUND_REJECT = 5
COOLDOWN_BALANCE_CHECK = 10
COOLDOWN_ORDERS_LIST = 30
COOLDOWN_INVITES_LIST = 30
COOLDOWN_STOREFRONT_PAGINATION = 30

# ============================================================================
# Rate Limits (uses per cooldown)
# ============================================================================

RATE_LIMIT_STOREFRONT_PAGINATION_MAX = 10

# ============================================================================
# Embed Limits (Discord API limits)
# ============================================================================

EMBED_DESCRIPTION_MAX_LENGTH = 4096
EMBED_FIELD_VALUE_MAX_LENGTH = 1024
EMBED_TITLE_MAX_LENGTH = 256
EMBED_FIELD_NAME_MAX_LENGTH = 256
EMBED_FOOTER_MAX_LENGTH = 2048
EMBED_AUTHOR_NAME_MAX_LENGTH = 256
EMBED_MAX_FIELDS = 25

# ============================================================================
# Currency
# ============================================================================

MIN_REFUND_AMOUNT_CENTS = 1  # $0.01
MAX_REFUND_AMOUNT_CENTS = 10_000_000  # $100,000.00
