import pytest
from unittest.mock import patch, MagicMock
import sys
import os
import asyncio

# We need to make sure bot.py can be imported. 
# It imports apex_core, so we assume PYTHONPATH includes project root.
from bot import _validate_token_format, main

def test_validate_token_format_valid():
    # Valid looking token structure
    # Part 1: ID-like string
    # Part 2: Timestamp-like string
    # Part 3: HMAC-like string
    token = "Valid_Token_Part_1.Part2.Part_3_Longer_And_Complex"
    assert _validate_token_format(token) is True
    
    # Another valid one
    token = "Another_Valid_Token.Time.Signature_With_Numbers_123"
    assert _validate_token_format(token) is True

def test_validate_token_format_invalid():
    # None or empty
    assert _validate_token_format(None) is False
    assert _validate_token_format("") is False
    
    # Wrong number of parts
    assert _validate_token_format("part1.part2") is False
    assert _validate_token_format("part1.part2.part3.part4") is False
    
    # Invalid characters
    assert _validate_token_format("part1.part2.part3$") is False
    assert _validate_token_format("part1.part 2.part3") is False
    
    # Too short segments
    assert _validate_token_format("short.short.short") is False # 5.5.5 -> 2nd is fine but 1st and 3rd too short
    assert _validate_token_format("1234567890.1.1234567890") is False # 2nd part too short
    assert _validate_token_format("1.12345.1234567890") is False # 1st part too short

@patch("bot.load_config")
@patch("bot.replace")
@patch("sys.exit")
@patch.dict(os.environ, {"DISCORD_TOKEN": "invalid.token", "CONFIG_PATH": "config.json"})
def test_main_invalid_token(mock_exit, mock_replace, mock_load_config):
    # Mock config
    mock_config = MagicMock()
    mock_load_config.return_value = mock_config
    
    # Mock exit to raise SystemExit so we can catch it
    mock_exit.side_effect = SystemExit(1)
    
    with pytest.raises(SystemExit):
        asyncio.run(main())
        
    mock_exit.assert_called_with(1)
    mock_replace.assert_not_called()

@patch("bot.load_config")
@patch("bot.replace")
@patch("bot.ApexCoreBot")
@patch("bot.load_payment_settings")
@patch.dict(os.environ, {"DISCORD_TOKEN": "Valid_Token_Part_1.Part2.Part_3_Longer_And_Complex", "CONFIG_PATH": "config.json"})
def test_main_valid_token(mock_load_payment, mock_bot_cls, mock_replace, mock_load_config):
    mock_config = MagicMock()
    # Ensure config has necessary attributes to avoid failures before bot start
    mock_config.bot_prefix = "!"
    mock_config.token = "old_token"
    mock_config.payment_settings = None # Simulate no payment settings
    
    mock_load_config.return_value = mock_config
    mock_replace.return_value = mock_config 
    
    # Mock load_payment_settings to raise FileNotFoundError so we skip that part logic
    mock_load_payment.side_effect = FileNotFoundError()
    
    mock_bot = MagicMock()
    mock_bot_cls.return_value = mock_bot
    
    # Setup async context manager for bot
    async def async_aenter(*args, **kwargs):
        return mock_bot
    async def async_aexit(*args, **kwargs):
        return None
    
    mock_bot.__aenter__ = MagicMock(side_effect=async_aenter)
    mock_bot.__aexit__ = MagicMock(side_effect=async_aexit)
    
    # Setup bot.start
    async def async_start(*args, **kwargs):
        pass
    mock_bot.start = MagicMock(side_effect=async_start)
    
    asyncio.run(main())
    
    mock_replace.assert_called()
