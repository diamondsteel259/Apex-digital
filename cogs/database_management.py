"""Database backup and management commands."""

from __future__ import annotations

import csv
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal, Optional

import discord
from discord import app_commands
from discord.ext import commands

from apex_core.logger import get_logger
from apex_core.utils import create_embed
from apex_core.utils.permissions import is_admin_from_bot

logger = get_logger()

# Check for optional S3 support
try:
    import boto3
    from botocore.exceptions import ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False


class DatabaseManagementCog(commands.Cog):
    """Commands for database backup and data export."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.backup_dir = Path("backups")
        self.backup_dir.mkdir(exist_ok=True)

    def _is_admin(self, user: discord.User, guild: Optional[discord.Guild]) -> bool:
        """Check if user is admin."""
        return is_admin_from_bot(user, guild, self.bot)

    async def _upload_to_s3(self, file_path: Path) -> tuple[bool, Optional[str]]:
        """Upload backup file to S3 if configured.
        
        Returns:
            Tuple of (success, error_message)
        """
        if not BOTO3_AVAILABLE:
            return False, "boto3 not installed"
        
        import os
        bucket = os.getenv("S3_BUCKET")
        
        if not bucket:
            return False, "S3 bucket not configured"
        
        try:
            s3_client = boto3.client(
                's3',
                aws_access_key_id=os.getenv("S3_ACCESS_KEY"),
                aws_secret_access_key=os.getenv("S3_SECRET_KEY"),
                region_name=os.getenv("S3_REGION", "us-east-1")
            )
            
            s3_key = f"backups/{file_path.name}"
            s3_client.upload_file(str(file_path), bucket, s3_key)
            
            logger.info(f"Backup uploaded to S3: s3://{bucket}/{s3_key}")
            return True, None
        except ClientError as e:
            logger.error(f"S3 upload failed: {e}")
            return False, str(e)
        except Exception as e:
            logger.error(f"S3 upload error: {e}")
            return False, str(e)

    @app_commands.command(name="backup")
    @app_commands.describe(
        upload_to_s3="Upload backup to S3 (requires configuration)"
    )
    async def backup_database(
        self,
        interaction: discord.Interaction,
        upload_to_s3: bool = False
    ) -> None:
        """Create database backup (admin only)."""
        if not self._is_admin(interaction.user, interaction.guild):
            await interaction.response.send_message(
                "🚫 You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Create backup filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = self.backup_dir / f"apex_core_backup_{timestamp}.db"
            
            # Copy database file
            db_path = Path(self.bot.db.db_path)
            if not db_path.exists():
                await interaction.followup.send(
                    "❌ Database file not found.",
                    ephemeral=True
                )
                return
            
            shutil.copy2(db_path, backup_file)
            
            # Get file size
            file_size_mb = backup_file.stat().st_size / (1024 * 1024)
            
            # Upload to S3 if requested
            s3_status = ""
            if upload_to_s3:
                success, error = await self._upload_to_s3(backup_file)
                if success:
                    s3_status = "\n✅ Uploaded to S3"
                else:
                    s3_status = f"\n⚠️ S3 upload failed: {error}"
            
            # Clean old backups (keep last 30 days)
            cutoff_date = datetime.now() - timedelta(days=30)
            deleted_count = 0
            for old_backup in self.backup_dir.glob("apex_core_backup_*.db"):
                try:
                    # Extract date from filename
                    date_str = old_backup.stem.split("_")[-2]  # Get date part
                    backup_date = datetime.strptime(date_str, "%Y%m%d")
                    if backup_date < cutoff_date:
                        old_backup.unlink()
                        deleted_count += 1
                except (ValueError, IndexError):
                    # Skip files with unexpected names
                    continue
            
            embed = create_embed(
                title="✅ Database Backup Created",
                description=(
                    f"**Backup File:** `{backup_file.name}`\n"
                    f"**Size:** {file_size_mb:.2f} MB\n"
                    f"**Location:** `{backup_file}`{s3_status}"
                ),
                color=discord.Color.green()
            )
            
            if deleted_count > 0:
                embed.add_field(
                    name="🧹 Cleanup",
                    value=f"Deleted {deleted_count} old backup(s) (>30 days)",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"Database backup created: {backup_file} by {interaction.user.id}")
            
        except Exception as e:
            logger.exception("Failed to create database backup", exc_info=True)
            await interaction.followup.send(
                f"❌ Failed to create backup: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="listbackups")
    async def list_backups(self, interaction: discord.Interaction) -> None:
        """List available backups (admin only)."""
        if not self._is_admin(interaction.user, interaction.guild):
            await interaction.response.send_message(
                "🚫 You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            backups = sorted(
                self.backup_dir.glob("apex_core_backup_*.db"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )
            
            if not backups:
                await interaction.followup.send(
                    "📭 No backups found.",
                    ephemeral=True
                )
                return
            
            # Show last 10 backups
            embed = create_embed(
                title="📦 Available Backups",
                description=f"Found {len(backups)} backup(s). Showing last 10:",
                color=discord.Color.blue()
            )
            
            for backup in backups[:10]:
                size_mb = backup.stat().st_size / (1024 * 1024)
                modified = datetime.fromtimestamp(backup.stat().st_mtime)
                age_days = (datetime.now() - modified).days
                
                embed.add_field(
                    name=backup.name,
                    value=f"Size: {size_mb:.2f} MB | Age: {age_days} day(s)",
                    inline=False
                )
            
            if len(backups) > 10:
                embed.set_footer(text=f"Showing 10 of {len(backups)} backups")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.exception("Failed to list backups", exc_info=True)
            await interaction.followup.send(
                f"❌ Failed to list backups: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="exportdata")
    @app_commands.describe(
        data_type="Type of data to export",
        timeframe="Time range (e.g., '7d', '30d', 'all')"
    )
    async def export_data(
        self,
        interaction: discord.Interaction,
        data_type: Literal["orders", "users", "transactions", "products"],
        timeframe: str = "30d"
    ) -> None:
        """Export data to CSV (admin only)."""
        if not self._is_admin(interaction.user, interaction.guild):
            await interaction.response.send_message(
                "🚫 You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Parse timeframe
            if timeframe == "all":
                days = None
            elif timeframe.endswith("d"):
                days = int(timeframe[:-1])
            else:
                await interaction.followup.send(
                    "❌ Invalid timeframe. Use format like '7d', '30d', or 'all'",
                    ephemeral=True
                )
                return
            
            # Calculate date cutoff
            cutoff_date = None
            if days:
                cutoff_date = datetime.now() - timedelta(days=days)
            
            # Export data based on type
            if data_type == "orders":
                rows = await self._export_orders(cutoff_date)
            elif data_type == "users":
                rows = await self._export_users(cutoff_date)
            elif data_type == "transactions":
                rows = await self._export_transactions(cutoff_date)
            elif data_type == "products":
                rows = await self._export_products()
            else:
                await interaction.followup.send(
                    "❌ Invalid data type.",
                    ephemeral=True
                )
                return
            
            if not rows:
                await interaction.followup.send(
                    f"📭 No {data_type} data found for the specified timeframe.",
                    ephemeral=True
                )
                return
            
            # Create CSV file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv_file = self.backup_dir / f"{data_type}_export_{timestamp}.csv"
            
            with csv_file.open("w", newline="", encoding="utf-8") as f:
                if rows:
                    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                    writer.writeheader()
                    writer.writerows(rows)
            
            # Send file
            file_size_mb = csv_file.stat().st_size / (1024 * 1024)
            
            embed = create_embed(
                title=f"✅ {data_type.title()} Export Complete",
                description=(
                    f"**Records:** {len(rows)}\n"
                    f"**File Size:** {file_size_mb:.2f} MB\n"
                    f"**Timeframe:** {timeframe}"
                ),
                color=discord.Color.green()
            )
            
            await interaction.followup.send(
                embed=embed,
                file=discord.File(str(csv_file), filename=csv_file.name),
                ephemeral=True
            )
            
            logger.info(f"Data export created: {csv_file} by {interaction.user.id}")
            
        except Exception as e:
            logger.exception("Failed to export data", exc_info=True)
            await interaction.followup.send(
                f"❌ Failed to export data: {str(e)}",
                ephemeral=True
            )

    async def _export_orders(self, cutoff_date: Optional[datetime]) -> list[dict[str, Any]]:
        """Export orders to CSV format."""
        if self.bot.db._connection is None:
            return []
        
        query = "SELECT * FROM orders"
        params: list[Any] = []
        
        if cutoff_date:
            query += " WHERE created_at >= ?"
            params.append(cutoff_date.isoformat())
        
        query += " ORDER BY created_at DESC"
        
        cursor = await self.bot.db._connection.execute(query, params)
        rows = await cursor.fetchall()
        
        return [dict(row) for row in rows]

    async def _export_users(self, cutoff_date: Optional[datetime]) -> list[dict[str, Any]]:
        """Export users to CSV format."""
        if self.bot.db._connection is None:
            return []
        
        query = "SELECT * FROM users"
        params: list[Any] = []
        
        if cutoff_date:
            query += " WHERE created_at >= ?"
            params.append(cutoff_date.isoformat())
        
        query += " ORDER BY created_at DESC"
        
        cursor = await self.bot.db._connection.execute(query, params)
        rows = await cursor.fetchall()
        
        return [dict(row) for row in rows]

    async def _export_transactions(self, cutoff_date: Optional[datetime]) -> list[dict[str, Any]]:
        """Export wallet transactions to CSV format."""
        if self.bot.db._connection is None:
            return []
        
        query = "SELECT * FROM wallet_transactions"
        params: list[Any] = []
        
        if cutoff_date:
            query += " WHERE created_at >= ?"
            params.append(cutoff_date.isoformat())
        
        query += " ORDER BY created_at DESC"
        
        cursor = await self.bot.db._connection.execute(query, params)
        rows = await cursor.fetchall()
        
        return [dict(row) for row in rows]

    async def _export_products(self) -> list[dict[str, Any]]:
        """Export products to CSV format."""
        if self.bot.db._connection is None:
            return []
        
        cursor = await self.bot.db._connection.execute(
            "SELECT * FROM products ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
        
        return [dict(row) for row in rows]


async def setup(bot: commands.Bot) -> None:
    """Load the DatabaseManagementCog cog."""
    await bot.add_cog(DatabaseManagementCog(bot))

