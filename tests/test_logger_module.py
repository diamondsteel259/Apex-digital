from __future__ import annotations

import logging
import sys
from types import SimpleNamespace

import pytest

from apex_core import logger as logger_module
from apex_core.logger import DiscordHandler, get_logger, setup_logger


def test_setup_logger_and_get_logger_are_idempotent() -> None:
    log = setup_logger(level=logging.DEBUG, enable_discord=False)
    assert log.name == "apex_core"
    assert log.level == logging.DEBUG
    assert log.propagate is False

    # Calling get_logger should return the same global logger.
    log2 = get_logger()
    assert log2 is log


def test_discord_handler_emit_short_circuits_without_bot() -> None:
    handler = DiscordHandler(bot=None, channel_id=123)
    record = logging.LogRecord(
        name="apex_core.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )

    handler.emit(record)  # should not raise


def test_discord_handler_formats_message_and_calls_schedule(monkeypatch: pytest.MonkeyPatch) -> None:
    sent = {"msg": None}

    class DummyBot:
        def get_channel(self, channel_id: int):
            return SimpleNamespace(id=channel_id)

    handler = DiscordHandler(bot=DummyBot(), channel_id=123)
    monkeypatch.setattr(handler, "_schedule_send", lambda _channel, msg: sent.__setitem__("msg", msg))

    record = logging.LogRecord(
        name="apex_core.test",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="warning-message",
        args=(),
        exc_info=None,
    )

    handler.emit(record)
    assert sent["msg"] is not None
    assert "WARNING" in sent["msg"]


@pytest.mark.asyncio
async def test_discord_handler_schedule_send_uses_running_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyBot:
        def __init__(self):
            self.loop = None

        def get_channel(self, channel_id: int):
            return SimpleNamespace(id=channel_id)

    handler = DiscordHandler(bot=DummyBot(), channel_id=123)

    called = {"count": 0}

    def _fake_run_coroutine_threadsafe(coro, _loop):
        called["count"] += 1
        coro.close()  # avoid "coroutine was never awaited" warnings
        return None

    monkeypatch.setattr(logger_module.asyncio, "run_coroutine_threadsafe", _fake_run_coroutine_threadsafe)

    handler._schedule_send(SimpleNamespace(id=123), "hello")
    assert called["count"] == 1

    # Also exercise DummyBot.get_channel for coverage.
    assert handler.bot.get_channel(123).id == 123


def test_discord_handler_emit_returns_when_channel_missing() -> None:
    class DummyBot:
        def get_channel(self, _channel_id: int):
            return None

    handler = DiscordHandler(bot=DummyBot(), channel_id=123)
    record = logging.LogRecord(
        name="apex_core.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )

    handler.emit(record)  # should short-circuit when channel is missing


def test_discord_handler_includes_traceback(monkeypatch: pytest.MonkeyPatch) -> None:
    sent = {"msg": None}

    class DummyBot:
        def get_channel(self, channel_id: int):
            return SimpleNamespace(id=channel_id)

    handler = DiscordHandler(bot=DummyBot(), channel_id=123)
    monkeypatch.setattr(handler, "_schedule_send", lambda _channel, msg: sent.__setitem__("msg", msg))

    try:
        raise ValueError("boom")
    except ValueError:
        exc_info = sys.exc_info()

    record = logging.LogRecord(
        name="apex_core.test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="error-message",
        args=(),
        exc_info=exc_info,
    )

    handler.emit(record)
    assert sent["msg"] is not None
    assert "```" in sent["msg"]
