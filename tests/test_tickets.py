import asyncio
from datetime import datetime, timedelta, timezone

import pytest
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
