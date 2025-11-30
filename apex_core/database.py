"""Async SQLite data layer for Apex Core."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import aiosqlite


class Database:
    """Async database handler using SQLite."""

    def __init__(self, db_path: str | Path = "apex_core.db") -> None:
        self.db_path = Path(db_path)
        self._connection: Optional[aiosqlite.Connection] = None
        self._wallet_lock = asyncio.Lock()

    async def connect(self) -> None:
        if self._connection is None:
            self._connection = await aiosqlite.connect(self.db_path)
            self._connection.row_factory = aiosqlite.Row
            await self._connection.execute("PRAGMA foreign_keys = ON;")
            await self._connection.commit()
            await self._initialize_schema()

    async def close(self) -> None:
        if self._connection:
            await self._connection.close()
            self._connection = None

    async def _initialize_schema(self) -> None:
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        await self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                discord_id INTEGER UNIQUE NOT NULL,
                wallet_balance_cents INTEGER NOT NULL DEFAULT 0,
                total_lifetime_spent_cents INTEGER NOT NULL DEFAULT 0,
                vip_tier TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price_cents INTEGER NOT NULL,
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
            await self._connection.execute("BEGIN IMMEDIATE;")
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
                    total_lifetime_spent_cents = CASE
                        WHEN ? > 0 THEN total_lifetime_spent_cents + ?
                        ELSE total_lifetime_spent_cents
                    END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE discord_id = ?;
                """,
                (delta_cents, delta_cents, delta_cents, discord_id),
            )
            await self._connection.commit()

            cursor = await self._connection.execute(
                "SELECT wallet_balance_cents FROM users WHERE discord_id = ?",
                (discord_id,),
            )
            row = await cursor.fetchone()
            return row["wallet_balance_cents"] if row else 0

    async def create_product(
        self,
        name: str,
        price_cents: int,
        role_id: Optional[int],
        content_payload: Optional[str],
    ) -> int:
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        cursor = await self._connection.execute(
            """
            INSERT INTO products (name, price_cents, role_id, content_payload)
            VALUES (?, ?, ?, ?)
            """,
            (name, price_cents, role_id, content_payload),
        )
        await self._connection.commit()
        return cursor.lastrowid

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
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        cursor = await self._connection.execute(
            """
            SELECT * FROM discounts
            WHERE (user_id IS NULL OR user_id = ?)
              AND (product_id IS NULL OR product_id = ?)
              AND (vip_tier IS NULL OR vip_tier = ?)
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

    async def update_user_vip_tier(self, discord_id: int, vip_tier: Optional[str]) -> None:
        if self._connection is None:
            raise RuntimeError("Database connection not initialized.")

        await self._connection.execute(
            """
            UPDATE users
            SET vip_tier = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE discord_id = ?
            """,
            (vip_tier, discord_id),
        )
        await self._connection.commit()
