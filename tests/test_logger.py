"""Test the enhanced logger module."""

import asyncio
import logging
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from apex_core.logger import get_logger, setup_logger, DiscordHandler


def test_get_logger_returns_logger():
    """Test that get_logger returns a valid logger instance."""
    logger = get_logger()
    assert logger is not None
    assert hasattr(logger, 'info')
    assert hasattr(logger, 'error')
    assert hasattr(logger, 'warning')


def test_setup_logger_creates_configured_logger():
    """Test that setup_logger creates a properly configured logger."""
    logger = setup_logger(level=logging.DEBUG)
    assert logger is not None
    assert logger.level == logging.DEBUG


def test_discord_handler_creation():
    """Test that DiscordHandler can be created without errors."""
    handler = DiscordHandler()
    assert handler is not None
    assert handler.bot is None
    assert handler.channel_id is None


def test_discord_handler_with_bot():
    """Test DiscordHandler with bot instance."""
    mock_bot = MagicMock()
    handler = DiscordHandler(bot=mock_bot, channel_id=12345)
    assert handler.bot is mock_bot
    assert handler.channel_id == 12345


def test_logger_is_mocked_in_tests(mock_logger):
    """Test that logger is properly mocked in test environment."""
    # This test verifies that the conftest.py fixtures are working
    from apex_core import logger as apex_logger
    assert apex_logger.logger is mock_logger