import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from telethon.errors import FloodWaitError
from helper.telegram_utils import fetch_message_batch
from helper.Logger import Logging

@pytest.fixture
def mock_config():
    config = MagicMock()
    config.get_with_default.side_effect = lambda section, key, default: {
        ("logging", "logger_name"): "MyLogger",
        ("logging", "log_stream_level"): "INFO",
        ("logging", "log_dir_name"): "logs",
    }.get((section, key), default)
    return config

@pytest.fixture
def logger(mock_config):
    logger = Logging(mock_config, instance_id="test_telegram_utils")
    yield logger
    logger.close_log()

@pytest.mark.asyncio
async def test_fetch_message_batch_success(logger):
    channel_id = "12345"
    offset_id = 0
    batch_size = 10
    client = AsyncMock()
    mock_messages = [MagicMock() for _ in range(batch_size)]
    client.get_messages.return_value = mock_messages

    messages = await fetch_message_batch(client, channel_id, offset_id, batch_size, logger)

    assert len(messages) == batch_size
    assert client.get_messages.called
    assert client.get_messages.call_args[0][0] == channel_id
    assert client.get_messages.call_args[1]["limit"] == batch_size
    assert client.get_messages.call_args[1]["offset_id"] == offset_id

@pytest.mark.asyncio
async def test_fetch_message_batch_flood_wait_error(logger):
    channel_id = "12345"
    offset_id = 0
    batch_size = 10
    client = AsyncMock()
    # Create FloodWaitError with a request and set seconds manually
    flood_wait_error = FloodWaitError(request=None)
    flood_wait_error.seconds = 5  # Manually set the seconds attribute
    client.get_messages.side_effect = flood_wait_error

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        messages = await fetch_message_batch(client, channel_id, offset_id, batch_size, logger)

    assert messages == []
    assert mock_sleep.called
    assert mock_sleep.call_args[0][0] == 5  # Wait time from FloodWaitError

@pytest.mark.asyncio
async def test_fetch_message_batch_general_error(logger):
    channel_id = "12345"
    offset_id = 0
    batch_size = 10
    client = AsyncMock()
    client.get_messages.side_effect = Exception("API error")

    messages = await fetch_message_batch(client, channel_id, offset_id, batch_size, logger)

    assert messages == []
    assert client.get_messages.called

@pytest.mark.asyncio
async def test_fetch_message_batch_no_logger():
    channel_id = "12345"
    offset_id = 0
    batch_size = 10
    client = AsyncMock()
    mock_messages = [MagicMock() for _ in range(batch_size)]
    client.get_messages.return_value = mock_messages

    messages = await fetch_message_batch(client, channel_id, offset_id, batch_size, logger=None)

    assert len(messages) == batch_size
    assert client.get_messages.called