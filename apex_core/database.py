"""Async SQLite data layer for Apex Core."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import aiosqlite

from .logger import get_logger

logger = get_logger()


class Database:
    """Async database handler using SQLite."""

    def __init__(self, db_path: str | Path = "apex_core.db", connect_timeout: float | None = None) -> None:
        self.db_path = Path(db_path)
        self._connection: Optional[aiosqlite.Connection] = None
        self._wallet_lock = asyncio.Lock()
        self.target_schema_version = 24
        
        if connect_timeout is None:
            connect_timeout = float(os.getenv("DB_CONNECT_TIMEOUT", "5.0"))
        self.connect_timeout = connect_timeout

    async def connect(self) -> None:
        """Connect to the database with timeout protection and retry logic."""
        if self._connection is None:
            max_retries = 5
            for attempt in range(max_retries + 1):
                try:
                    self._connection = await asyncio.wait_for(
                        aiosqlite.connect(str(self.db_path)),
                        timeout=self.connect_timeout
                    )

                    try:
                        self._connection.row_factory = aiosqlite.Row
                        await self._connection.execute("PRAGMA foreign_keys = ON;")
                        await self._connection.commit()
                        await self._initialize_schema()
                    except Exception as init_error:
                        if self._connection:
                            await self._connection.close()
                        self._connection = None
                        logger.error(
                            f"Failed to initialize database after connection: {init_error}. "
                            f"Database path: {self.db_path}"
                        )
                        raise

                    return

                except asyncio.TimeoutError:
                    self._connection = None
                    timeout_msg = (
                        f"Database connection timed out after {self.connect_timeout}s "
                        f"(attempt {attempt + 1}/{max_retries + 1}). Database path: {self.db_path}"
                    )
                    if attempt < max_retries:
                        wait_seconds = 2 ** attempt  # Exponential backoff: 1, 2, 4, 8, 16
                        logger.warning(f"{timeout_msg}. Waiting {wait_seconds}s before retry...")
                        await asyncio.sleep(wait_seconds)
                    else:
                        logger.error(f"{timeout_msg}. Max retries exhausted.")
                        raise TimeoutError(timeout_msg) from None

                except Exception as conn_error:
                    self._connection = None
                    error_msg = (
                        f"Failed to connect to database (attempt {attempt + 1}/{max_retries + 1}): {conn_error}. "
                        f"Database path: {self.db_path}"
                    )
                    if attempt < max_retries:
                        wait_seconds = 2 ** attempt  # Exponential backoff: 1, 2, 4, 8, 16
                        logger.warning(f"{error_msg}. Waiting {wait_seconds}s before retry...")
                        await asyncio.sleep(wait_seconds)
                    else:
                        logger.error(f"{error_msg}. Max retries exhausted.")
                        raise RuntimeError(error_msg) from conn_error

    async def close(self) -> None:
        if self._connection:
            await self._connection.close()
            self._connection = None

    async def _initialize_schema(self) -> None:
        """Initialize the database schema with versioning support."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        # Create the schema_migrations table if it doesn't exist
        await self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await self._connection.commit()

        # Get current schema version
        current_version = await self._get_current_schema_version()
        logger.info(f"Current database schema version: {current_version}")

        # Apply all pending migrations
        await self._apply_pending_migrations(current_version)

        # Log final version
        final_version = await self._get_current_schema_version()
        logger.info(f"Database schema migration complete. Final version: {final_version}")

    async def _get_current_schema_version(self) -> int:
        """Get the current schema version from the migrations table."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        cursor = await self._connection.execute(
            "SELECT MAX(version) as version FROM schema_migrations"
        )
        row = await cursor.fetchone()
        return row["version"] if row and row["version"] else 0

    async def _apply_pending_migrations(self, current_version: int) -> None:
        """Apply all pending migrations after the current version."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        # Define all migrations in order
        migrations = {
            1: ("base_schema", self._migration_v1),
            2: ("migrate_products_table", self._migration_v2),
            3: ("migrate_discounts_indexes", self._migration_v3),
            4: ("extend_tickets_schema", self._migration_v4),
            5: ("wallet_transactions_table", self._migration_v5),
            6: ("extend_orders_schema", self._migration_v6),
            7: ("transcripts_table", self._migration_v7),
            8: ("ticket_counter_table", self._migration_v8),
            9: ("refunds_table", self._migration_v9),
            10: ("referrals_table", self._migration_v10),
            11: ("permanent_messages_table", self._migration_v11),
            12: ("wallet_transactions_user_created_index", self._migration_v12),
            13: ("setup_sessions_table", self._migration_v13),
            14: ("inventory_stock_tracking", self._migration_v14),
            15: ("promo_codes_system", self._migration_v15),
            16: ("gift_system", self._migration_v16),
            17: ("announcements_table", self._migration_v17),
            18: ("orders_status_tracking", self._migration_v18),
            19: ("reviews_system", self._migration_v19),
            20: ("supplier_tracking", self._migration_v20),
            21: ("ai_support_system", self._migration_v21),
            22: ("wishlist_and_tags", self._migration_v22),
            23: ("atto_integration", self._migration_v23),
            24: ("crypto_wallets", self._migration_v24),
        }

        for version in sorted(migrations.keys()):
            if version > current_version:
                name, migration_fn = migrations[version]
                logger.info(f"Applying migration v{version}: {name}")
                try:
                    await migration_fn()
                    await self._record_migration(version, name)
                    logger.info(f"Migration v{version}: {name} applied successfully")
                except Exception as e:
                    logger.exception(
                        f"Failed to apply migration v{version} ({name}): {e}",
                        exc_info=True
                    )
                    raise RuntimeError(
                        f"Migration v{version} ({name}) failed: {e}"
                    ) from e

    async def _record_migration(self, version: int, name: str) -> None:
        """Record a migration as applied in the schema_migrations table."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        await self._connection.execute(
            "INSERT INTO schema_migrations (version, name) VALUES (?, ?)",
            (version, name),
        )
        await self._connection.commit()

    async def _migration_v1(self) -> None:
        """Migration v1: Create base schema with all core tables."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        await self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                discord_id INTEGER UNIQUE NOT NULL,
                wallet_balance_cents INTEGER NOT NULL DEFAULT 0,
                total_lifetime_spent_cents INTEGER NOT NULL DEFAULT 0,
                has_client_role INTEGER NOT NULL DEFAULT 0,
                manually_assigned_roles TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                main_category TEXT NOT NULL,
                sub_category TEXT NOT NULL,
                service_name TEXT NOT NULL,
                variant_name TEXT NOT NULL,
                price_cents INTEGER NOT NULL,
                start_time TEXT,
                duration TEXT,
                refill_period TEXT,
                additional_info TEXT,
                role_id INTEGER,
                content_payload TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS discounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                product_id INTEGER,
                vip_tier TEXT,
                discount_percent REAL NOT NULL,
                description TEXT,
                expires_at TIMESTAMP,
                is_stackable INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_discord_id INTEGER NOT NULL,
                channel_id INTEGER UNIQUE NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                last_activity TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_discord_id) REFERENCES users(discord_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_discord_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                price_paid_cents INTEGER NOT NULL,
                discount_applied_percent REAL NOT NULL DEFAULT 0,
                order_metadata TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_discord_id) REFERENCES users(discord_id) ON DELETE CASCADE,
                FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE
            );
            """
        )
        await self._connection.commit()

    async def _migration_v2(self) -> None:
        """Migration v2: Migrate products table from old schema to new schema."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        # Check if the products table has the old 'name' column
        cursor = await self._connection.execute("PRAGMA table_info(products)")
        columns = [row[1] for row in await cursor.fetchall()]

        # If the table has the old 'name' column but not the new columns, migrate it
        if "name" in columns and "main_category" not in columns:
            logger.info("Migrating products table from old schema...")

            # Create a backup of existing products
            await self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS products_backup AS 
                SELECT * FROM products
                """
            )

            # Create the new products table
            await self._connection.execute("DROP TABLE IF EXISTS products_new")

            await self._connection.execute(
                """
                CREATE TABLE products_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    main_category TEXT NOT NULL DEFAULT 'Legacy',
                    sub_category TEXT NOT NULL DEFAULT 'Service',
                    service_name TEXT NOT NULL DEFAULT 'Legacy Product',
                    variant_name TEXT NOT NULL,
                    price_cents INTEGER NOT NULL,
                    start_time TEXT,
                    duration TEXT,
                    refill_period TEXT,
                    additional_info TEXT,
                    role_id INTEGER,
                    content_payload TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            # Migrate data from old table to new table
            await self._connection.execute(
                """
                INSERT INTO products_new (
                    id, variant_name, price_cents, role_id, content_payload, 
                    is_active, created_at, updated_at
                )
                SELECT 
                    id, name, price_cents, role_id, content_payload,
                    is_active, created_at, updated_at
                FROM products
                """
            )

            # Drop old table and rename new one
            await self._connection.execute("DROP TABLE products")
            await self._connection.execute("ALTER TABLE products_new RENAME TO products")

            await self._connection.commit()
            logger.info("Products table migration completed successfully")

    async def _migration_v3(self) -> None:
        """Migration v3: Create indexes for discounts and orders tables."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        await self._connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_discounts_expires_at
                ON discounts(expires_at)
            """
        )
        await self._connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_tickets_user_status
                ON tickets(user_discord_id, status)
            """
        )
        await self._connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_orders_user
                ON orders(user_discord_id)
            """
        )
        await self._connection.commit()

    async def _migration_v4(self) -> None:
        """Migration v4: Extend tickets table with type, order_id, assigned_staff_id, closed_at, and priority columns."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        cursor = await self._connection.execute("PRAGMA table_info(tickets)")
        columns = [row[1] for row in await cursor.fetchall()]

        if "type" not in columns:
            await self._connection.execute(
                "ALTER TABLE tickets ADD COLUMN type TEXT NOT NULL DEFAULT 'support'"
            )

        if "order_id" not in columns:
            await self._connection.execute(
                "ALTER TABLE tickets ADD COLUMN order_id INTEGER"
            )

        if "assigned_staff_id" not in columns:
            await self._connection.execute(
                "ALTER TABLE tickets ADD COLUMN assigned_staff_id INTEGER"
            )

        if "closed_at" not in columns:
            await self._connection.execute(
                "ALTER TABLE tickets ADD COLUMN closed_at TIMESTAMP"
            )

        if "priority" not in columns:
            await self._connection.execute(
                "ALTER TABLE tickets ADD COLUMN priority TEXT"
            )

        await self._connection.commit()

    async def _migration_v5(self) -> None:
        """Migration v5: Create wallet_transactions table for ledger tracking."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        await self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS wallet_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_discord_id INTEGER NOT NULL,
                amount_cents INTEGER NOT NULL,
                balance_after_cents INTEGER NOT NULL,
                transaction_type TEXT NOT NULL,
                description TEXT,
                order_id INTEGER,
                ticket_id INTEGER,
                staff_discord_id INTEGER,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_discord_id) REFERENCES users(discord_id) ON DELETE CASCADE,
                FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE SET NULL,
                FOREIGN KEY(ticket_id) REFERENCES tickets(id) ON DELETE SET NULL
            )
            """
        )

        await self._connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_wallet_transactions_user
                ON wallet_transactions(user_discord_id, created_at DESC)
            """
        )

        await self._connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_wallet_transactions_type
                ON wallet_transactions(transaction_type)
            """
        )

        await self._connection.commit()

    async def _migration_v6(self) -> None:
        """Migration v6: Extend orders table with status and warranty fields."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        cursor = await self._connection.execute("PRAGMA table_info(orders)")
        columns = [row[1] for row in await cursor.fetchall()]

        if "status" not in columns:
            await self._connection.execute(
                "ALTER TABLE orders ADD COLUMN status TEXT NOT NULL DEFAULT 'pending'"
            )

        if "warranty_expires_at" not in columns:
            await self._connection.execute(
                "ALTER TABLE orders ADD COLUMN warranty_expires_at TIMESTAMP"
            )

        if "last_renewed_at" not in columns:
            await self._connection.execute(
                "ALTER TABLE orders ADD COLUMN last_renewed_at TIMESTAMP"
            )

        if "renewal_count" not in columns:
            await self._connection.execute(
                "ALTER TABLE orders ADD COLUMN renewal_count INTEGER NOT NULL DEFAULT 0"
            )

        # Create indexes for the new fields
        await self._connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_orders_status
                ON orders(status)
            """
        )

        await self._connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_orders_warranty_expiry
                ON orders(warranty_expires_at)
            """
        )

        await self._connection.commit()

    async def _migration_v7(self) -> None:
        """Migration v7: Create transcripts table for transcript persistence."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        await self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS transcripts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL,
                user_discord_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                storage_type TEXT NOT NULL,
                storage_path TEXT NOT NULL,
                file_size_bytes INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(ticket_id) REFERENCES tickets(id) ON DELETE CASCADE
            )
            """
        )

        await self._connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_transcripts_ticket
                ON transcripts(ticket_id)
            """
        )

        await self._connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_transcripts_user
                ON transcripts(user_discord_id)
            """
        )

        await self._connection.commit()

    async def _migration_v8(self) -> None:
        """Migration v8: Create ticket_counter table for unique ticket naming."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        await self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS ticket_counter (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                ticket_type TEXT NOT NULL,
                next_count INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, ticket_type)
            )
            """
        )

        await self._connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_ticket_counter_user_type
                ON ticket_counter(user_id, ticket_type)
            """
        )

        await self._connection.commit()

    async def _migration_v9(self) -> None:
        """Migration v9: Create refunds table for refund management and approval workflow."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        await self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS refunds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                user_discord_id INTEGER NOT NULL,
                requested_amount_cents INTEGER NOT NULL,
                handling_fee_cents INTEGER NOT NULL,
                final_refund_cents INTEGER NOT NULL,
                reason TEXT NOT NULL,
                proof_attachment_url TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP,
                resolved_by_staff_id INTEGER,
                rejection_reason TEXT,
                FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE,
                FOREIGN KEY(user_discord_id) REFERENCES users(discord_id) ON DELETE CASCADE,
                FOREIGN KEY(resolved_by_staff_id) REFERENCES users(discord_id) ON DELETE SET NULL
            )
            """
        )

        await self._connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_refunds_order
                ON refunds(order_id)
            """
        )

        await self._connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_refunds_user
                ON refunds(user_discord_id)
            """
        )

        await self._connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_refunds_status
                ON refunds(status)
            """
        )

        await self._connection.commit()

    async def _migration_v10(self) -> None:
        """Migration v10: Create referrals table for invite rewards tracking."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        await self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_user_id INTEGER NOT NULL,
                referred_user_id INTEGER UNIQUE NOT NULL,
                referred_total_spend_cents INTEGER DEFAULT 0,
                cashback_earned_cents INTEGER DEFAULT 0,
                cashback_paid_cents INTEGER DEFAULT 0,
                is_blacklisted INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(referrer_user_id) REFERENCES users(discord_id) ON DELETE CASCADE,
                FOREIGN KEY(referred_user_id) REFERENCES users(discord_id) ON DELETE CASCADE
            )
            """
        )

        await self._connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_referrals_referrer
                ON referrals(referrer_user_id)
            """
        )

        await self._connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_referrals_referred
                ON referrals(referred_user_id)
            """
        )

        await self._connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_referrals_blacklist
                ON referrals(is_blacklisted)
            """
        )

        await self._connection.commit()

    async def ensure_user(self, discord_id: int) -> aiosqlite.Row:
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        await self._connection.execute(
            """
            INSERT INTO users (discord_id)
            VALUES (?)
            ON CONFLICT(discord_id) DO NOTHING
            """,
            (discord_id,),
        )
        await self._connection.commit()
        row = await self.get_user(discord_id)
        if row is None:
            raise RuntimeError("Failed to create or retrieve user record.")
        return row

    async def get_user(self, discord_id: int) -> Optional[aiosqlite.Row]:
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        cursor = await self._connection.execute(
            "SELECT * FROM users WHERE discord_id = ?",
            (discord_id,),
        )
        return await cursor.fetchone()

    async def update_wallet_balance(self, discord_id: int, delta_cents: int) -> int:
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        async with self._wallet_lock:
            if self._connection is None:
                raise RuntimeError("Database connection not initialized.")

            started_transaction = False
            if not self._connection.in_transaction:
                await self._connection.execute("BEGIN IMMEDIATE;")
                started_transaction = True

            try:
                await self._connection.execute(
                    """
                    INSERT INTO users (discord_id, wallet_balance_cents)
                    VALUES (?, 0)
                    ON CONFLICT(discord_id) DO NOTHING;
                    """,
                    (discord_id,),
                )
                await self._connection.execute(
                    """
                    UPDATE users
                    SET wallet_balance_cents = wallet_balance_cents + ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE discord_id = ?;
                    """,
                    (delta_cents, discord_id),
                )
            except Exception as e:
                if started_transaction:
                    await self._connection.rollback()
                logger.error(
                    f"Failed to update wallet balance for user {discord_id}: "
                    f"delta={delta_cents} cents, error={str(e)}"
                )
                raise RuntimeError(
                    f"Failed to update wallet balance for user {discord_id}: {str(e)}"
                ) from e

            if started_transaction:
                await self._connection.commit()

            cursor = await self._connection.execute(
                "SELECT wallet_balance_cents FROM users WHERE discord_id = ?",
                (discord_id,),
            )
            row = await cursor.fetchone()
            return row["wallet_balance_cents"] if row else 0

    async def log_wallet_transaction(
        self,
        *,
        user_discord_id: int,
        amount_cents: int,
        balance_after_cents: int,
        transaction_type: str,
        description: Optional[str] = None,
        order_id: Optional[int] = None,
        ticket_id: Optional[int] = None,
        staff_discord_id: Optional[int] = None,
        metadata: Optional[str | dict] = None,
    ) -> int:
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        validated_metadata = None
        if metadata is not None:
            if isinstance(metadata, dict):
                try:
                    validated_metadata = json.dumps(metadata)
                except (TypeError, ValueError) as e:
                    logger.warning(
                        f"Failed to serialize metadata dict for user {user_discord_id}: {e}",
                        exc_info=True
                    )
                    validated_metadata = None
            else:
                try:
                    json.loads(metadata)
                    validated_metadata = metadata
                except (json.JSONDecodeError, TypeError) as e:
                    logger.warning(
                        f"Invalid JSON metadata for user {user_discord_id}: {e}",
                        exc_info=True
                    )
                    validated_metadata = None

        cursor = await self._connection.execute(
            """
            INSERT INTO wallet_transactions (
                user_discord_id, amount_cents, balance_after_cents,
                transaction_type, description, order_id, ticket_id,
                staff_discord_id, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_discord_id,
                amount_cents,
                balance_after_cents,
                transaction_type,
                description,
                order_id,
                ticket_id,
                staff_discord_id,
                validated_metadata,
            ),
        )
        await self._connection.commit()
        return cursor.lastrowid

    async def get_wallet_transactions(
        self,
        user_discord_id: int,
        *,
        limit: int = 10,
        offset: int = 0,
    ) -> list[aiosqlite.Row]:
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        cursor = await self._connection.execute(
            """
            SELECT * FROM wallet_transactions
            WHERE user_discord_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            (user_discord_id, limit, offset),
        )
        return await cursor.fetchall()

    async def count_wallet_transactions(self, user_discord_id: int) -> int:
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        cursor = await self._connection.execute(
            """
            SELECT COUNT(*) as count FROM wallet_transactions
            WHERE user_discord_id = ?
            """,
            (user_discord_id,),
        )
        row = await cursor.fetchone()
        return row["count"] if row else 0

    async def create_product(
        self,
        *,
        main_category: str,
        sub_category: str,
        service_name: str,
        variant_name: str,
        price_cents: int,
        start_time: Optional[str] = None,
        duration: Optional[str] = None,
        refill_period: Optional[str] = None,
        additional_info: Optional[str] = None,
        role_id: Optional[int] = None,
        content_payload: Optional[str] = None,
        supplier_id: Optional[str] = None,
        supplier_name: Optional[str] = None,
        supplier_service_id: Optional[str] = None,
        supplier_price_cents: Optional[int] = None,
        markup_percent: Optional[float] = None,
        supplier_api_url: Optional[str] = None,
        supplier_order_url: Optional[str] = None,
    ) -> int:
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        # Check if supplier fields exist (migration v20)
        cursor = await self._connection.execute("PRAGMA table_info(products)")
        columns = [row[1] for row in await cursor.fetchall()]
        has_supplier_fields = "supplier_id" in columns

        if has_supplier_fields:
            cursor = await self._connection.execute(
                """
                INSERT INTO products (
                    main_category, sub_category, service_name, variant_name, 
                    price_cents, start_time, duration, refill_period, additional_info,
                    role_id, content_payload,
                    supplier_id, supplier_name, supplier_service_id, supplier_price_cents,
                    markup_percent, supplier_api_url, supplier_order_url
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    main_category, sub_category, service_name, variant_name,
                    price_cents, start_time, duration, refill_period, additional_info,
                    role_id, content_payload,
                    supplier_id, supplier_name, supplier_service_id, supplier_price_cents,
                    markup_percent, supplier_api_url, supplier_order_url
                ),
            )
        else:
            # Fallback for older schema
            cursor = await self._connection.execute(
                """
                INSERT INTO products (
                    main_category, sub_category, service_name, variant_name, 
                    price_cents, start_time, duration, refill_period, additional_info,
                    role_id, content_payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    main_category, sub_category, service_name, variant_name,
                    price_cents, start_time, duration, refill_period, additional_info,
                    role_id, content_payload
                ),
            )
        await self._connection.commit()
        return cursor.lastrowid

    async def create_product_legacy(
        self,
        name: str,
        price_cents: int,
        role_id: Optional[int],
        content_payload: Optional[str],
    ) -> int:
        """Legacy method for backward compatibility."""
        return await self.create_product(
            main_category="Legacy",
            sub_category="Service", 
            service_name="Legacy Product",
            variant_name=name,
            price_cents=price_cents,
            role_id=role_id,
            content_payload=content_payload,
        )

    async def get_product(self, product_id: int) -> Optional[aiosqlite.Row]:
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        cursor = await self._connection.execute(
            "SELECT * FROM products WHERE id = ?",
            (product_id,),
        )
        return await cursor.fetchone()

    async def set_discount(
        self,
        *,
        user_id: Optional[int],
        product_id: Optional[int],
        vip_tier: Optional[str],
        discount_percent: float,
        description: str,
        expires_at: Optional[str] = None,
        is_stackable: bool = False,
    ) -> int:
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        cursor = await self._connection.execute(
            """
            INSERT INTO discounts (
                user_id, product_id, vip_tier, discount_percent, description, expires_at, is_stackable
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                product_id,
                vip_tier,
                discount_percent,
                description,
                expires_at,
                1 if is_stackable else 0,
            ),
        )
        await self._connection.commit()
        return cursor.lastrowid

    async def get_applicable_discounts(
        self,
        *,
        user_id: Optional[int],
        product_id: Optional[int],
        vip_tier: Optional[str],
    ) -> list[aiosqlite.Row]:
        """Get applicable discounts, filtering out expired ones.
        
        Returns discounts that match the user, product, and VIP tier criteria,
        but only those that haven't expired (expires_at is NULL or in the future).
        """
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        cursor = await self._connection.execute(
            """
            SELECT * FROM discounts
            WHERE (user_id IS NULL OR user_id = ?)
              AND (product_id IS NULL OR product_id = ?)
              AND (vip_tier IS NULL OR vip_tier = ?)
              AND (expires_at IS NULL OR expires_at >= CURRENT_TIMESTAMP)
            """,
            (user_id, product_id, vip_tier),
        )
        return await cursor.fetchall()

    async def get_all_products(self, *, active_only: bool = True) -> list[aiosqlite.Row]:
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        query = "SELECT * FROM products"
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY price_cents ASC"

        cursor = await self._connection.execute(query)
        return await cursor.fetchall()

    async def get_distinct_main_categories(self) -> list[str]:
        """Get all distinct main_category values from active products, sorted alphabetically."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        cursor = await self._connection.execute(
            """
            SELECT DISTINCT main_category 
            FROM products 
            WHERE is_active = 1 
            ORDER BY main_category ASC
            """
        )
        rows = await cursor.fetchall()
        return [row[0] for row in rows]

    async def get_distinct_sub_categories(self, main_category: str) -> list[str]:
        """Get all distinct sub_category values for a main_category from active products, sorted alphabetically."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        cursor = await self._connection.execute(
            """
            SELECT DISTINCT sub_category 
            FROM products 
            WHERE main_category = ? AND is_active = 1 
            ORDER BY sub_category ASC
            """,
            (main_category,),
        )
        rows = await cursor.fetchall()
        return [row[0] for row in rows]

    async def get_products_by_category(
        self, main_category: str, sub_category: str
    ) -> list[aiosqlite.Row]:
        """Get all active products for a specific main_category and sub_category combination."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        cursor = await self._connection.execute(
            """
            SELECT * FROM products 
            WHERE main_category = ? AND sub_category = ? AND is_active = 1 
            ORDER BY service_name ASC, variant_name ASC
            """,
            (main_category, sub_category),
        )
        return await cursor.fetchall()

    async def find_product_by_fields(
        self,
        *,
        main_category: str,
        sub_category: str,
        service_name: str,
        variant_name: str,
    ) -> Optional[aiosqlite.Row]:
        """Find a product by matching the four key fields."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        cursor = await self._connection.execute(
            """
            SELECT * FROM products 
            WHERE main_category = ? 
              AND sub_category = ? 
              AND service_name = ? 
              AND variant_name = ?
            """,
            (main_category, sub_category, service_name, variant_name),
        )
        return await cursor.fetchone()

    async def update_product(
        self,
        product_id: int,
        *,
        main_category: Optional[str] = None,
        sub_category: Optional[str] = None,
        service_name: Optional[str] = None,
        variant_name: Optional[str] = None,
        price_cents: Optional[int] = None,
        start_time: Optional[str] = None,
        duration: Optional[str] = None,
        refill_period: Optional[str] = None,
        additional_info: Optional[str] = None,
        role_id: Optional[int] = None,
        content_payload: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> None:
        """Update an existing product with the provided fields."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        # Build dynamic update query
        update_fields = []
        params = []
        
        field_mapping = {
            'main_category': main_category,
            'sub_category': sub_category,
            'service_name': service_name,
            'variant_name': variant_name,
            'price_cents': price_cents,
            'start_time': start_time,
            'duration': duration,
            'refill_period': refill_period,
            'additional_info': additional_info,
            'role_id': role_id,
            'content_payload': content_payload,
            'is_active': 1 if is_active else 0 if is_active is not None else None,
        }
        
        for field, value in field_mapping.items():
            if value is not None:
                update_fields.append(f"{field} = ?")
                params.append(value)
        
        if not update_fields:
            return  # Nothing to update
        
        # Add updated_at timestamp
        update_fields.append("updated_at = CURRENT_TIMESTAMP")
        params.append(product_id)
        
        query = f"""
            UPDATE products 
            SET {', '.join(update_fields)}
            WHERE id = ?
        """
        
        await self._connection.execute(query, params)
        await self._connection.commit()

    async def deactivate_all_products_except(
        self,
        active_product_ids: list[int],
    ) -> int:
        """Mark all products as inactive except those in the provided list."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        if not active_product_ids:
            # If no active products, deactivate all
            cursor = await self._connection.execute(
                "UPDATE products SET is_active = 0, updated_at = CURRENT_TIMESTAMP"
            )
        else:
            # Deactivate all except the specified IDs
            placeholders = ','.join('?' for _ in active_product_ids)
            cursor = await self._connection.execute(
                f"""
                UPDATE products 
                SET is_active = 0, updated_at = CURRENT_TIMESTAMP
                WHERE id NOT IN ({placeholders})
                """,
                active_product_ids,
            )
        
        await self._connection.commit()
        return cursor.rowcount

    async def mark_client_role_assigned(self, discord_id: int) -> None:
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        await self._connection.execute(
            """
            UPDATE users
            SET has_client_role = 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE discord_id = ?
            """,
            (discord_id,),
        )
        await self._connection.commit()

    async def get_manually_assigned_roles(self, discord_id: int) -> list[str]:
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        cursor = await self._connection.execute(
            "SELECT manually_assigned_roles FROM users WHERE discord_id = ?",
            (discord_id,),
        )
        row = await cursor.fetchone()
        if not row or not row["manually_assigned_roles"]:
            return []

        import json
        try:
            return json.loads(row["manually_assigned_roles"])
        except (json.JSONDecodeError, TypeError):
            return []

    async def add_manually_assigned_role(self, discord_id: int, role_name: str) -> None:
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        import json
        
        async with self._wallet_lock:
            cursor = await self._connection.execute(
                "SELECT manually_assigned_roles FROM users WHERE discord_id = ?",
                (discord_id,),
            )
            row = await cursor.fetchone()
            
            roles = []
            if row and row["manually_assigned_roles"]:
                try:
                    roles = json.loads(row["manually_assigned_roles"])
                except (json.JSONDecodeError, TypeError):
                    roles = []
            
            if role_name not in roles:
                roles.append(role_name)
            
            await self._connection.execute(
                """
                UPDATE users
                SET manually_assigned_roles = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE discord_id = ?
                """,
                (json.dumps(roles), discord_id),
            )
            await self._connection.commit()

    async def remove_manually_assigned_role(self, discord_id: int, role_name: str) -> None:
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        import json
        
        async with self._wallet_lock:
            cursor = await self._connection.execute(
                "SELECT manually_assigned_roles FROM users WHERE discord_id = ?",
                (discord_id,),
            )
            row = await cursor.fetchone()
            
            roles = []
            if row and row["manually_assigned_roles"]:
                try:
                    roles = json.loads(row["manually_assigned_roles"])
                except (json.JSONDecodeError, TypeError):
                    roles = []
            
            if role_name in roles:
                roles.remove(role_name)
            
            await self._connection.execute(
                """
                UPDATE users
                SET manually_assigned_roles = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE discord_id = ?
                """,
                (json.dumps(roles) if roles else None, discord_id),
            )
            await self._connection.commit()

    async def create_ticket(
        self,
        *,
        user_discord_id: int,
        channel_id: int,
        status: str = "open",
        ticket_type: str = "support",
        order_id: Optional[int] = None,
        assigned_staff_id: Optional[int] = None,
        priority: Optional[str] = None,
    ) -> int:
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        cursor = await self._connection.execute(
            """
            INSERT INTO tickets (
                user_discord_id, channel_id, status, type, order_id, 
                assigned_staff_id, priority
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_discord_id,
                channel_id,
                status,
                ticket_type,
                order_id,
                assigned_staff_id,
                priority,
            ),
        )
        await self._connection.commit()
        return cursor.lastrowid

    async def get_open_ticket_for_user(self, user_discord_id: int) -> Optional[aiosqlite.Row]:
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        cursor = await self._connection.execute(
            """
            SELECT *
            FROM tickets
            WHERE user_discord_id = ? AND status = 'open'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (user_discord_id,),
        )
        return await cursor.fetchone()

    async def get_ticket_by_channel(self, channel_id: int) -> Optional[aiosqlite.Row]:
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        cursor = await self._connection.execute(
            "SELECT * FROM tickets WHERE channel_id = ?",
            (channel_id,),
        )
        return await cursor.fetchone()

    async def update_ticket_status(
        self, channel_id: int, status: str, *, update_activity: bool = False
    ) -> None:
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        if update_activity:
            await self._connection.execute(
                """
                UPDATE tickets
                SET status = ?,
                    last_activity = CURRENT_TIMESTAMP
                WHERE channel_id = ?
                """,
                (status, channel_id),
            )
        else:
            await self._connection.execute(
                """
                UPDATE tickets
                SET status = ?
                WHERE channel_id = ?
                """,
                (status, channel_id),
            )
        await self._connection.commit()

    async def touch_ticket_activity(self, channel_id: int) -> None:
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        await self._connection.execute(
            """
            UPDATE tickets
            SET last_activity = CURRENT_TIMESTAMP
            WHERE channel_id = ?
            """,
            (channel_id,),
        )
        await self._connection.commit()

    async def get_open_tickets(self) -> list[aiosqlite.Row]:
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        cursor = await self._connection.execute(
            """
            SELECT *
            FROM tickets
            WHERE status = 'open'
            ORDER BY last_activity ASC
            """
        )
        return await cursor.fetchall()

    async def update_ticket(
        self,
        channel_id: int,
        *,
        status: Optional[str] = None,
        ticket_type: Optional[str] = None,
        order_id: Optional[int] = None,
        assigned_staff_id: Optional[int] = None,
        priority: Optional[str] = None,
        closed_at: Optional[str] = None,
    ) -> None:
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        update_fields = []
        params = []

        if status is not None:
            update_fields.append("status = ?")
            params.append(status)

        if ticket_type is not None:
            update_fields.append("type = ?")
            params.append(ticket_type)

        if order_id is not None:
            update_fields.append("order_id = ?")
            params.append(order_id)

        if assigned_staff_id is not None:
            update_fields.append("assigned_staff_id = ?")
            params.append(assigned_staff_id)

        if priority is not None:
            update_fields.append("priority = ?")
            params.append(priority)

        if closed_at is not None:
            update_fields.append("closed_at = ?")
            params.append(closed_at)

        if not update_fields:
            return

        params.append(channel_id)
        query = f"""
            UPDATE tickets
            SET {', '.join(update_fields)}
            WHERE channel_id = ?
        """

        await self._connection.execute(query, params)
        await self._connection.commit()

    async def get_next_ticket_count(self, user_id: int, ticket_type: str) -> int:
        """Get the next ticket count for a user and ticket type, incrementing the counter."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        async with self._wallet_lock:
            await self._connection.execute("BEGIN IMMEDIATE;")
            
            cursor = await self._connection.execute(
                """
                SELECT next_count FROM ticket_counter
                WHERE user_id = ? AND ticket_type = ?
                """,
                (user_id, ticket_type),
            )
            row = await cursor.fetchone()
            
            if row:
                count = row["next_count"]
                await self._connection.execute(
                    """
                    UPDATE ticket_counter
                    SET next_count = next_count + 1,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ? AND ticket_type = ?
                    """,
                    (user_id, ticket_type),
                )
            else:
                count = 1
                await self._connection.execute(
                    """
                    INSERT INTO ticket_counter (user_id, ticket_type, next_count)
                    VALUES (?, ?, ?)
                    """,
                    (user_id, ticket_type, 2),
                )
            
            await self._connection.commit()
            return count

    async def create_ticket_with_counter(
        self,
        *,
        user_discord_id: int,
        channel_id: int,
        status: str = "open",
        ticket_type: str = "support",
        order_id: Optional[int] = None,
        assigned_staff_id: Optional[int] = None,
        priority: Optional[str] = None,
    ) -> tuple[int, int]:
        """Create a ticket and return both ticket_id and the counter used.
        
        Returns:
            Tuple of (ticket_id, counter_value)
        """
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        counter = await self.get_next_ticket_count(user_discord_id, ticket_type)
        
        ticket_id = await self.create_ticket(
            user_discord_id=user_discord_id,
            channel_id=channel_id,
            status=status,
            ticket_type=ticket_type,
            order_id=order_id,
            assigned_staff_id=assigned_staff_id,
            priority=priority,
        )
        
        return ticket_id, counter

    async def create_order(
        self,
        *,
        user_discord_id: int,
        product_id: int,
        price_paid_cents: int,
        discount_applied_percent: float,
        order_metadata: Optional[str] = None,
        status: str = "pending",
        warranty_expires_at: Optional[str] = None,
    ) -> int:
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        cursor = await self._connection.execute(
            """
            INSERT INTO orders (
                user_discord_id, product_id, price_paid_cents, 
                discount_applied_percent, order_metadata, status,
                warranty_expires_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_discord_id,
                product_id,
                price_paid_cents,
                discount_applied_percent,
                order_metadata,
                status,
                warranty_expires_at,
            ),
        )
        await self._connection.commit()
        return cursor.lastrowid

    async def create_manual_order(
        self,
        *,
        user_discord_id: int,
        product_name: str,
        price_paid_cents: int,
        notes: Optional[str] = None,
    ) -> tuple[int, int]:
        """
        Create a manual order without affecting wallet balance.
        
        Args:
            user_discord_id: Discord user ID
            product_name: Name of the product (for logging)
            price_paid_cents: Amount paid in cents
            notes: Additional notes about the order
        
        Returns:
            Tuple of (order_id, new_lifetime_spend_cents)
        """
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        async with self._wallet_lock:
            await self._connection.execute("BEGIN IMMEDIATE;")
            
            # Ensure user exists
            await self.ensure_user(user_discord_id)
            
            # Update lifetime spend only (not wallet balance)
            await self._connection.execute(
                """
                UPDATE users
                SET total_lifetime_spent_cents = total_lifetime_spent_cents + ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE discord_id = ?
                """,
                (price_paid_cents, user_discord_id),
            )
            
            # Create order record with a dummy product_id (0 for manual orders)
            import json
            order_metadata = json.dumps({
                "product_name": product_name,
                "manual_order": True,
                "notes": notes,
            })
            
            cursor = await self._connection.execute(
                """
                INSERT INTO orders (
                    user_discord_id, product_id, price_paid_cents,
                    discount_applied_percent, order_metadata, status
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    user_discord_id,
                    0,  # product_id = 0 for manual orders
                    price_paid_cents,
                    0.0,  # No discount for manual orders
                    order_metadata,
                    "pending",  # Default status for manual orders
                ),
            )
            order_id = cursor.lastrowid
            
            await self._connection.commit()
            
            # Get updated lifetime spend
            cursor = await self._connection.execute(
                "SELECT total_lifetime_spent_cents FROM users WHERE discord_id = ?",
                (user_discord_id,),
            )
            row = await cursor.fetchone()
            new_lifetime_spend = row["total_lifetime_spent_cents"] if row else 0
            
            # Log referral cashback if user was referred
            try:
                await self.log_referral_purchase(user_discord_id, order_id, price_paid_cents)
            except Exception as e:
                logger.error(f"Error logging referral purchase for user {user_discord_id}: {e}")
            
            return order_id, new_lifetime_spend

    async def bulk_upsert_products(
        self,
        products_to_add: list[dict],
        products_to_update: list[dict],
        product_ids_to_keep_active: list[int],
    ) -> tuple[int, int, int]:
        """Perform bulk insert/update/deactivate of products in a single transaction.

        Args:
            products_to_add: List of dicts with fields for new products
            products_to_update: List of dicts with 'id' and update fields
            product_ids_to_keep_active: List of product IDs to keep active (others deactivated)

        Returns:
            Tuple of (added_count, updated_count, deactivated_count)
        """
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        await self._connection.execute("BEGIN IMMEDIATE;")
        try:
            added_count = 0
            updated_count = 0
            deactivated_count = 0

            for product in products_to_add:
                await self._connection.execute(
                    """
                    INSERT INTO products (
                        main_category, sub_category, service_name, variant_name,
                        price_cents, start_time, duration, refill_period, additional_info,
                        role_id, content_payload
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        product.get('main_category'),
                        product.get('sub_category'),
                        product.get('service_name'),
                        product.get('variant_name'),
                        product.get('price_cents'),
                        product.get('start_time'),
                        product.get('duration'),
                        product.get('refill_period'),
                        product.get('additional_info'),
                        product.get('role_id'),
                        product.get('content_payload'),
                    ),
                )
                added_count += 1

            for product in products_to_update:
                product_id = product.pop('id')
                update_fields = []
                params = []

                for field, value in product.items():
                    if value is not None:
                        update_fields.append(f"{field} = ?")
                        params.append(value)

                if update_fields:
                    update_fields.append("updated_at = CURRENT_TIMESTAMP")
                    params.append(product_id)

                    query = f"""
                        UPDATE products
                        SET {', '.join(update_fields)}
                        WHERE id = ?
                    """
                    await self._connection.execute(query, params)
                    updated_count += 1

            if not product_ids_to_keep_active:
                cursor = await self._connection.execute(
                    "UPDATE products SET is_active = 0, updated_at = CURRENT_TIMESTAMP"
                )
            else:
                placeholders = ','.join('?' for _ in product_ids_to_keep_active)
                cursor = await self._connection.execute(
                    f"""
                    UPDATE products
                    SET is_active = 0, updated_at = CURRENT_TIMESTAMP
                    WHERE id NOT IN ({placeholders})
                    """,
                    product_ids_to_keep_active,
                )
            deactivated_count = cursor.rowcount

            await self._connection.commit()
            return added_count, updated_count, deactivated_count
        except Exception:
            await self._connection.rollback()
            raise

    async def purchase_product(
        self,
        *,
        user_discord_id: int,
        product_id: int,
        price_paid_cents: int,
        discount_applied_percent: float,
        order_metadata: Optional[str] = None,
    ) -> tuple[int, int]:
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        async with self._wallet_lock:
            await self._connection.execute("BEGIN IMMEDIATE;")

            cursor = await self._connection.execute(
                "SELECT wallet_balance_cents FROM users WHERE discord_id = ?",
                (user_discord_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                await self._connection.rollback()
                raise ValueError("User not found")

            current_balance = row["wallet_balance_cents"]
            if current_balance < price_paid_cents:
                await self._connection.rollback()
                raise ValueError("Insufficient balance")

            await self._connection.execute(
                """
                UPDATE users
                SET wallet_balance_cents = wallet_balance_cents - ?,
                    total_lifetime_spent_cents = total_lifetime_spent_cents + ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE discord_id = ?
                """,
                (price_paid_cents, price_paid_cents, user_discord_id),
            )

            cursor = await self._connection.execute(
                """
                INSERT INTO orders (
                    user_discord_id, product_id, price_paid_cents,
                    discount_applied_percent, order_metadata, status
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    user_discord_id,
                    product_id,
                    price_paid_cents,
                    discount_applied_percent,
                    order_metadata,
                    "pending",  # Default status for new orders
                ),
            )
            order_id = cursor.lastrowid

            cursor = await self._connection.execute(
                "SELECT wallet_balance_cents FROM users WHERE discord_id = ?",
                (user_discord_id,),
            )
            row = await cursor.fetchone()
            new_balance = row["wallet_balance_cents"] if row else 0

            await self._connection.execute(
                """
                INSERT INTO wallet_transactions (
                    user_discord_id, amount_cents, balance_after_cents,
                    transaction_type, description, order_id, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_discord_id,
                    -price_paid_cents,
                    new_balance,
                    "purchase",
                    f"Purchase of product #{product_id}",
                    order_id,
                    order_metadata,
                ),
            )

            await self._connection.commit()

            # Log referral cashback if user was referred
            try:
                await self.log_referral_purchase(user_discord_id, order_id, price_paid_cents)
            except Exception as e:
                logger.error(f"Error logging referral purchase for user {user_discord_id}: {e}")

            return order_id, new_balance

    async def get_orders_for_user(
        self,
        user_discord_id: int,
        *,
        limit: int = 10,
        offset: int = 0,
    ) -> list[aiosqlite.Row]:
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        cursor = await self._connection.execute(
            """
            SELECT * FROM orders
            WHERE user_discord_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            (user_discord_id, limit, offset),
        )
        return await cursor.fetchall()

    async def count_orders_for_user(self, user_discord_id: int) -> int:
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        cursor = await self._connection.execute(
            """
            SELECT COUNT(*) as count FROM orders
            WHERE user_discord_id = ?
            """,
            (user_discord_id,),
        )
        row = await cursor.fetchone()
        return row["count"] if row else 0

    async def get_order_by_id(self, order_id: int) -> Optional[aiosqlite.Row]:
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        cursor = await self._connection.execute(
            "SELECT * FROM orders WHERE id = ?",
            (order_id,),
        )
        return await cursor.fetchone()

    async def get_ticket_by_order_id(self, order_id: int) -> Optional[aiosqlite.Row]:
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        cursor = await self._connection.execute(
            "SELECT * FROM tickets WHERE order_id = ?",
            (order_id,),
        )
        return await cursor.fetchone()

    # Removed duplicate update_order_status

    async def renew_order_warranty(
        self, 
        order_id: int, 
        warranty_expires_at: str,
        staff_discord_id: Optional[int] = None
    ) -> None:
        """Renew an order's warranty and update renewal tracking."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        await self._connection.execute("BEGIN IMMEDIATE;")
        
        try:
            # Update warranty and renewal info
            await self._connection.execute(
                """
                UPDATE orders 
                SET warranty_expires_at = ?,
                    last_renewed_at = CURRENT_TIMESTAMP,
                    renewal_count = renewal_count + 1
                WHERE id = ?
                """,
                (warranty_expires_at, order_id),
            )

            # Log the renewal in wallet transactions
            cursor = await self._connection.execute(
                "SELECT user_discord_id FROM orders WHERE id = ?",
                (order_id,),
            )
            order_row = await cursor.fetchone()
            if order_row:
                await self.log_wallet_transaction(
                    user_discord_id=order_row["user_discord_id"],
                    amount_cents=0,
                    balance_after_cents=0,  # Not applicable for warranty renewal
                    transaction_type="warranty_renewal",
                    description=f"Warranty renewal for order #{order_id}",
                    order_id=order_id,
                    staff_discord_id=staff_discord_id,
                    metadata=f'{{"renewal_date": "{warranty_expires_at}"}}',
                )

            await self._connection.commit()
        except Exception:
            await self._connection.rollback()
            raise

    async def get_orders_expiring_soon(self, days_ahead: int = 7) -> list[aiosqlite.Row]:
        """Get orders with warranties expiring within the specified number of days."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        cursor = await self._connection.execute(
            """
            SELECT o.*, u.discord_id as user_discord_id
            FROM orders o
            JOIN users u ON o.user_discord_id = u.discord_id
            WHERE o.warranty_expires_at IS NOT NULL
              AND o.warranty_expires_at <= datetime('now', '+' || ? || ' days')
              AND o.warranty_expires_at > datetime('now')
              AND o.status IN ('fulfilled', 'refill')
            ORDER BY o.warranty_expires_at ASC
            """,
            (days_ahead,),
        )
        return await cursor.fetchall()

    async def get_active_orders(self, user_discord_id: Optional[int] = None) -> list[aiosqlite.Row]:
        """Get orders that are currently active (not refunded)."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        if user_discord_id:
            cursor = await self._connection.execute(
                """
                SELECT * FROM orders
                WHERE user_discord_id = ? AND status != 'refunded'
                ORDER BY created_at DESC
                """,
                (user_discord_id,),
            )
        else:
            cursor = await self._connection.execute(
                """
                SELECT * FROM orders
                WHERE status != 'refunded'
                ORDER BY created_at DESC
                """
            )
        return await cursor.fetchall()

    async def save_transcript(
        self,
        *,
        ticket_id: int,
        user_discord_id: int,
        channel_id: int,
        storage_type: str,
        storage_path: str,
        file_size_bytes: Optional[int] = None,
    ) -> int:
        """Save transcript metadata to the database."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        cursor = await self._connection.execute(
            """
            INSERT INTO transcripts (
                ticket_id, user_discord_id, channel_id,
                storage_type, storage_path, file_size_bytes
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (ticket_id, user_discord_id, channel_id, storage_type, storage_path, file_size_bytes),
        )
        await self._connection.commit()
        return cursor.lastrowid

    async def get_transcript_by_ticket_id(self, ticket_id: int) -> Optional[aiosqlite.Row]:
        """Get transcript metadata for a specific ticket."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        cursor = await self._connection.execute(
            "SELECT * FROM transcripts WHERE ticket_id = ? ORDER BY created_at DESC LIMIT 1",
            (ticket_id,),
        )
        return await cursor.fetchone()

    async def get_transcripts_by_user(self, user_discord_id: int) -> list[aiosqlite.Row]:
        """Get all transcript metadata for a specific user."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        cursor = await self._connection.execute(
            "SELECT * FROM transcripts WHERE user_discord_id = ? ORDER BY created_at DESC",
            (user_discord_id,),
        )
        return await cursor.fetchall()

    # Refund Management Methods
    
    async def create_refund_request(
        self,
        order_id: int,
        user_discord_id: int,
        amount_cents: int,
        reason: str,
        proof_attachment_url: Optional[str] = None,
        handling_fee_percent: float = 10.0,
    ) -> int:
        """Create a refund request with calculated handling fee."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        handling_fee_cents = int(amount_cents * handling_fee_percent / 100)
        final_refund_cents = amount_cents - handling_fee_cents

        cursor = await self._connection.execute(
            """
            INSERT INTO refunds (
                order_id, user_discord_id, requested_amount_cents,
                handling_fee_cents, final_refund_cents, reason,
                proof_attachment_url, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
            """,
            (
                order_id,
                user_discord_id,
                amount_cents,
                handling_fee_cents,
                final_refund_cents,
                reason,
                proof_attachment_url,
            ),
        )
        await self._connection.commit()
        return cursor.lastrowid

    async def approve_refund(
        self,
        refund_id: int,
        staff_discord_id: int,
        approved_amount_cents: Optional[int] = None,
        handling_fee_percent: float = 10.0,
    ) -> None:
        """Approve a refund and credit user wallet."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        await self._connection.execute("BEGIN IMMEDIATE;")

        try:
            # Get refund details
            cursor = await self._connection.execute(
                "SELECT * FROM refunds WHERE id = ? AND status = 'pending'",
                (refund_id,),
            )
            refund_row = await cursor.fetchone()
            if not refund_row:
                await self._connection.rollback()
                raise ValueError("Refund not found or already processed")

            # Use approved amount or original requested amount
            final_amount_cents = approved_amount_cents or refund_row["requested_amount_cents"]
            handling_fee_cents = int(final_amount_cents * handling_fee_percent / 100)
            final_refund_cents = final_amount_cents - handling_fee_cents

            # Update refund status
            await self._connection.execute(
                """
                UPDATE refunds 
                SET status = 'approved',
                    resolved_at = CURRENT_TIMESTAMP,
                    resolved_by_staff_id = ?,
                    handling_fee_cents = ?,
                    final_refund_cents = ?
                WHERE id = ?
                """,
                (staff_discord_id, handling_fee_cents, final_refund_cents, refund_id),
            )

            # Credit user wallet
            await self.update_wallet_balance(refund_row["user_discord_id"], final_refund_cents)

            # Get updated balance for transaction log
            cursor = await self._connection.execute(
                "SELECT wallet_balance_cents FROM users WHERE discord_id = ?",
                (refund_row["user_discord_id"],),
            )
            user_row = await cursor.fetchone()
            balance_after = user_row["wallet_balance_cents"] if user_row else 0

            # Log transaction
            await self.log_wallet_transaction(
                user_discord_id=refund_row["user_discord_id"],
                amount_cents=final_refund_cents,
                balance_after_cents=balance_after,
                transaction_type="refund",
                description=f"Refund for order #{refund_row['order_id']}",
                order_id=refund_row["order_id"],
                staff_discord_id=staff_discord_id,
                metadata=f'{{"refund_id": {refund_id}, "handling_fee_cents": {handling_fee_cents}}}',
            )

            await self._connection.commit()
        except Exception:
            await self._connection.rollback()
            raise

    async def reject_refund(
        self,
        refund_id: int,
        staff_discord_id: int,
        rejection_reason: str,
    ) -> None:
        """Reject a refund request."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        cursor = await self._connection.execute(
            """
            UPDATE refunds 
            SET status = 'rejected',
                resolved_at = CURRENT_TIMESTAMP,
                resolved_by_staff_id = ?,
                rejection_reason = ?
            WHERE id = ? AND status = 'pending'
            """,
            (staff_discord_id, rejection_reason, refund_id),
        )
        await self._connection.commit()

    async def get_user_refunds(
        self,
        user_discord_id: int,
        status: Optional[str] = None,
    ) -> list[aiosqlite.Row]:
        """Get refund requests for a user, optionally filtered by status."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        if status:
            cursor = await self._connection.execute(
                """
                SELECT r.*, o.created_at as order_date
                FROM refunds r
                JOIN orders o ON r.order_id = o.id
                WHERE r.user_discord_id = ? AND r.status = ?
                ORDER BY r.created_at DESC
                """,
                (user_discord_id, status),
            )
        else:
            cursor = await self._connection.execute(
                """
                SELECT r.*, o.created_at as order_date
                FROM refunds r
                JOIN orders o ON r.order_id = o.id
                WHERE r.user_discord_id = ?
                ORDER BY r.created_at DESC
                """,
                (user_discord_id,),
            )
        return await cursor.fetchall()

    async def get_refund_by_id(self, refund_id: int) -> Optional[aiosqlite.Row]:
        """Get a specific refund by ID."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        cursor = await self._connection.execute(
            """
            SELECT r.*, o.created_at as order_date, p.service_name, p.variant_name
            FROM refunds r
            JOIN orders o ON r.order_id = o.id
            JOIN products p ON o.product_id = p.id
            WHERE r.id = ?
            """,
            (refund_id,),
        )
        return await cursor.fetchone()

    async def get_pending_refunds(self) -> list[aiosqlite.Row]:
        """Get all pending refund requests for staff review."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        cursor = await self._connection.execute(
            """
            SELECT r.*, o.created_at as order_date, p.service_name, p.variant_name
            FROM refunds r
            JOIN orders o ON r.order_id = o.id
            JOIN products p ON o.product_id = p.id
            WHERE r.status = 'pending'
            ORDER BY r.created_at ASC
            """
        )
        return await cursor.fetchall()

    async def validate_order_for_refund(
        self,
        order_id: int,
        user_discord_id: int,
        max_days: int = 3,
    ) -> Optional[aiosqlite.Row]:
        """Validate that an order belongs to the user and is within the refund window."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        cursor = await self._connection.execute(
            """
            SELECT o.*, p.service_name, p.variant_name
            FROM orders o
            JOIN products p ON o.product_id = p.id
            WHERE o.id = ? 
              AND o.user_discord_id = ?
              AND o.status IN ('fulfilled', 'refill')
              AND o.created_at >= datetime('now', '-' || ? || ' days')
            """,
            (order_id, user_discord_id, max_days),
        )
        return await cursor.fetchone()

    async def create_referral(self, referrer_id: int, referred_id: int) -> int:
        """Create a referral link between referrer and referred user.
        
        Args:
            referrer_id: Discord ID of the user who referred someone
            referred_id: Discord ID of the user who was referred
            
        Returns:
            The referral record ID
            
        Raises:
            RuntimeError: If the referral already exists or if self-referral is attempted
        """
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        if referrer_id == referred_id:
            raise RuntimeError("Users cannot refer themselves")

        # Ensure both users exist
        await self.ensure_user(referrer_id)
        await self.ensure_user(referred_id)

        # Check if referred user already has a referrer
        cursor = await self._connection.execute(
            "SELECT id FROM referrals WHERE referred_user_id = ?",
            (referred_id,),
        )
        existing = await cursor.fetchone()
        if existing:
            raise RuntimeError("This user has already been referred by someone")

        cursor = await self._connection.execute(
            """
            INSERT INTO referrals (referrer_user_id, referred_user_id)
            VALUES (?, ?)
            """,
            (referrer_id, referred_id),
        )
        await self._connection.commit()
        return cursor.lastrowid

    async def log_referral_purchase(
        self, referred_id: int, order_id: int, amount_cents: int, cashback_percent: float = 0.5
    ) -> Optional[int]:
        """Log a purchase by a referred user and update cashback.

        Args:
            referred_id: Discord ID of the user who made the purchase
            order_id: The order ID
            amount_cents: Amount of the purchase in cents
            cashback_percent: Cashback percentage (default: 0.5 for 0.5%)

        Returns:
            The cashback amount in cents if applicable, None if no referral or blacklisted
        """
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        # Get the referral record
        cursor = await self._connection.execute(
            """
            SELECT id, referrer_user_id, is_blacklisted
            FROM referrals
            WHERE referred_user_id = ?
            """,
            (referred_id,),
        )
        referral = await cursor.fetchone()

        if not referral:
            return None

        if referral["is_blacklisted"]:
            logger.info(f"Referral for user {referred_id} is blacklisted, skipping cashback")
            return None

        # Calculate cashback based on configuration
        cashback_cents = int(amount_cents * (cashback_percent / 100))

        # Update the referral record
        await self._connection.execute(
            """
            UPDATE referrals
            SET referred_total_spend_cents = referred_total_spend_cents + ?,
                cashback_earned_cents = cashback_earned_cents + ?
            WHERE referred_user_id = ?
            """,
            (amount_cents, cashback_cents, referred_id),
        )
        await self._connection.commit()

        logger.info(
            f"Referral cashback logged: {cashback_cents} cents for referrer "
            f"{referral['referrer_user_id']} from order {order_id}"
        )

        return cashback_cents

    async def get_referral_stats(self, referrer_id: int) -> dict:
        """Get referral statistics for a user.
        
        Args:
            referrer_id: Discord ID of the referrer
            
        Returns:
            Dictionary with referral stats including:
            - referral_count: Number of users referred
            - total_spend_cents: Total amount spent by referred users
            - total_earned_cents: Total cashback earned
            - total_paid_cents: Total cashback already paid out
            - pending_cents: Cashback earned but not yet paid
        """
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        cursor = await self._connection.execute(
            """
            SELECT 
                COUNT(*) as referral_count,
                COALESCE(SUM(referred_total_spend_cents), 0) as total_spend_cents,
                COALESCE(SUM(cashback_earned_cents), 0) as total_earned_cents,
                COALESCE(SUM(cashback_paid_cents), 0) as total_paid_cents
            FROM referrals
            WHERE referrer_user_id = ? AND is_blacklisted = 0
            """,
            (referrer_id,),
        )
        row = await cursor.fetchone()

        if not row:
            return {
                "referral_count": 0,
                "total_spend_cents": 0,
                "total_earned_cents": 0,
                "total_paid_cents": 0,
                "pending_cents": 0,
            }

        total_earned = row["total_earned_cents"]
        total_paid = row["total_paid_cents"]
        pending = total_earned - total_paid

        return {
            "referral_count": row["referral_count"],
            "total_spend_cents": row["total_spend_cents"],
            "total_earned_cents": total_earned,
            "total_paid_cents": total_paid,
            "pending_cents": pending,
        }

    async def calculate_pending_cashback(self, referrer_id: int) -> int:
        """Calculate the pending (unpaid) cashback for a referrer.
        
        Args:
            referrer_id: Discord ID of the referrer
            
        Returns:
            Pending cashback amount in cents
        """
        stats = await self.get_referral_stats(referrer_id)
        return stats["pending_cents"]

    async def get_referrals(self, referrer_id: int) -> list[aiosqlite.Row]:
        """Get all referrals for a user with details.
        
        Args:
            referrer_id: Discord ID of the referrer
            
        Returns:
            List of referral records
        """
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        cursor = await self._connection.execute(
            """
            SELECT *
            FROM referrals
            WHERE referrer_user_id = ?
            ORDER BY created_at DESC
            """,
            (referrer_id,),
        )
        return await cursor.fetchall()

    async def blacklist_referral_user(self, user_id: int) -> bool:
        """Mark a user as blacklisted for referrals.
        
        Args:
            user_id: Discord ID of the user to blacklist
            
        Returns:
            True if user was blacklisted, False if no referral records found
        """
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        cursor = await self._connection.execute(
            """
            UPDATE referrals
            SET is_blacklisted = 1
            WHERE referrer_user_id = ?
            """,
            (user_id,),
        )
        await self._connection.commit()
        
        return cursor.rowcount > 0

    async def get_referrer_for_user(self, referred_id: int) -> Optional[int]:
        """Get the referrer Discord ID for a referred user.
        
        Args:
            referred_id: Discord ID of the referred user
            
        Returns:
            Discord ID of the referrer, or None if user wasn't referred
        """
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        cursor = await self._connection.execute(
            """
            SELECT referrer_user_id
            FROM referrals
            WHERE referred_user_id = ?
            """,
            (referred_id,),
        )
        row = await cursor.fetchone()
        return row["referrer_user_id"] if row else None

    async def get_all_pending_referral_cashbacks(self) -> list[dict]:
        """Get all referrers with pending cashback (earned > paid), grouped by referrer.
        
        Returns:
            List of dicts with referrer_id, pending_cents, referral_count
        """
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        cursor = await self._connection.execute(
            """
            SELECT 
                referrer_user_id,
                COUNT(*) as referral_count,
                SUM(cashback_earned_cents - cashback_paid_cents) as pending_cents
            FROM referrals
            WHERE is_blacklisted = 0
              AND (cashback_earned_cents - cashback_paid_cents) > 0
            GROUP BY referrer_user_id
            HAVING pending_cents > 0
            ORDER BY pending_cents DESC
            """
        )
        rows = await cursor.fetchall()
        
        return [
            {
                "referrer_id": row["referrer_user_id"],
                "pending_cents": row["pending_cents"],
                "referral_count": row["referral_count"],
            }
            for row in rows
        ]

    async def get_pending_cashback_for_user(self, referrer_id: int) -> dict:
        """Get pending cashback details for a specific referrer.
        
        Args:
            referrer_id: Discord ID of the referrer
            
        Returns:
            Dict with pending_cents, referral_count, is_blacklisted, referral_details
        """
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        # Get aggregated stats
        cursor = await self._connection.execute(
            """
            SELECT 
                COUNT(*) as referral_count,
                SUM(cashback_earned_cents - cashback_paid_cents) as pending_cents,
                MAX(is_blacklisted) as is_blacklisted
            FROM referrals
            WHERE referrer_user_id = ?
              AND (cashback_earned_cents - cashback_paid_cents) > 0
            """,
            (referrer_id,),
        )
        row = await cursor.fetchone()
        
        if not row or row["pending_cents"] is None or row["pending_cents"] <= 0:
            return {
                "pending_cents": 0,
                "referral_count": 0,
                "is_blacklisted": False,
                "referral_details": [],
            }
        
        # Get individual referral details
        cursor = await self._connection.execute(
            """
            SELECT 
                referred_user_id,
                cashback_earned_cents - cashback_paid_cents as pending_cents
            FROM referrals
            WHERE referrer_user_id = ?
              AND is_blacklisted = 0
              AND (cashback_earned_cents - cashback_paid_cents) > 0
            """,
            (referrer_id,),
        )
        referral_details = await cursor.fetchall()
        
        return {
            "pending_cents": row["pending_cents"],
            "referral_count": row["referral_count"],
            "is_blacklisted": bool(row["is_blacklisted"]),
            "referral_details": [
                {
                    "user_id": r["referred_user_id"],
                    "amount_cents": r["pending_cents"],
                }
                for r in referral_details
            ],
        }

    async def mark_cashback_paid(self, referrer_id: int, amount_cents: int) -> None:
        """Update referrals table to mark cashback as paid for a referrer.
        
        Args:
            referrer_id: Discord ID of the referrer
            amount_cents: Amount being paid out
        """
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        await self._connection.execute(
            """
            UPDATE referrals
            SET cashback_paid_cents = cashback_earned_cents
            WHERE referrer_user_id = ?
              AND is_blacklisted = 0
              AND (cashback_earned_cents - cashback_paid_cents) > 0
            """,
            (referrer_id,),
        )
        await self._connection.commit()

    async def _migration_v11(self) -> None:
        """Migration v11: Create permanent_messages table for setup command panels."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        await self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS permanent_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                message_id INTEGER UNIQUE NOT NULL,
                channel_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                title TEXT,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by_staff_id INTEGER
            )
            """
        )

        await self._connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_permanent_messages_type_guild
                ON permanent_messages(type, guild_id)
            """
        )

        await self._connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_permanent_messages_channel
                ON permanent_messages(channel_id)
            """
        )

        await self._connection.commit()

    async def _migration_v12(self) -> None:
        """Migration v12: Create composite index on wallet_transactions for user and created_at."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        await self._connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_wallet_transactions_user_created
                ON wallet_transactions(user_discord_id, created_at)
            """
        )
        await self._connection.commit()

    async def _migration_v13(self) -> None:
        """Migration v13: Create setup_sessions table for persisting setup wizard state."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        await self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS setup_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                panel_types TEXT NOT NULL,
                current_index INTEGER NOT NULL DEFAULT 0,
                completed_panels TEXT,
                progress TEXT,
                session_payload TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                UNIQUE(guild_id, user_id)
            )
            """
        )

        await self._connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_setup_sessions_guild_user
                ON setup_sessions(guild_id, user_id)
            """
        )

        await self._connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_setup_sessions_expires_at
                ON setup_sessions(expires_at)
            """
        )

        await self._connection.commit()

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
        """Deploy a new panel to the database.
        
        Args:
            panel_type: Type of panel (products/support/help/reviews)
            message_id: Discord message ID
            channel_id: Discord channel ID
            guild_id: Discord guild ID
            title: Panel title
            description: Panel description
            created_by_staff_id: Discord ID of staff member deploying
            
        Returns:
            ID of the deployed panel
        """
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        cursor = await self._connection.execute(
            """
            INSERT INTO permanent_messages 
            (type, message_id, channel_id, guild_id, title, description, created_by_staff_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (panel_type, message_id, channel_id, guild_id, title, description, created_by_staff_id),
        )
        await self._connection.commit()
        return cursor.lastrowid

    async def get_deployments(self, guild_id: int) -> list[dict]:
        """Get all deployed panels for a guild.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            List of deployment records
        """
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        cursor = await self._connection.execute(
            """
            SELECT id, type, message_id, channel_id, title, created_at, updated_at
            FROM permanent_messages
            WHERE guild_id = ?
            ORDER BY type, created_at
            """,
            (guild_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_panel_by_type_and_channel(
        self, panel_type: str, channel_id: int, guild_id: int
    ) -> Optional[dict]:
        """Find an existing panel by type and channel.
        
        Args:
            panel_type: Type of panel
            channel_id: Discord channel ID
            guild_id: Discord guild ID
            
        Returns:
            Panel record or None
        """
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        cursor = await self._connection.execute(
            """
            SELECT id, type, message_id, channel_id, guild_id, title, description, created_at, updated_at
            FROM permanent_messages
            WHERE type = ? AND channel_id = ? AND guild_id = ?
            """,
            (panel_type, channel_id, guild_id),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def update_panel(self, panel_id: int, message_id: int) -> None:
        """Update an existing panel's message ID.
        
        Args:
            panel_id: Panel database ID
            message_id: New Discord message ID
        """
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        await self._connection.execute(
            """
            UPDATE permanent_messages
            SET message_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (message_id, panel_id),
        )
        await self._connection.commit()

    async def remove_panel(self, panel_id: int) -> None:
        """Remove a panel from the database.
        
        Args:
            panel_id: Panel database ID
        """
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        await self._connection.execute(
            "DELETE FROM permanent_messages WHERE id = ?",
            (panel_id,),
        )
        await self._connection.commit()

    async def find_panel(self, panel_type: str, guild_id: int) -> Optional[dict]:
        """Find first panel of a specific type in a guild.
        
        Args:
            panel_type: Type of panel
            guild_id: Discord guild ID
            
        Returns:
            Panel record or None
        """
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        cursor = await self._connection.execute(
            """
            SELECT id, type, message_id, channel_id, guild_id, title, description, created_at, updated_at
            FROM permanent_messages
            WHERE type = ? AND guild_id = ?
            LIMIT 1
            """,
            (panel_type, guild_id),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    @asynccontextmanager
    async def transaction(self):
        """Context manager for atomic database transactions.
        
        Provides rollback on exception and ensures all operations within the context
        are committed atomically. Any exceptions will cause automatic rollback.
        
        Yields:
            The transaction context
            
        Example:
            async with self.db.transaction() as tx:
                await tx.execute("INSERT INTO ...")
                await tx.execute("UPDATE ...")
                # Auto-commit on successful exit
                # Auto-rollback on exception
        """
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        try:
            await self._connection.execute("BEGIN TRANSACTION")
            yield self._connection
            await self._connection.execute("COMMIT")
        except Exception as e:
            try:
                await self._connection.execute("ROLLBACK")
                logger.debug(f"Database transaction rolled back due to: {e}")
            except Exception as rollback_error:
                logger.error(f"Failed to rollback transaction: {rollback_error}")
            raise

    async def create_setup_session(
        self,
        guild_id: int,
        user_id: int,
        panel_types: list[str],
        session_payload: Optional[str] = None,
        expires_at: Optional[str] = None,
        current_index: int = 0,
        completed_panels: Optional[list[str]] = None,
    ) -> int:
        """Create a new setup session.
        
        Args:
            guild_id: Discord guild ID
            user_id: Discord user ID
            panel_types: List of panel types to set up
            session_payload: Serialized session state (JSON)
            expires_at: Expiration timestamp in ISO format
            current_index: Current position in setup flow (default: 0)
            completed_panels: List of completed panel types (default: [])
            
        Returns:
            Session ID
        """
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        panel_types_str = json.dumps(panel_types)
        completed_panels_str = json.dumps(completed_panels if completed_panels is not None else [])
        
        cursor = await self._connection.execute(
            """
            INSERT INTO setup_sessions (guild_id, user_id, panel_types, current_index, completed_panels, session_payload, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET
                panel_types = excluded.panel_types,
                current_index = excluded.current_index,
                completed_panels = excluded.completed_panels,
                session_payload = excluded.session_payload,
                expires_at = excluded.expires_at,
                updated_at = CURRENT_TIMESTAMP
            """,
            (guild_id, user_id, panel_types_str, current_index, completed_panels_str, session_payload, expires_at),
        )
        await self._connection.commit()
        return cursor.lastrowid

    async def get_setup_session(self, guild_id: int, user_id: int) -> Optional[dict]:
        """Get an active setup session.
        
        Args:
            guild_id: Discord guild ID
            user_id: Discord user ID
            
        Returns:
            Session record or None
        """
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        cursor = await self._connection.execute(
            """
            SELECT * FROM setup_sessions
            WHERE guild_id = ? AND user_id = ?
            AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
            """,
            (guild_id, user_id),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def update_setup_session(
        self,
        guild_id: int,
        user_id: int,
        current_index: Optional[int] = None,
        completed_panels: Optional[list[str]] = None,
        progress: Optional[str] = None,
        session_payload: Optional[str] = None,
    ) -> bool:
        """Update an existing setup session.
        
        Args:
            guild_id: Discord guild ID
            user_id: Discord user ID
            current_index: Current panel index
            completed_panels: List of completed panel types
            progress: Progress description
            session_payload: Serialized session state
            
        Returns:
            True if session was updated, False if not found
        """
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        # Build update clause
        updates = ["updated_at = CURRENT_TIMESTAMP"]
        params: list[Any] = []
        
        if current_index is not None:
            updates.append("current_index = ?")
            params.append(current_index)
        
        if completed_panels is not None:
            updates.append("completed_panels = ?")
            params.append(json.dumps(completed_panels))
        
        if progress is not None:
            updates.append("progress = ?")
            params.append(progress)
        
        if session_payload is not None:
            updates.append("session_payload = ?")
            params.append(session_payload)
        
        params.extend([guild_id, user_id])
        
        query = f"""
            UPDATE setup_sessions
            SET {', '.join(updates)}
            WHERE guild_id = ? AND user_id = ?
        """
        
        cursor = await self._connection.execute(query, params)
        await self._connection.commit()
        return cursor.rowcount > 0

    async def delete_setup_session(self, guild_id: int, user_id: int) -> bool:
        """Delete a setup session.
        
        Args:
            guild_id: Discord guild ID
            user_id: Discord user ID
            
        Returns:
            True if session was deleted, False if not found
        """
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        cursor = await self._connection.execute(
            """
            DELETE FROM setup_sessions
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        )
        await self._connection.commit()
        return cursor.rowcount > 0

    async def cleanup_expired_sessions(self) -> int:
        """Remove expired setup sessions.
        
        Returns:
            Number of sessions deleted
        """
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        cursor = await self._connection.execute(
            """
            DELETE FROM setup_sessions
            WHERE expires_at IS NOT NULL AND expires_at <= CURRENT_TIMESTAMP
            """
        )
        await self._connection.commit()
        return cursor.rowcount

    async def get_all_active_sessions(self) -> list[dict]:
        """Get all active setup sessions.
        
        Returns:
            List of active session records
        """
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        cursor = await self._connection.execute(
            """
            SELECT * FROM setup_sessions
            WHERE expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP
            ORDER BY updated_at DESC
            """
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    # ==================== INVENTORY MANAGEMENT METHODS ====================
    
    async def update_product_stock(self, product_id: int, quantity: Optional[int]) -> bool:
        """Update product stock quantity.
        
        Args:
            product_id: Product ID
            quantity: Stock quantity (None for unlimited)
            
        Returns:
            True if updated successfully
        """
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        await self._connection.execute(
            "UPDATE products SET stock_quantity = ? WHERE id = ?",
            (quantity, product_id)
        )
        await self._connection.commit()
        return True

    async def decrease_product_stock(self, product_id: int, amount: int = 1) -> bool:
        """Decrease product stock by amount. Returns False if insufficient stock.
        
        Args:
            product_id: Product ID
            amount: Quantity to decrease (default 1)
            
        Returns:
            True if stock decreased successfully, False if insufficient stock
        """
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        async with self._wallet_lock:  # Use lock for atomic stock operations
            product = await self.get_product(product_id)
            if not product:
                return False
            
            stock = product.get("stock_quantity")
            
            # NULL stock = unlimited
            if stock is None:
                return True
            
            # Check if sufficient stock
            if stock < amount:
                return False
            
            # Decrease stock
            new_stock = stock - amount
            await self._connection.execute(
                "UPDATE products SET stock_quantity = ? WHERE id = ?",
                (new_stock, product_id)
            )
            await self._connection.commit()
            return True

    async def get_low_stock_products(self, threshold: int = 10) -> list[aiosqlite.Row]:
        """Get products with low stock.
        
        Args:
            threshold: Stock level threshold
            
        Returns:
            List of products with stock <= threshold
        """
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        cursor = await self._connection.execute(
            """
            SELECT * FROM products
            WHERE stock_quantity IS NOT NULL
              AND stock_quantity > 0
              AND stock_quantity <= ?
              AND is_active = 1
            ORDER BY stock_quantity ASC
            """,
            (threshold,)
        )
        return await cursor.fetchall()

    async def get_out_of_stock_products(self) -> list[aiosqlite.Row]:
        """Get products that are out of stock.
        
        Returns:
            List of products with stock_quantity = 0
        """
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        cursor = await self._connection.execute(
            """
            SELECT * FROM products
            WHERE stock_quantity = 0
              AND is_active = 1
            ORDER BY variant_name ASC
            """
        )
        return await cursor.fetchall()

    # ==================== PROMO CODE METHODS ====================
    
    async def create_promo_code(
        self,
        *,
        code: str,
        code_type: str,
        discount_value: float,
        free_product_id: Optional[int] = None,
        description: Optional[str] = None,
        max_uses: Optional[int] = None,
        max_uses_per_user: int = 1,
        minimum_purchase_cents: int = 0,
        applicable_categories: Optional[str] = None,
        applicable_products: Optional[str] = None,
        first_time_only: bool = False,
        starts_at: Optional[str] = None,
        expires_at: Optional[str] = None,
        is_active: bool = True,
        is_stackable: bool = False,
        created_by_staff_id: int,
    ) -> int:
        """Create a new promo code.
        
        Returns:
            Promo code ID
        """
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        cursor = await self._connection.execute(
            """
            INSERT INTO promo_codes (
                code, code_type, discount_value, free_product_id, description,
                max_uses, max_uses_per_user, minimum_purchase_cents,
                applicable_categories, applicable_products, first_time_only,
                starts_at, expires_at, is_active, is_stackable, created_by_staff_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                code.upper(), code_type, discount_value, free_product_id, description,
                max_uses, max_uses_per_user, minimum_purchase_cents,
                applicable_categories, applicable_products, 1 if first_time_only else 0,
                starts_at, expires_at, 1 if is_active else 0, 1 if is_stackable else 0,
                created_by_staff_id
            )
        )
        await self._connection.commit()
        return cursor.lastrowid

    async def get_promo_code(self, code: str) -> Optional[aiosqlite.Row]:
        """Get promo code by code string."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        cursor = await self._connection.execute(
            "SELECT * FROM promo_codes WHERE code = ? COLLATE NOCASE",
            (code.upper(),)
        )
        return await cursor.fetchone()

    async def get_all_promo_codes(self, active_only: bool = False) -> list[aiosqlite.Row]:
        """Get all promo codes."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        query = "SELECT * FROM promo_codes"
        if active_only:
            query += " WHERE is_active = 1 AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)"
        query += " ORDER BY created_at DESC"
        
        cursor = await self._connection.execute(query)
        return await cursor.fetchall()

    async def validate_promo_code(
        self,
        code: str,
        user_id: int,
        order_amount_cents: int,
        product_id: Optional[int] = None,
    ) -> tuple[bool, str, int]:
        """Validate promo code and calculate discount.
        
        Returns:
            Tuple of (is_valid, error_message, discount_cents)
        """
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        promo = await self.get_promo_code(code)
        if not promo:
            return False, "Invalid promo code", 0
        
        if not promo["is_active"]:
            return False, "Promo code is inactive", 0
        
        # Check expiration
        if promo["expires_at"]:
            from datetime import datetime
            expires = datetime.fromisoformat(promo["expires_at"])
            if datetime.now() > expires:
                return False, "Promo code has expired", 0
        
        # Check start date
        if promo["starts_at"]:
            from datetime import datetime
            starts = datetime.fromisoformat(promo["starts_at"])
            if datetime.now() < starts:
                return False, "Promo code is not yet active", 0
        
        # Check max uses
        if promo["max_uses"] and promo["current_uses"] >= promo["max_uses"]:
            return False, "Promo code has reached maximum uses", 0
        
        # Check minimum purchase
        if order_amount_cents < promo["minimum_purchase_cents"]:
            return False, f"Minimum purchase of ${promo['minimum_purchase_cents']/100:.2f} required", 0
        
        # Check user usage limit
        cursor = await self._connection.execute(
            """
            SELECT COUNT(*) as count FROM promo_code_usage
            WHERE code_id = ? AND user_discord_id = ?
            """,
            (promo["id"], user_id)
        )
        usage_row = await cursor.fetchone()
        user_uses = usage_row["count"] if usage_row else 0
        
        if user_uses >= promo["max_uses_per_user"]:
            return False, "You have already used this promo code the maximum number of times", 0
        
        # Check first-time buyer restriction
        if promo["first_time_only"]:
            cursor = await self._connection.execute(
                "SELECT COUNT(*) as count FROM orders WHERE user_discord_id = ?",
                (user_id,)
            )
            order_row = await cursor.fetchone()
            if order_row and order_row["count"] > 0:
                return False, "This promo code is only for first-time buyers", 0
        
        # Calculate discount
        discount_cents = 0
        if promo["code_type"] == "percentage":
            discount_cents = int(order_amount_cents * (promo["discount_value"] / 100))
        elif promo["code_type"] == "fixed_amount":
            discount_cents = int(promo["discount_value"] * 100)  # Convert dollars to cents
            if discount_cents > order_amount_cents:
                discount_cents = order_amount_cents  # Can't discount more than order total
        
        return True, "", discount_cents

    async def use_promo_code(
        self,
        code: str,
        user_id: int,
        order_id: int,
        discount_cents: int,
    ) -> None:
        """Record promo code usage."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        promo = await self.get_promo_code(code)
        if not promo:
            raise ValueError("Promo code not found")
        
        async with self._wallet_lock:
            await self._connection.execute("BEGIN IMMEDIATE;")
            
            # Record usage
            await self._connection.execute(
                """
                INSERT INTO promo_code_usage (code_id, user_discord_id, order_id, discount_applied_cents)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(code_id, user_discord_id) DO NOTHING
                """,
                (promo["id"], user_id, order_id, discount_cents)
            )
            
            # Increment usage count
            await self._connection.execute(
                "UPDATE promo_codes SET current_uses = current_uses + 1 WHERE id = ?",
                (promo["id"],)
            )
            
            await self._connection.commit()

    async def deactivate_promo_code(self, code: str) -> bool:
        """Deactivate a promo code."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        cursor = await self._connection.execute(
            "UPDATE promo_codes SET is_active = 0 WHERE code = ? COLLATE NOCASE",
            (code.upper(),)
        )
        await self._connection.commit()
        return cursor.rowcount > 0

    async def delete_promo_code(self, code: str) -> bool:
        """Delete a promo code permanently."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        cursor = await self._connection.execute(
            "DELETE FROM promo_codes WHERE code = ? COLLATE NOCASE",
            (code.upper(),)
        )
        await self._connection.commit()
        return cursor.rowcount > 0

    async def get_promo_code_usage_stats(self, code: str) -> dict:
        """Get usage statistics for a promo code."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        promo = await self.get_promo_code(code)
        if not promo:
            return {}
        
        cursor = await self._connection.execute(
            """
            SELECT 
                COUNT(*) as total_uses,
                COUNT(DISTINCT user_discord_id) as unique_users,
                SUM(discount_applied_cents) as total_discount_cents
            FROM promo_code_usage
            WHERE code_id = ?
            """,
            (promo["id"],)
        )
        stats = await cursor.fetchone()
        
        return {
            "code": promo["code"],
            "current_uses": promo["current_uses"],
            "max_uses": promo["max_uses"],
            "total_uses": stats["total_uses"] if stats else 0,
            "unique_users": stats["unique_users"] if stats else 0,
            "total_discount_cents": stats["total_discount_cents"] if stats else 0,
        }

    # ==================== GIFT SYSTEM METHODS ====================
    
    async def create_gift(
        self,
        *,
        gift_type: str,
        sender_discord_id: int,
        recipient_discord_id: Optional[int] = None,
        product_id: Optional[int] = None,
        wallet_amount_cents: Optional[int] = None,
        gift_code: Optional[str] = None,
        gift_message: Optional[str] = None,
        anonymous: bool = False,
        expires_at: Optional[str] = None,
    ) -> int:
        """Create a new gift.
        
        Returns:
            Gift ID
        """
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        cursor = await self._connection.execute(
            """
            INSERT INTO gifts (
                gift_type, sender_discord_id, recipient_discord_id,
                product_id, wallet_amount_cents, gift_code, gift_message,
                anonymous, expires_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                gift_type, sender_discord_id, recipient_discord_id,
                product_id, wallet_amount_cents, gift_code, gift_message,
                1 if anonymous else 0, expires_at
            )
        )
        await self._connection.commit()
        return cursor.lastrowid

    async def get_gift_by_code(self, code: str) -> Optional[aiosqlite.Row]:
        """Get gift by gift code."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        cursor = await self._connection.execute(
            "SELECT * FROM gifts WHERE gift_code = ?",
            (code,)
        )
        return await cursor.fetchone()

    async def claim_gift(self, gift_id: int, user_id: int) -> bool:
        """Claim a gift.
        
        Returns:
            True if claimed successfully
        """
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        async with self._wallet_lock:
            await self._connection.execute("BEGIN IMMEDIATE;")
            
            # Get gift
            cursor = await self._connection.execute(
                "SELECT * FROM gifts WHERE id = ? AND status = 'pending'",
                (gift_id,)
            )
            gift = await cursor.fetchone()
            
            if not gift:
                await self._connection.rollback()
                return False
            
            # Check expiration
            if gift["expires_at"]:
                from datetime import datetime
                expires = datetime.fromisoformat(gift["expires_at"])
                if datetime.now() > expires:
                    await self._connection.rollback()
                    return False
            
            # Update gift status
            await self._connection.execute(
                """
                UPDATE gifts
                SET status = 'claimed',
                    claimed_at = CURRENT_TIMESTAMP,
                    claimed_by_user_id = ?
                WHERE id = ?
                """,
                (user_id, gift_id)
            )
            
            # Apply gift
            if gift["gift_type"] == "wallet" and gift["wallet_amount_cents"]:
                await self.update_wallet_balance(user_id, gift["wallet_amount_cents"])
            
            await self._connection.commit()
            return True

    async def get_user_gifts_sent(self, user_id: int) -> list[aiosqlite.Row]:
        """Get gifts sent by a user."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        cursor = await self._connection.execute(
            """
            SELECT * FROM gifts
            WHERE sender_discord_id = ?
            ORDER BY created_at DESC
            """,
            (user_id,)
        )
        return await cursor.fetchall()

    async def get_user_gifts_received(self, user_id: int) -> list[aiosqlite.Row]:
        """Get gifts received by a user."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        cursor = await self._connection.execute(
            """
            SELECT * FROM gifts
            WHERE recipient_discord_id = ?
            ORDER BY created_at DESC
            """,
            (user_id,)
        )
        return await cursor.fetchall()

    async def cancel_gift(self, gift_id: int) -> bool:
        """Cancel a pending gift."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        cursor = await self._connection.execute(
            "UPDATE gifts SET status = 'cancelled' WHERE id = ? AND status = 'pending'",
            (gift_id,)
        )
        await self._connection.commit()
        return cursor.rowcount > 0

    # ==================== ORDER STATUS METHODS ====================
    
    async def update_order_status(
        self,
        order_id: int,
        status: str,
        estimated_delivery: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Optional[aiosqlite.Row]:
        """Update order status and return the order row.
        
        Used to fetch user_id for notifications.
        """
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        valid_statuses = ["pending", "fulfilled", "refill", "refunded"]
        if status not in valid_statuses:
            raise ValueError(f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
        
        await self._connection.execute(
            """
            UPDATE orders
            SET status = ?,
                estimated_delivery = ?,
                status_notes = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (status, estimated_delivery, notes, order_id)
        )
        await self._connection.commit()
        
        return await self.get_order_by_id(order_id)

    async def get_order_by_id(self, order_id: int) -> Optional[aiosqlite.Row]:
        """Get order by ID."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        cursor = await self._connection.execute(
            "SELECT * FROM orders WHERE id = ?",
            (order_id,)
        )
        return await cursor.fetchone()

    # ==================== ANNOUNCEMENT METHODS ====================
    
    async def create_announcement(
        self,
        *,
        title: str,
        message: str,
        announcement_type: str,
        target_role_id: Optional[int] = None,
        target_vip_tier: Optional[str] = None,
        delivery_method: str,
        channel_id: Optional[int] = None,
        created_by_staff_id: int,
        scheduled_for: Optional[str] = None,
    ) -> int:
        """Create an announcement record.
        
        Returns:
            Announcement ID
        """
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        cursor = await self._connection.execute(
            """
            INSERT INTO announcements (
                title, message, announcement_type, target_role_id, target_vip_tier,
                delivery_method, channel_id, created_by_staff_id, scheduled_for
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                title, message, announcement_type, target_role_id, target_vip_tier,
                delivery_method, channel_id, created_by_staff_id, scheduled_for
            )
        )
        await self._connection.commit()
        return cursor.lastrowid

    async def update_announcement_stats(
        self,
        announcement_id: int,
        total_recipients: int,
        successful_deliveries: int,
        failed_deliveries: int,
    ) -> None:
        """Update announcement delivery statistics."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        await self._connection.execute(
            """
            UPDATE announcements
            SET total_recipients = ?,
                successful_deliveries = ?,
                failed_deliveries = ?,
                sent_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (total_recipients, successful_deliveries, failed_deliveries, announcement_id)
        )
        await self._connection.commit()

    async def get_announcements(
        self,
        *,
        limit: int = 10,
        offset: int = 0,
    ) -> list[aiosqlite.Row]:
        """Get announcement history."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        cursor = await self._connection.execute(
            """
            SELECT * FROM announcements
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset)
        )
        return await cursor.fetchall()

    async def _migration_v14(self) -> None:
        """Migration v14: Add stock tracking to products table."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        # Check if column already exists
        cursor = await self._connection.execute("PRAGMA table_info(products)")
        columns = [row[1] for row in await cursor.fetchall()]
        
        if "stock_quantity" not in columns:
            await self._connection.execute(
                "ALTER TABLE products ADD COLUMN stock_quantity INTEGER DEFAULT NULL"
            )
            await self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_products_stock ON products(stock_quantity) WHERE stock_quantity IS NOT NULL"
            )
            await self._connection.commit()
            logger.info("Added stock_quantity column to products table")

    async def _migration_v15(self) -> None:
        """Migration v15: Create promo codes system tables."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        await self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS promo_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE COLLATE NOCASE,
                code_type TEXT NOT NULL,
                discount_value REAL NOT NULL,
                free_product_id INTEGER,
                description TEXT,
                max_uses INTEGER DEFAULT NULL,
                max_uses_per_user INTEGER DEFAULT 1,
                current_uses INTEGER DEFAULT 0,
                minimum_purchase_cents INTEGER DEFAULT 0,
                applicable_categories TEXT,
                applicable_products TEXT,
                first_time_only BOOLEAN DEFAULT 0,
                starts_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP DEFAULT NULL,
                is_active BOOLEAN DEFAULT 1,
                is_stackable BOOLEAN DEFAULT 0,
                created_by_staff_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(free_product_id) REFERENCES products(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS promo_code_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code_id INTEGER NOT NULL,
                user_discord_id INTEGER NOT NULL,
                order_id INTEGER NOT NULL,
                discount_applied_cents INTEGER NOT NULL,
                used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(code_id) REFERENCES promo_codes(id) ON DELETE CASCADE,
                FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_promo_codes_code ON promo_codes(code);
            CREATE INDEX IF NOT EXISTS idx_promo_codes_active ON promo_codes(is_active, expires_at);
            CREATE INDEX IF NOT EXISTS idx_promo_code_usage_user ON promo_code_usage(user_discord_id);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_promo_code_usage_unique ON promo_code_usage(code_id, user_discord_id);
            """
        )
        await self._connection.commit()
        logger.info("Created promo codes system tables")

    async def _migration_v16(self) -> None:
        """Migration v16: Create gift system tables."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        await self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS gifts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gift_type TEXT NOT NULL,
                sender_discord_id INTEGER NOT NULL,
                recipient_discord_id INTEGER,
                product_id INTEGER,
                wallet_amount_cents INTEGER,
                gift_code TEXT UNIQUE,
                gift_message TEXT,
                anonymous BOOLEAN DEFAULT 0,
                status TEXT DEFAULT 'pending',
                claimed_at TIMESTAMP,
                claimed_by_user_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS idx_gifts_recipient ON gifts(recipient_discord_id, status);
            CREATE INDEX IF NOT EXISTS idx_gifts_code ON gifts(gift_code) WHERE gift_code IS NOT NULL;
            CREATE INDEX IF NOT EXISTS idx_gifts_sender ON gifts(sender_discord_id);
            """
        )
        await self._connection.commit()
        logger.info("Created gift system tables")

    async def _migration_v17(self) -> None:
        """Migration v17: Create announcements table."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        await self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS announcements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                announcement_type TEXT NOT NULL,
                target_role_id INTEGER,
                target_vip_tier TEXT,
                delivery_method TEXT NOT NULL,
                channel_id INTEGER,
                total_recipients INTEGER DEFAULT 0,
                successful_deliveries INTEGER DEFAULT 0,
                failed_deliveries INTEGER DEFAULT 0,
                created_by_staff_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                scheduled_for TIMESTAMP,
                sent_at TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_announcements_created ON announcements(created_at);
            """
        )
        await self._connection.commit()
        logger.info("Created announcements table")

    async def _migration_v19(self) -> None:
        """Migration v19: Create reviews system table."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        await self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_discord_id INTEGER NOT NULL,
                order_id INTEGER NOT NULL,
                rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
                comment TEXT NOT NULL,
                photo_url TEXT,
                status TEXT DEFAULT 'pending',
                reviewed_by_staff_id INTEGER,
                reviewed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_discord_id) REFERENCES users(discord_id) ON DELETE CASCADE,
                FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_reviews_user ON reviews(user_discord_id);
            CREATE INDEX IF NOT EXISTS idx_reviews_order ON reviews(order_id);
            CREATE INDEX IF NOT EXISTS idx_reviews_status ON reviews(status);
            CREATE INDEX IF NOT EXISTS idx_reviews_rating ON reviews(rating);
            """
        )
        await self._connection.commit()
        logger.info("Created reviews system table")

    async def _migration_v20(self) -> None:
        """Migration v20: Add supplier tracking to products and create suppliers table."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        await self._connection.executescript(
            """
            -- Add supplier tracking fields to products table
            ALTER TABLE products ADD COLUMN supplier_id TEXT;
            ALTER TABLE products ADD COLUMN supplier_name TEXT;
            ALTER TABLE products ADD COLUMN supplier_service_id TEXT;
            ALTER TABLE products ADD COLUMN supplier_price_cents INTEGER;
            ALTER TABLE products ADD COLUMN markup_percent REAL DEFAULT 0;
            ALTER TABLE products ADD COLUMN supplier_api_url TEXT;
            ALTER TABLE products ADD COLUMN supplier_order_url TEXT;
            
            -- Create suppliers table for managing API suppliers
            CREATE TABLE IF NOT EXISTS suppliers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                api_url TEXT NOT NULL,
                api_key TEXT NOT NULL,
                supplier_type TEXT NOT NULL,
                markup_percent REAL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_products_supplier ON products(supplier_id);
            CREATE INDEX IF NOT EXISTS idx_suppliers_name ON suppliers(name);
            """
        )
        await self._connection.commit()
        logger.info("Added supplier tracking to products table and created suppliers table")

    async def _migration_v21(self) -> None:
        """Migration v21: Add AI support system tables."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        await self._connection.executescript(
            """
            -- AI usage logs table
            CREATE TABLE IF NOT EXISTS ai_usage_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_discord_id INTEGER NOT NULL,
                tier TEXT NOT NULL,
                model TEXT NOT NULL,
                input_tokens INTEGER,
                output_tokens INTEGER,
                total_tokens INTEGER,
                estimated_cost_cents INTEGER,
                question_preview TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_discord_id) REFERENCES users(discord_id) ON DELETE CASCADE
            );
            
            -- AI subscriptions table
            CREATE TABLE IF NOT EXISTS ai_subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_discord_id INTEGER NOT NULL UNIQUE,
                tier TEXT NOT NULL,
                subscription_start TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                subscription_end TIMESTAMP,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_discord_id) REFERENCES users(discord_id) ON DELETE CASCADE
            );
            
            -- Daily question usage tracking
            CREATE TABLE IF NOT EXISTS ai_daily_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_discord_id INTEGER NOT NULL,
                usage_date DATE NOT NULL,
                general_questions INTEGER NOT NULL DEFAULT 0,
                product_questions INTEGER NOT NULL DEFAULT 0,
                images_generated INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_discord_id, usage_date),
                FOREIGN KEY(user_discord_id) REFERENCES users(discord_id) ON DELETE CASCADE
            );
            
            CREATE INDEX IF NOT EXISTS idx_ai_usage_user ON ai_usage_logs(user_discord_id);
            CREATE INDEX IF NOT EXISTS idx_ai_usage_date ON ai_usage_logs(created_at);
            CREATE INDEX IF NOT EXISTS idx_ai_subscriptions_user ON ai_subscriptions(user_discord_id);
            CREATE INDEX IF NOT EXISTS idx_ai_subscriptions_active ON ai_subscriptions(is_active);
            CREATE INDEX IF NOT EXISTS idx_ai_daily_usage_user_date ON ai_daily_usage(user_discord_id, usage_date);
            """
        )
        await self._connection.commit()
        logger.info("Created AI support system tables")

    async def _migration_v22(self) -> None:
        """Migration v22: Add wishlist, product tags, and PIN security."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        await self._connection.executescript(
            """
            -- Wishlist table
            CREATE TABLE IF NOT EXISTS wishlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_discord_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_discord_id, product_id),
                FOREIGN KEY(user_discord_id) REFERENCES users(discord_id) ON DELETE CASCADE,
                FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE
            );
            
            -- Product tags table
            CREATE TABLE IF NOT EXISTS product_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                tag TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(product_id, tag),
                FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE
            );
            """
        )
        # Add PIN columns safely (SQLite doesn't support IF NOT EXISTS for ALTER TABLE)
        try:
            cursor = await self._connection.execute("PRAGMA table_info(users)")
            columns = [row[1] for row in await cursor.fetchall()]
            
            if "pin_hash" not in columns:
                await self._connection.execute("ALTER TABLE users ADD COLUMN pin_hash TEXT")
            if "pin_attempts" not in columns:
                await self._connection.execute("ALTER TABLE users ADD COLUMN pin_attempts INTEGER DEFAULT 0")
            if "pin_locked_until" not in columns:
                await self._connection.execute("ALTER TABLE users ADD COLUMN pin_locked_until TIMESTAMP")
        except Exception as e:
            logger.warning(f"Could not add PIN columns (may already exist): {e}")
        
        await self._connection.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_wishlist_user ON wishlist(user_discord_id);
            CREATE INDEX IF NOT EXISTS idx_wishlist_product ON wishlist(product_id);
            CREATE INDEX IF NOT EXISTS idx_product_tags_product ON product_tags(product_id);
            CREATE INDEX IF NOT EXISTS idx_product_tags_tag ON product_tags(tag);
            """
        )
        await self._connection.commit()
        logger.info("Created wishlist, product tags, and PIN security tables")

    async def _migration_v23(self) -> None:
        """Migration v23: Add Atto cryptocurrency integration (main wallet system)."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        await self._connection.executescript(
            """
            -- Atto user balances (tracked in database, not individual wallets)
            CREATE TABLE IF NOT EXISTS atto_user_balances (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_discord_id INTEGER NOT NULL UNIQUE,
                balance_raw TEXT NOT NULL DEFAULT '0',
                total_deposited_raw TEXT NOT NULL DEFAULT '0',
                total_withdrawn_raw TEXT NOT NULL DEFAULT '0',
                deposit_memo TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_discord_id) REFERENCES users(discord_id) ON DELETE CASCADE
            );
            
            -- Atto transactions
            CREATE TABLE IF NOT EXISTS atto_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_discord_id INTEGER NOT NULL,
                transaction_type TEXT NOT NULL,
                amount_raw TEXT NOT NULL,
                amount_usd_cents INTEGER,
                cashback_raw TEXT DEFAULT '0',
                from_address TEXT,
                to_address TEXT,
                transaction_hash TEXT,
                memo TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_discord_id) REFERENCES users(discord_id) ON DELETE CASCADE
            );
            
            -- Atto swap history (wallet balance to Atto)
            CREATE TABLE IF NOT EXISTS atto_swaps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_discord_id INTEGER NOT NULL,
                from_currency TEXT NOT NULL,
                to_currency TEXT NOT NULL,
                from_amount_cents INTEGER NOT NULL,
                to_amount_raw TEXT NOT NULL,
                exchange_rate REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_discord_id) REFERENCES users(discord_id) ON DELETE CASCADE
            );
            
            -- Main wallet config (stored in database)
            CREATE TABLE IF NOT EXISTS atto_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_atto_balances_user ON atto_user_balances(user_discord_id);
            CREATE INDEX IF NOT EXISTS idx_atto_transactions_user ON atto_transactions(user_discord_id);
            CREATE INDEX IF NOT EXISTS idx_atto_transactions_hash ON atto_transactions(transaction_hash);
            CREATE INDEX IF NOT EXISTS idx_atto_transactions_memo ON atto_transactions(memo);
            CREATE INDEX IF NOT EXISTS idx_atto_swaps_user ON atto_swaps(user_discord_id);
            """
        )
        await self._connection.commit()
        logger.info("Created Atto integration tables (main wallet system)")

    async def _migration_v24(self) -> None:
        """Migration v24: Add crypto wallet and transaction verification system."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        await self._connection.executescript(
            """
            -- Crypto addresses per order (unique addresses for tracking)
            CREATE TABLE IF NOT EXISTS crypto_order_addresses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                network TEXT NOT NULL,
                address TEXT NOT NULL,
                amount_cents INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE,
                UNIQUE(order_id, network)
            );
            
            -- Crypto transaction verifications
            CREATE TABLE IF NOT EXISTS crypto_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                network TEXT NOT NULL,
                transaction_hash TEXT NOT NULL,
                address TEXT NOT NULL,
                amount_cents INTEGER,
                amount_crypto TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                confirmations INTEGER DEFAULT 0,
                verified_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE
            );
            
            CREATE INDEX IF NOT EXISTS idx_crypto_addresses_order ON crypto_order_addresses(order_id);
            CREATE INDEX IF NOT EXISTS idx_crypto_addresses_network ON crypto_order_addresses(network);
            CREATE INDEX IF NOT EXISTS idx_crypto_tx_order ON crypto_transactions(order_id);
            CREATE INDEX IF NOT EXISTS idx_crypto_tx_hash ON crypto_transactions(transaction_hash);
            CREATE INDEX IF NOT EXISTS idx_crypto_tx_status ON crypto_transactions(status);
            """
        )
        await self._connection.commit()
        logger.info("Created crypto wallet and transaction verification tables")

    # ==================== SUPPLIER METHODS ====================
    
    async def get_product_by_supplier_service(
        self, supplier_id: str, supplier_service_id: str
    ) -> Optional[aiosqlite.Row]:
        """Get product by supplier ID and service ID."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        # Check if supplier fields exist
        cursor = await self._connection.execute("PRAGMA table_info(products)")
        columns = [row[1] for row in await cursor.fetchall()]
        if "supplier_id" not in columns:
            return None
        
        cursor = await self._connection.execute(
            """
            SELECT * FROM products 
            WHERE supplier_id = ? AND supplier_service_id = ?
            LIMIT 1
            """,
            (supplier_id, supplier_service_id)
        )
        return await cursor.fetchone()
    
    async def create_supplier(
        self,
        name: str,
        api_url: str,
        api_key: str,
        supplier_type: str,
        markup_percent: float = 0.0,
    ) -> int:
        """Create a new supplier record."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        cursor = await self._connection.execute(
            """
            INSERT INTO suppliers (name, api_url, api_key, supplier_type, markup_percent)
            VALUES (?, ?, ?, ?, ?)
            """,
            (name, api_url, api_key, supplier_type, markup_percent)
        )
        await self._connection.commit()
        return cursor.lastrowid
    
    async def get_supplier(self, supplier_id: int) -> Optional[aiosqlite.Row]:
        """Get supplier by ID."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        cursor = await self._connection.execute(
            "SELECT * FROM suppliers WHERE id = ?",
            (supplier_id,)
        )
        return await cursor.fetchone()
    
    async def get_all_suppliers(self) -> list[aiosqlite.Row]:
        """Get all active suppliers."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        cursor = await self._connection.execute(
            "SELECT * FROM suppliers WHERE is_active = 1 ORDER BY name ASC"
        )
        return await cursor.fetchall()

    # ==================== REVIEW SYSTEM METHODS ====================
    
    async def create_review(
        self,
        *,
        user_discord_id: int,
        order_id: int,
        rating: int,
        comment: str,
        photo_url: Optional[str] = None,
    ) -> int:
        """Create a new review.
        
        Returns:
            Review ID
        """
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        # Validate rating
        if not 1 <= rating <= 5:
            raise ValueError("Rating must be between 1 and 5")
        
        # Validate comment length
        if len(comment) < 50 or len(comment) > 1000:
            raise ValueError("Comment must be between 50 and 1000 characters")
        
        # Check if user already reviewed this order
        cursor = await self._connection.execute(
            "SELECT id FROM reviews WHERE user_discord_id = ? AND order_id = ?",
            (user_discord_id, order_id)
        )
        existing = await cursor.fetchone()
        if existing:
            raise ValueError("You have already submitted a review for this order")
        
        # Check if order exists and belongs to user
        order = await self.get_order_by_id(order_id)
        if not order:
            raise ValueError("Order not found")
        
        if order["user_discord_id"] != user_discord_id:
            raise ValueError("You can only review your own orders")
        
        cursor = await self._connection.execute(
            """
            INSERT INTO reviews (user_discord_id, order_id, rating, comment, photo_url, status)
            VALUES (?, ?, ?, ?, ?, 'pending')
            """,
            (user_discord_id, order_id, rating, comment, photo_url)
        )
        await self._connection.commit()
        return cursor.lastrowid

    async def get_review(self, review_id: int) -> Optional[aiosqlite.Row]:
        """Get review by ID."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        cursor = await self._connection.execute(
            "SELECT * FROM reviews WHERE id = ?",
            (review_id,)
        )
        return await cursor.fetchone()

    async def get_reviews_by_user(
        self,
        user_discord_id: int,
        *,
        status: Optional[str] = None
    ) -> list[aiosqlite.Row]:
        """Get reviews by user."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        query = "SELECT * FROM reviews WHERE user_discord_id = ?"
        params: list[Any] = [user_discord_id]
        
        if status:
            query += " AND status = ?"
            params.append(status)
        
        query += " ORDER BY created_at DESC"
        
        cursor = await self._connection.execute(query, params)
        return await cursor.fetchall()

    async def get_pending_reviews(self, *, limit: int = 50) -> list[aiosqlite.Row]:
        """Get pending reviews for admin approval."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        cursor = await self._connection.execute(
            """
            SELECT * FROM reviews
            WHERE status = 'pending'
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (limit,)
        )
        return await cursor.fetchall()

    async def approve_review(
        self,
        review_id: int,
        staff_discord_id: int
    ) -> bool:
        """Approve a review and award rewards.
        
        Returns:
            True if approved successfully
        """
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        async with self._wallet_lock:
            await self._connection.execute("BEGIN IMMEDIATE;")
            
            # Get review
            review = await self.get_review(review_id)
            if not review or review["status"] != "pending":
                await self._connection.rollback()
                return False
            
            # Update review status
            await self._connection.execute(
                """
                UPDATE reviews
                SET status = 'approved',
                    reviewed_by_staff_id = ?,
                    reviewed_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (staff_discord_id, review_id)
            )
            
            # Award Apex Insider role if configured
            # This would need to be handled in the cog to access guild
            
            await self._connection.commit()
            return True

    async def reject_review(
        self,
        review_id: int,
        staff_discord_id: int,
        reason: Optional[str] = None
    ) -> bool:
        """Reject a review.
        
        Returns:
            True if rejected successfully
        """
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        review = await self.get_review(review_id)
        if not review or review["status"] != "pending":
            return False
        
        await self._connection.execute(
            """
            UPDATE reviews
            SET status = 'rejected',
                reviewed_by_staff_id = ?,
                reviewed_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (staff_discord_id, review_id)
        )
        await self._connection.commit()
        return True

    async def get_reviews_by_product(
        self,
        product_id: int,
        *,
        approved_only: bool = True,
        limit: int = 20
    ) -> list[aiosqlite.Row]:
        """Get reviews for a specific product.
        
        Args:
            product_id: Product ID
            approved_only: Only return approved reviews
            limit: Maximum number of reviews to return
        """
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        query = """
            SELECT r.* FROM reviews r
            INNER JOIN orders o ON r.order_id = o.id
            WHERE o.product_id = ?
        """
        params: list[Any] = [product_id]
        
        if approved_only:
            query += " AND r.status = 'approved'"
        
        query += " ORDER BY r.created_at DESC LIMIT ?"
        params.append(limit)
        
        cursor = await self._connection.execute(query, params)
        return await cursor.fetchall()

    async def get_review_stats(self, product_id: Optional[int] = None) -> dict:
        """Get review statistics.
        
        Args:
            product_id: Optional product ID to filter by
        
        Returns:
            Dictionary with review statistics
        """
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        if product_id:
            query = """
                SELECT 
                    COUNT(*) as total_reviews,
                    AVG(rating) as avg_rating,
                    COUNT(CASE WHEN rating = 5 THEN 1 END) as five_star,
                    COUNT(CASE WHEN rating = 4 THEN 1 END) as four_star,
                    COUNT(CASE WHEN rating = 3 THEN 1 END) as three_star,
                    COUNT(CASE WHEN rating = 2 THEN 1 END) as two_star,
                    COUNT(CASE WHEN rating = 1 THEN 1 END) as one_star
                FROM reviews r
                INNER JOIN orders o ON r.order_id = o.id
                WHERE o.product_id = ? AND r.status = 'approved'
            """
            cursor = await self._connection.execute(query, (product_id,))
        else:
            query = """
                SELECT 
                    COUNT(*) as total_reviews,
                    AVG(rating) as avg_rating,
                    COUNT(CASE WHEN rating = 5 THEN 1 END) as five_star,
                    COUNT(CASE WHEN rating = 4 THEN 1 END) as four_star,
                    COUNT(CASE WHEN rating = 3 THEN 1 END) as three_star,
                    COUNT(CASE WHEN rating = 2 THEN 1 END) as two_star,
                    COUNT(CASE WHEN rating = 1 THEN 1 END) as one_star
                FROM reviews
                WHERE status = 'approved'
            """
            cursor = await self._connection.execute(query)
        
        row = await cursor.fetchone()
        if row:
            return {
                "total_reviews": row["total_reviews"] or 0,
                "avg_rating": round(row["avg_rating"] or 0, 2),
                "five_star": row["five_star"] or 0,
                "four_star": row["four_star"] or 0,
                "three_star": row["three_star"] or 0,
                "two_star": row["two_star"] or 0,
                "one_star": row["one_star"] or 0,
            }
        return {
            "total_reviews": 0,
            "avg_rating": 0.0,
            "five_star": 0,
            "four_star": 0,
            "three_star": 0,
            "two_star": 0,
            "one_star": 0,
        }

    async def _migration_v18(self) -> None:
        """Migration v18: Add status tracking to orders table."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        # Check if status column already exists
        cursor = await self._connection.execute("PRAGMA table_info(orders)")
        columns = [row[1] for row in await cursor.fetchall()]
        
        if "status" not in columns:
            await self._connection.execute(
                "ALTER TABLE orders ADD COLUMN status TEXT DEFAULT 'pending'"
            )
            await self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)"
            )

        if "estimated_delivery" not in columns:
            await self._connection.execute(
                "ALTER TABLE orders ADD COLUMN estimated_delivery TEXT"
            )

        if "status_notes" not in columns:
            await self._connection.execute(
                "ALTER TABLE orders ADD COLUMN status_notes TEXT"
            )

        if "updated_at" not in columns:
            await self._connection.execute(
                "ALTER TABLE orders ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            )

        await self._connection.commit()
        logger.info("Added status tracking columns to orders table")

    # ==================== AI SUPPORT METHODS ====================
    
    async def get_ai_subscription(self, user_discord_id: int) -> Optional[aiosqlite.Row]:
        """Get user's AI subscription."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        cursor = await self._connection.execute(
            "SELECT * FROM ai_subscriptions WHERE user_discord_id = ? AND is_active = 1",
            (user_discord_id,)
        )
        return await cursor.fetchone()
    
    async def create_ai_subscription(
        self,
        user_discord_id: int,
        tier: str,
        subscription_end: Optional[datetime] = None
    ) -> int:
        """Create or update AI subscription."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        # Check if subscription exists
        existing = await self.get_ai_subscription(user_discord_id)
        
        if existing:
            # Update existing
            await self._connection.execute(
                """
                UPDATE ai_subscriptions
                SET tier = ?, subscription_end = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_discord_id = ?
                """,
                (tier, subscription_end.isoformat() if subscription_end else None, user_discord_id)
            )
        else:
            # Create new
            cursor = await self._connection.execute(
                """
                INSERT INTO ai_subscriptions (user_discord_id, tier, subscription_end)
                VALUES (?, ?, ?)
                """,
                (user_discord_id, tier, subscription_end.isoformat() if subscription_end else None)
            )
            await self._connection.commit()
            return cursor.lastrowid
        
        await self._connection.commit()
        return existing["id"] if existing else 0
    
    async def get_ai_usage_stats(self, user_discord_id: int, days: int = 30) -> dict:
        """Get AI usage statistics for a user."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        cursor = await self._connection.execute(
            """
            SELECT 
                COUNT(*) as total_questions,
                SUM(total_tokens) as total_tokens,
                SUM(estimated_cost_cents) as total_cost_cents,
                tier
            FROM ai_usage_logs
            WHERE user_discord_id = ? AND created_at >= datetime('now', '-' || ? || ' days')
            GROUP BY tier
            """,
            (user_discord_id, days)
        )
        return await cursor.fetchall()
    
    # ==================== WISHLIST METHODS ====================
    
    async def add_to_wishlist(self, user_discord_id: int, product_id: int) -> bool:
        """Add product to user's wishlist."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        try:
            await self._connection.execute(
                "INSERT OR IGNORE INTO wishlist (user_discord_id, product_id) VALUES (?, ?)",
                (user_discord_id, product_id)
            )
            await self._connection.commit()
            return True
        except Exception as e:
            logger.error(f"Error adding to wishlist: {e}")
            return False
    
    async def remove_from_wishlist(self, user_discord_id: int, product_id: int) -> bool:
        """Remove product from user's wishlist."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        try:
            await self._connection.execute(
                "DELETE FROM wishlist WHERE user_discord_id = ? AND product_id = ?",
                (user_discord_id, product_id)
            )
            await self._connection.commit()
            return True
        except Exception as e:
            logger.error(f"Error removing from wishlist: {e}")
            return False
    
    async def get_wishlist(self, user_discord_id: int) -> list[aiosqlite.Row]:
        """Get user's wishlist."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        cursor = await self._connection.execute(
            """
            SELECT w.*, p.*
            FROM wishlist w
            JOIN products p ON w.product_id = p.id
            WHERE w.user_discord_id = ?
            ORDER BY w.created_at DESC
            """,
            (user_discord_id,)
        )
        return await cursor.fetchall()
    
    async def is_in_wishlist(self, user_discord_id: int, product_id: int) -> bool:
        """Check if product is in user's wishlist."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        cursor = await self._connection.execute(
            "SELECT 1 FROM wishlist WHERE user_discord_id = ? AND product_id = ? LIMIT 1",
            (user_discord_id, product_id)
        )
        return await cursor.fetchone() is not None
    
    # ==================== PRODUCT TAGS METHODS ====================
    
    async def add_product_tag(self, product_id: int, tag: str) -> bool:
        """Add tag to product."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        try:
            await self._connection.execute(
                "INSERT OR IGNORE INTO product_tags (product_id, tag) VALUES (?, ?)",
                (product_id, tag.lower())
            )
            await self._connection.commit()
            return True
        except Exception as e:
            logger.error(f"Error adding product tag: {e}")
            return False
    
    async def remove_product_tag(self, product_id: int, tag: str) -> bool:
        """Remove tag from product."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        try:
            await self._connection.execute(
                "DELETE FROM product_tags WHERE product_id = ? AND tag = ?",
                (product_id, tag.lower())
            )
            await self._connection.commit()
            return True
        except Exception as e:
            logger.error(f"Error removing product tag: {e}")
            return False
    
    async def get_product_tags(self, product_id: int) -> list[str]:
        """Get all tags for a product."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        cursor = await self._connection.execute(
            "SELECT tag FROM product_tags WHERE product_id = ?",
            (product_id,)
        )
        rows = await cursor.fetchall()
        return [row["tag"] for row in rows]
    
    async def search_products_by_tag(self, tag: str) -> list[aiosqlite.Row]:
        """Search products by tag."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        cursor = await self._connection.execute(
            """
            SELECT DISTINCT p.*
            FROM products p
            JOIN product_tags pt ON p.id = pt.product_id
            WHERE pt.tag = ? AND p.is_active = 1
            """,
            (tag.lower(),)
        )
        return await cursor.fetchall()
    
    # ==================== PIN SECURITY METHODS ====================
    
    async def set_user_pin(self, user_discord_id: int, pin_hash: str) -> bool:
        """Set user PIN."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        try:
            # Check if PIN columns exist
            cursor = await self._connection.execute("PRAGMA table_info(users)")
            columns = [row[1] for row in await cursor.fetchall()]
            
            if "pin_hash" not in columns:
                logger.warning("PIN columns not found in users table")
                return False
            
            await self._connection.execute(
                "UPDATE users SET pin_hash = ?, pin_attempts = 0, pin_locked_until = NULL WHERE discord_id = ?",
                (pin_hash, user_discord_id)
            )
            await self._connection.commit()
            return True
        except Exception as e:
            logger.error(f"Error setting user PIN: {e}")
            return False
    
    async def verify_user_pin(self, user_discord_id: int, pin_hash: str) -> bool:
        """Verify user PIN."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        try:
            cursor = await self._connection.execute(
                "SELECT pin_hash, pin_attempts, pin_locked_until FROM users WHERE discord_id = ?",
                (user_discord_id,)
            )
            user = await cursor.fetchone()
            
            if not user or not user["pin_hash"]:
                return False
            
            # Check if locked
            if user["pin_locked_until"]:
                locked_until = datetime.fromisoformat(user["pin_locked_until"])
                if datetime.now(timezone.utc) < locked_until:
                    return False
            
            # Verify PIN
            if user["pin_hash"] == pin_hash:
                # Reset attempts on success
                await self._connection.execute(
                    "UPDATE users SET pin_attempts = 0 WHERE discord_id = ?",
                    (user_discord_id,)
                )
                await self._connection.commit()
                return True
            else:
                # Increment attempts
                attempts = (user["pin_attempts"] or 0) + 1
                locked_until = None
                
                if attempts >= 5:
                    # Lock for 1 hour
                    locked_until = datetime.now(timezone.utc) + timedelta(hours=1)
                
                await self._connection.execute(
                    "UPDATE users SET pin_attempts = ?, pin_locked_until = ? WHERE discord_id = ?",
                    (attempts, locked_until.isoformat() if locked_until else None, user_discord_id)
                )
                await self._connection.commit()
                return False
        except Exception as e:
            logger.error(f"Error verifying user PIN: {e}")
            return False
    
    # ==================== ATTO INTEGRATION METHODS ====================
    
    async def get_atto_balance(self, user_discord_id: int) -> Optional[aiosqlite.Row]:
        """Get user's tracked Atto balance."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        cursor = await self._connection.execute(
            "SELECT * FROM atto_user_balances WHERE user_discord_id = ?",
            (user_discord_id,)
        )
        return await cursor.fetchone()
    
    async def create_atto_balance(self, user_discord_id: int, deposit_memo: str) -> int:
        """Create Atto balance record for user."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        cursor = await self._connection.execute(
            "INSERT INTO atto_user_balances (user_discord_id, deposit_memo) VALUES (?, ?)",
            (user_discord_id, deposit_memo)
        )
        await self._connection.commit()
        return cursor.lastrowid
    
    async def add_atto_balance(self, user_discord_id: int, amount_raw: str, cashback_raw: str = "0") -> bool:
        """Add Atto balance to user (for deposits)."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        try:
            # Get or create balance record
            balance = await self.get_atto_balance(user_discord_id)
            if not balance:
                # Create with memo
                memo = f"USER_{user_discord_id}"
                await self.create_atto_balance(user_discord_id, memo)
            
            # Add deposit + cashback
            total_added = str(int(amount_raw) + int(cashback_raw))
            await self._connection.execute(
                """
                UPDATE atto_user_balances 
                SET balance_raw = CAST(balance_raw AS INTEGER) + CAST(? AS INTEGER),
                    total_deposited_raw = CAST(total_deposited_raw AS INTEGER) + CAST(? AS INTEGER),
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_discord_id = ?
                """,
                (total_added, amount_raw, user_discord_id)
            )
            await self._connection.commit()
            return True
        except Exception as e:
            logger.error(f"Error adding Atto balance: {e}")
            return False
    
    async def deduct_atto_balance(self, user_discord_id: int, amount_raw: str) -> bool:
        """Deduct Atto balance from user (for payments/withdrawals)."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        try:
            await self._connection.execute(
                """
                UPDATE atto_user_balances 
                SET balance_raw = CAST(balance_raw AS INTEGER) - CAST(? AS INTEGER),
                    total_withdrawn_raw = CAST(total_withdrawn_raw AS INTEGER) + CAST(? AS INTEGER),
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_discord_id = ? AND CAST(balance_raw AS INTEGER) >= CAST(? AS INTEGER)
                """,
                (amount_raw, amount_raw, user_discord_id, amount_raw)
            )
            await self._connection.commit()
            return True
        except Exception as e:
            logger.error(f"Error deducting Atto balance: {e}")
            return False
    
    async def get_main_wallet_address(self) -> Optional[str]:
        """Get main wallet address from config."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        cursor = await self._connection.execute(
            "SELECT value FROM atto_config WHERE key = 'main_wallet_address'"
        )
        row = await cursor.fetchone()
        return row["value"] if row else None
    
    async def set_main_wallet_address(self, address: str) -> bool:
        """Set main wallet address in config."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        try:
            await self._connection.execute(
                """
                INSERT INTO atto_config (key, value, updated_at)
                VALUES ('main_wallet_address', ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = CURRENT_TIMESTAMP
                """,
                (address, address)
            )
            await self._connection.commit()
            return True
        except Exception as e:
            logger.error(f"Error setting main wallet address: {e}")
            return False
    
    # ==================== CRYPTO WALLET METHODS ====================
    
    async def create_crypto_order_address(
        self, order_id: int, network: str, address: str, amount_cents: int
    ) -> int:
        """Create crypto address for order."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        cursor = await self._connection.execute(
            """
            INSERT INTO crypto_order_addresses (order_id, network, address, amount_cents)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(order_id, network) DO UPDATE SET address = ?, amount_cents = ?
            """,
            (order_id, network, address, amount_cents, address, amount_cents)
        )
        await self._connection.commit()
        return cursor.lastrowid
    
    async def get_crypto_order_address(self, order_id: int, network: str) -> Optional[aiosqlite.Row]:
        """Get crypto address for order."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        cursor = await self._connection.execute(
            "SELECT * FROM crypto_order_addresses WHERE order_id = ? AND network = ?",
            (order_id, network)
        )
        return await cursor.fetchone()
    
    async def create_crypto_transaction(
        self,
        order_id: int,
        network: str,
        transaction_hash: str,
        address: str,
        amount_cents: Optional[int] = None,
        amount_crypto: Optional[str] = None,
        status: str = "pending"
    ) -> int:
        """Create crypto transaction record."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        cursor = await self._connection.execute(
            """
            INSERT INTO crypto_transactions 
            (order_id, network, transaction_hash, address, amount_cents, amount_crypto, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (order_id, network, transaction_hash, address, amount_cents, amount_crypto, status)
        )
        await self._connection.commit()
        return cursor.lastrowid
    
    async def get_crypto_transaction(self, transaction_hash: str) -> Optional[aiosqlite.Row]:
        """Get crypto transaction by hash."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        cursor = await self._connection.execute(
            "SELECT * FROM crypto_transactions WHERE transaction_hash = ?",
            (transaction_hash,)
        )
        return await cursor.fetchone()
    
    async def update_crypto_transaction_status(
        self, transaction_hash: str, status: str, confirmations: int = 0
    ) -> bool:
        """Update crypto transaction status."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        try:
            await self._connection.execute(
                """
                UPDATE crypto_transactions 
                SET status = ?, confirmations = ?, verified_at = CURRENT_TIMESTAMP
                WHERE transaction_hash = ?
                """,
                (status, confirmations, transaction_hash)
            )
            await self._connection.commit()
            return True
        except Exception as e:
            logger.error(f"Error updating crypto transaction status: {e}")
            return False
    
    async def log_atto_transaction(
        self,
        user_discord_id: int,
        transaction_type: str,
        amount_raw: str,
        amount_usd_cents: int,
        from_address: Optional[str] = None,
        to_address: Optional[str] = None,
        transaction_hash: Optional[str] = None,
        memo: Optional[str] = None,
        cashback_raw: Optional[str] = None,
        status: str = "pending"
    ) -> int:
        """Log Atto transaction."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        cursor = await self._connection.execute(
            """
            INSERT INTO atto_transactions 
            (user_discord_id, transaction_type, amount_raw, amount_usd_cents, cashback_raw, from_address, to_address, transaction_hash, memo, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_discord_id, transaction_type, amount_raw, amount_usd_cents, cashback_raw or "0", from_address, to_address, transaction_hash, memo, status)
        )
        await self._connection.commit()
        return cursor.lastrowid
    
    async def log_atto_swap(
        self,
        user_discord_id: int,
        from_currency: str,
        to_currency: str,
        from_amount_cents: int,
        to_amount_raw: str,
        exchange_rate: float
    ) -> int:
        """Log Atto swap transaction."""
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")
        
        cursor = await self._connection.execute(
            """
            INSERT INTO atto_swaps 
            (user_discord_id, from_currency, to_currency, from_amount_cents, to_amount_raw, exchange_rate)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_discord_id, from_currency, to_currency, from_amount_cents, to_amount_raw, exchange_rate)
        )
        await self._connection.commit()
        return cursor.lastrowid
