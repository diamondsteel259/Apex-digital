import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, AsyncMock, patch

import pytest
import discord
from cogs.ticket_management import TicketManagementCog


@pytest.fixture
def ticket_management_cog():
    return object.__new__(TicketManagementCog)


def test_parse_timestamp_with_datetime_object_aware(ticket_management_cog):
    dt = datetime(2024, 5, 1, 12, 30, 15, tzinfo=timezone.utc)
    result = ticket_management_cog._parse_timestamp(dt)
    assert result == dt
    assert result.tzinfo == timezone.utc


def test_parse_timestamp_with_datetime_object_naive(ticket_management_cog):
    dt = datetime(2024, 5, 1, 12, 30, 15)
    result = ticket_management_cog._parse_timestamp(dt)
    assert result.year == 2024
    assert result.month == 5
    assert result.day == 1
    assert result.hour == 12
    assert result.minute == 30
    assert result.second == 15
    assert result.tzinfo == timezone.utc


def test_parse_timestamp_with_iso_format_string(ticket_management_cog):
    result = ticket_management_cog._parse_timestamp("2024-05-01T12:30:15+02:00")
    assert result.tzinfo == timezone.utc
    assert result.hour == 10
    assert result.minute == 30


def test_parse_timestamp_with_space_separated_string(ticket_management_cog):
    result = ticket_management_cog._parse_timestamp("2024-05-01 12:30:15")
    assert result.tzinfo == timezone.utc
    assert result.hour == 12
    assert result.minute == 30


def test_parse_timestamp_with_timezone_aware_string(ticket_management_cog):
    result = ticket_management_cog._parse_timestamp("2024-05-01T12:30:15+00:00")
    assert result.tzinfo == timezone.utc
    assert result.hour == 12
    assert result.minute == 30


def test_parse_timestamp_with_invalid_type_raises(ticket_management_cog):
    with pytest.raises(ValueError, match="Unsupported timestamp type"):
        ticket_management_cog._parse_timestamp(12345)


def test_parse_timestamp_preserves_microseconds(ticket_management_cog):
    result = ticket_management_cog._parse_timestamp("2024-05-01T12:30:15.123456")
    assert result.microsecond == 123456
    assert result.tzinfo == timezone.utc


def test_parse_timestamp_normalizes_to_utc(ticket_management_cog):
    offset_dt = datetime(2024, 5, 1, 5, 30, 15, tzinfo=timezone(timedelta(hours=-5)))
    result = ticket_management_cog._parse_timestamp(offset_dt)
    assert result.tzinfo == timezone.utc
    assert result.hour == 10
    assert result.minute == 30


@pytest.mark.asyncio
async def test_ticket_counter_generates_unique_values(db, user_factory):
    user_id = await user_factory(26000)

    counts = await asyncio.gather(
        *(db.get_next_ticket_count(user_id, "order") for _ in range(5))
    )

    assert sorted(counts) == [1, 2, 3, 4, 5]


@pytest.mark.asyncio
async def test_create_ticket_with_counter_returns_sequence(db, user_factory):
    user_id = await user_factory(26001)

    first_ticket_id, first_counter = await db.create_ticket_with_counter(
        user_discord_id=user_id,
        channel_id=999100,
        ticket_type="order",
    )
    assert first_ticket_id > 0
    assert first_counter == 1

    second_ticket_id, second_counter = await db.create_ticket_with_counter(
        user_discord_id=user_id,
        channel_id=999101,
        ticket_type="order",
    )
    assert second_ticket_id > first_ticket_id
    assert second_counter == 2


@pytest.mark.asyncio
async def test_touch_ticket_activity_updates_timestamp(db, user_factory):
    user_id = await user_factory(26002)

    ticket_id = await db.create_ticket(
        user_discord_id=user_id,
        channel_id=999102,
        ticket_type="support",
    )

    await db._connection.execute(
        "UPDATE tickets SET last_activity = '2000-01-01 00:00:00' WHERE id = ?",
        (ticket_id,),
    )
    await db._connection.commit()

    await db.touch_ticket_activity(999102)
    ticket = await db.get_ticket_by_channel(999102)
    assert ticket["last_activity"] != "2000-01-01 00:00:00"


