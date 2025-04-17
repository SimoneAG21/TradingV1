import pytest
import os
import json
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from datetime import datetime
import pytz
from sqlalchemy.engine import Engine
from helper.message_storage import MessageStorageHandler
from helper.Logger import Logging

@pytest.fixture
def mock_config():
    config = MagicMock()
    config.get_with_default.side_effect = lambda section, key, default: {
        ("message_storage", "temp_dir"): "temp_messages",
        ("message_storage", "media_subdir"): "media",
        ("timezone", "name"): "America/Chicago",
    }.get((section, key), default)
    return config

@pytest.fixture
def logger(mock_config):
    logger = Logging(mock_config, instance_id="test_message_storage")
    yield logger
    logger.close_log()

@pytest.fixture
def engine():
    return MagicMock(spec=Engine)

@pytest.fixture
def message_storage(mock_config, logger, engine):
    return MessageStorageHandler(mock_config, logger, engine)

@pytest.fixture
def mock_messages():
    message1 = MagicMock()
    message1.id = 1
    message1.date = datetime(2025, 4, 14, 15, 0, 0)
    message1.text = "Test message 1"
    message1.sender_id = 123
    message1.reply_to_msg_id = None
    message1.media = None
    message1.photo = None
    message1.video = None
    message1.document = None

    message2 = MagicMock()
    message2.id = 2
    message2.date = datetime(2025, 4, 14, 15, 1, 0)
    message2.text = "Test message 2"
    message2.sender_id = 456
    message2.reply_to_msg_id = 1
    message2.media = True
    message2.photo = True
    message2.video = None
    message2.document = None

    return [message1, message2]

@pytest.mark.asyncio
async def test_store_messages_no_media(message_storage, mock_messages):
    channel_id = "12345"
    client = AsyncMock()
    
    with patch("os.makedirs"), \
         patch("os.path.getsize", return_value=1024), \
         patch("helper.message_storage.get_formatted_timestamp", return_value="20250414_150000") as mock_timestamp, \
         patch("helper.message_storage.to_local_time", side_effect=lambda dt: dt), \
         patch("pytz.timezone", return_value=pytz.timezone("America/Chicago")), \
         patch.object(message_storage.engine, "connect", new_callable=MagicMock) as mock_connect:
        mock_conn = MagicMock()
        mock_connect.return_value.__enter__.return_value = mock_conn
        mock_conn.execute.return_value.fetchone.return_value = None  # Simulate first run

        # Mock file writing for messages and stats
        mock_file = mock_open()
        with patch("builtins.open", mock_file):
            await message_storage.store_messages(mock_messages, channel_id, client)

        # Verify JSON file was written
        assert mock_file.call_count == 2  # Messages and stats files
        messages_file = mock_file.call_args_list[0][0][0]
        expected_prefix = os.path.join("temp_messages", channel_id, "batch_20250414_150000").replace(os.sep, '/')
        assert messages_file.replace(os.sep, '/').startswith(expected_prefix)
        assert messages_file.endswith(".json")

        # Verify database updates (INSERT, SELECT, UPDATE)
        assert mock_conn.execute.call_count == 3  # INSERT into channel_fetch_batches, SELECT from channels, UPDATE channels

@pytest.mark.asyncio
async def test_store_messages_with_media(message_storage, mock_messages):
    channel_id = "12345"
    client = AsyncMock()
    client.download_media = AsyncMock(return_value=None)
    
    with patch("os.makedirs"), \
         patch("os.path.getsize", return_value=1024), \
         patch("helper.message_storage.get_formatted_timestamp", return_value="20250414_150000") as mock_timestamp, \
         patch("helper.message_storage.to_local_time", side_effect=lambda dt: dt), \
         patch("pytz.timezone", return_value=pytz.timezone("America/Chicago")), \
         patch.object(message_storage.engine, "connect", new_callable=MagicMock) as mock_connect:
        mock_conn = MagicMock()
        mock_connect.return_value.__enter__.return_value = mock_conn
        mock_conn.execute.return_value.fetchone.return_value = None

        # Mock file writing for messages and stats
        mock_file = mock_open()
        with patch("builtins.open", mock_file):
            await message_storage.store_messages(mock_messages, channel_id, client)

        # Verify media download
        assert client.download_media.called
        media_file = client.download_media.call_args[1]["file"]
        expected_suffix = f"{channel_id}_2_20250414_150000.jpg"
        assert media_file.replace(os.sep, '/').endswith(expected_suffix)

@pytest.mark.asyncio
async def test_store_messages_database_failure(message_storage, mock_messages):
    channel_id = "12345"
    client = AsyncMock()
    
    with patch("os.makedirs"), \
         patch("helper.message_storage.get_formatted_timestamp", return_value="20250414_150000") as mock_timestamp, \
         patch("helper.message_storage.to_local_time", side_effect=lambda dt: dt), \
         patch("pytz.timezone", return_value=pytz.timezone("America/Chicago")), \
         patch.object(message_storage.engine, "connect", new_callable=MagicMock) as mock_connect:
        mock_conn = MagicMock()
        mock_connect.return_value.__enter__.return_value = mock_conn
        mock_conn.execute.side_effect = Exception("Database error")

        # Mock file writing for messages and stats
        mock_file = mock_open()
        with patch("builtins.open", mock_file):
            with pytest.raises(Exception, match="Database error"):
                await message_storage.store_messages(mock_messages, channel_id, client)