@pytest.mark.asyncio
async def test_save_and_retrieve_transcripts(db, user_factory):
    user_id = await user_factory(26003)

    ticket_id = await db.create_ticket(
        user_discord_id=user_id,
        channel_id=999103,
    )

    transcript_id = await db.save_transcript(
        ticket_id=ticket_id,
        user_discord_id=user_id,
        channel_id=999103,
        storage_type="local",
        storage_path="transcripts/ticket.html",
        file_size_bytes=1024,
    )
    assert transcript_id > 0

    transcript = await db.get_transcript_by_ticket_id(ticket_id)
    assert transcript is not None
    assert transcript["storage_path"] == "transcripts/ticket.html"


class TestSecureTicketChannels:
    """Tests for secure ticket channel creation with permission overwrites."""

    def test_build_ticket_channel_overwrites_denies_everyone(self, ticket_management_cog):
        """Test that @everyone is denied view_channel and send_messages."""
        guild = MagicMock(spec=discord.Guild)
        guild.default_role = MagicMock(spec=discord.Role, id=123)
        guild.me = MagicMock(spec=discord.Member, id=456)
        
        admin_role = MagicMock(spec=discord.Role, id=789)
        member = MagicMock(spec=discord.Member, id=999)
        
        overwrites = ticket_management_cog._build_ticket_channel_overwrites(
            guild, admin_role, member
        )
        
        assert guild.default_role in overwrites
        everyone_overwrite = overwrites[guild.default_role]
        assert everyone_overwrite.view_channel is False
        assert everyone_overwrite.send_messages is False

    def test_build_ticket_channel_overwrites_allows_bot(self, ticket_management_cog):
        """Test that the bot has full permissions including message history."""
        guild = MagicMock(spec=discord.Guild)
        guild.default_role = MagicMock(spec=discord.Role, id=123)
        guild.me = MagicMock(spec=discord.Member, id=456)
        
        admin_role = MagicMock(spec=discord.Role, id=789)
        member = MagicMock(spec=discord.Member, id=999)
        
        overwrites = ticket_management_cog._build_ticket_channel_overwrites(
            guild, admin_role, member
        )
        
        assert guild.me in overwrites
        bot_overwrite = overwrites[guild.me]
        assert bot_overwrite.view_channel is True
        assert bot_overwrite.send_messages is True
        assert bot_overwrite.manage_channels is True
        assert bot_overwrite.read_message_history is True

    def test_build_ticket_channel_overwrites_allows_admin(self, ticket_management_cog):
        """Test that the admin role has view/send/read permissions."""
        guild = MagicMock(spec=discord.Guild)
        guild.default_role = MagicMock(spec=discord.Role, id=123)
        guild.me = MagicMock(spec=discord.Member, id=456)
        
        admin_role = MagicMock(spec=discord.Role, id=789)
        member = MagicMock(spec=discord.Member, id=999)
        
        overwrites = ticket_management_cog._build_ticket_channel_overwrites(
            guild, admin_role, member
        )
        
        assert admin_role in overwrites
        admin_overwrite = overwrites[admin_role]
        assert admin_overwrite.view_channel is True
        assert admin_overwrite.send_messages is True
        assert admin_overwrite.read_message_history is True

    def test_build_ticket_channel_overwrites_allows_member(self, ticket_management_cog):
        """Test that the requesting member has view/send/read permissions."""
        guild = MagicMock(spec=discord.Guild)
        guild.default_role = MagicMock(spec=discord.Role, id=123)
        guild.me = MagicMock(spec=discord.Member, id=456)
        
        admin_role = MagicMock(spec=discord.Role, id=789)
        member = MagicMock(spec=discord.Member, id=999)
        
        overwrites = ticket_management_cog._build_ticket_channel_overwrites(
            guild, admin_role, member
        )
        
        assert member in overwrites
        member_overwrite = overwrites[member]
        assert member_overwrite.view_channel is True
        assert member_overwrite.send_messages is True
        assert member_overwrite.read_message_history is True

    def test_build_ticket_channel_overwrites_without_admin_role(self, ticket_management_cog):
        """Test that overwrites work when admin role is None."""
        guild = MagicMock(spec=discord.Guild)
        guild.default_role = MagicMock(spec=discord.Role, id=123)
        guild.me = MagicMock(spec=discord.Member, id=456)
        
        member = MagicMock(spec=discord.Member, id=999)
        
        overwrites = ticket_management_cog._build_ticket_channel_overwrites(
            guild, None, member
        )
        
        assert len(overwrites) == 3
        assert guild.default_role in overwrites
        assert guild.me in overwrites
        assert member in overwrites
        assert None not in overwrites

    def test_build_ticket_channel_overwrites_has_correct_count(self, ticket_management_cog):
        """Test that exactly the expected number of overwrites are created."""
        guild = MagicMock(spec=discord.Guild)
        guild.default_role = MagicMock(spec=discord.Role, id=123)
        guild.me = MagicMock(spec=discord.Member, id=456)
        
        admin_role = MagicMock(spec=discord.Role, id=789)
        member = MagicMock(spec=discord.Member, id=999)
        
        overwrites = ticket_management_cog._build_ticket_channel_overwrites(
            guild, admin_role, member
        )
        
        assert len(overwrites) == 4
        targets = {guild.default_role, guild.me, admin_role, member}
        assert set(overwrites.keys()) == targets


class TestGeneralSupportModalOverwrites:
    """Tests for GeneralSupportModal permission overwrites."""

    def test_general_support_modal_has_build_method(self):
        """Test that GeneralSupportModal has the _build_ticket_channel_overwrites method."""
        from cogs.ticket_management import GeneralSupportModal
        
        assert hasattr(GeneralSupportModal, '_build_ticket_channel_overwrites')

    def test_general_support_modal_overwrites_denies_everyone(self, ticket_management_cog):
        """Test that GeneralSupportModal creates overwrites that deny @everyone."""
        guild = MagicMock(spec=discord.Guild)
        guild.default_role = MagicMock(spec=discord.Role, id=123)
        guild.me = MagicMock(spec=discord.Member, id=456)
        
        admin_role = MagicMock(spec=discord.Role, id=789)
        member = MagicMock(spec=discord.Member, id=999)
        
        from cogs.ticket_management import GeneralSupportModal
        modal = object.__new__(GeneralSupportModal)
        
        overwrites = modal._build_ticket_channel_overwrites(
            guild, admin_role, member
        )
        
        assert guild.default_role in overwrites
        everyone_overwrite = overwrites[guild.default_role]
        assert everyone_overwrite.view_channel is False
        assert everyone_overwrite.send_messages is False


class TestRefundSupportModalOverwrites:
    """Tests for RefundSupportModal permission overwrites."""

    def test_refund_support_modal_has_build_method(self):
        """Test that RefundSupportModal has the _build_ticket_channel_overwrites method."""
        from cogs.ticket_management import RefundSupportModal
        
        assert hasattr(RefundSupportModal, '_build_ticket_channel_overwrites')

    def test_refund_support_modal_overwrites_denies_everyone(self, ticket_management_cog):
        """Test that RefundSupportModal creates overwrites that deny @everyone."""
        guild = MagicMock(spec=discord.Guild)
        guild.default_role = MagicMock(spec=discord.Role, id=123)
        guild.me = MagicMock(spec=discord.Member, id=456)
        
        admin_role = MagicMock(spec=discord.Role, id=789)
        member = MagicMock(spec=discord.Member, id=999)
        
        from cogs.ticket_management import RefundSupportModal
        modal = object.__new__(RefundSupportModal)
        
        overwrites = modal._build_ticket_channel_overwrites(
            guild, admin_role, member
        )
        
        assert guild.default_role in overwrites
        everyone_overwrite = overwrites[guild.default_role]
        assert everyone_overwrite.view_channel is False
        assert everyone_overwrite.send_messages is False
