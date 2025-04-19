# tests/test_telegram_fetch.py
import pytest
import asyncio
import logging
import os
import json
from datetime import datetime
from unittest.mock import patch, AsyncMock, MagicMock
from telethon.errors import FloodWaitError
from scripts.telegram_fetch import (
    parse_arguments, initialize_dependencies, reload_config, fetch_active_channels,
    fetch_message_batch, store_messages_to_file, record_batch_metadata, update_channel_status
)
from helper.config_manager import ConfigManager
from helper.Logger import Logging

@pytest.fixture
def mock_config():
    project_root = "/home/egirg/shared/trading_dev"
    config = ConfigManager("config/combined_config.yaml", project_root=project_root)
    return config

@pytest.fixture
def mock_logger(mock_config):
    return Logging(mock_config, "telegram_fetch_test")

@pytest.fixture
def mock_engine():
    engine = MagicMock()
    connection = MagicMock()
    engine.connect.return_value.__enter__.return_value = connection
    return engine

@pytest.fixture
def mock_client():
    return AsyncMock()

@pytest.fixture
def mock_lock_handler():
    return MagicMock()

@pytest.mark.asyncio
async def test_parse_arguments_default():
    with patch("sys.argv", ["telegram_fetch.py"]):
        config_path, max_batches = parse_arguments()
        assert config_path == "config/combined_config.yaml"
        assert max_batches == 0

@pytest.mark.asyncio
async def test_parse_arguments_max_batches():
    with patch("sys.argv", ["telegram_fetch.py", "--max-batches", "5"]):
        config_path, max_batches = parse_arguments()
        assert config_path == "config/combined_config.yaml"
        assert max_batches == 5

@pytest.mark.asyncio
async def test_parse_arguments_custom():
    with patch("sys.argv", ["telegram_fetch.py", "--config", "custom_config.yaml"]):
        config_path, max_batches = parse_arguments()
        assert config_path == "custom_config.yaml"
        assert max_batches == 0

@pytest.mark.asyncio
async def test_initialize_dependencies(mock_config, mock_logger):
    with patch("helper.telegram_client.TelegramClientHandler.get_client", new=AsyncMock(return_value="mock_client")) as mock_get_client, \
         patch("helper.database.DatabaseHandler.get_engine", return_value="mock_engine"):
        config, logger, client, engine = await initialize_dependencies(
            "config/combined_config.yaml", "/home/egirg/shared/trading_dev"
        )
        assert isinstance(config, ConfigManager)
        assert isinstance(logger, Logging)
        assert client == "mock_client"
        assert engine == "mock_engine"
        mock_get_client.assert_called_once()

@pytest.mark.asyncio
async def test_reload_config_success(mock_config, mock_logger, caplog):
    caplog.set_level(logging.DEBUG)
    with patch("scripts.telegram_fetch.ConfigManager", return_value=mock_config):
        config = reload_config("config/combined_config.yaml", "/home/egirg/shared/trading_dev", mock_logger)
        assert isinstance(config, ConfigManager)
        assert "Successfully reloaded configuration" in caplog.text

@pytest.mark.asyncio
async def test_reload_config_error(mock_logger, caplog):
    caplog.set_level(logging.ERROR)
    with patch("scripts.telegram_fetch.ConfigManager", side_effect=Exception("Config error")):
        config = reload_config("config/combined_config.yaml", "/home/egirg/shared/trading_dev", mock_logger)
        assert config is None
        assert "Failed to reload configuration: Config error" in caplog.text

def test_fetch_active_channels_success(mock_engine, mock_logger, caplog):
    caplog.set_level(logging.INFO)
    mock_result = [
        (123, 1000, "2025-04-01 12:00:00", 2000),
        (124, 1500, "2025-04-02 14:00:00", None)
    ]
    mock_engine.connect().__enter__().execute.return_value.fetchall.return_value = mock_result
    channels = fetch_active_channels(mock_engine, mock_logger)
    assert len(channels) == 2
    assert channels == mock_result
    assert "Fetched 2 active channels" in caplog.text

def test_fetch_active_channels_empty(mock_engine, mock_logger, caplog):
    caplog.set_level(logging.INFO)
    mock_engine.connect().__enter__().execute.return_value.fetchall.return_value = []
    channels = fetch_active_channels(mock_engine, mock_logger)
    assert channels == []
    assert "Fetched 0 active channels" in caplog.text

def test_fetch_active_channels_error(mock_engine, mock_logger, caplog):
    caplog.set_level(logging.ERROR)
    mock_engine.connect().__enter__().execute.side_effect = Exception("Database error")
    channels = fetch_active_channels(mock_engine, mock_logger)
    assert channels == []
    assert "Error fetching active channels: Database error" in caplog.text


@pytest.mark.asyncio
async def test_fetch_message_batch_success(mock_client, mock_logger, caplog):
    caplog.set_level(logging.INFO)
    mock_messages = [MagicMock(id=1001), MagicMock(id=1002)]
    mock_client.get_messages.return_value = mock_messages
    messages = await fetch_message_batch(mock_client, 123, 1000, 100, mock_logger)
    assert len(messages) == 2
    assert messages == mock_messages
    assert "Fetched 2 valid messages for channel 123 at final offset 1002" in caplog.text
    mock_client.get_messages.assert_called_with(123, limit=100, offset_id=1000, reverse=True)


@pytest.mark.asyncio
async def test_fetch_message_batch_flood_wait(mock_client, mock_logger, caplog):
    caplog.set_level(logging.WARNING)
    error = FloodWaitError(request=None)
    error.seconds = 2
    mock_client.get_messages.side_effect = error
    messages = await fetch_message_batch(mock_client, 123, 1000, 100, mock_logger)
    assert messages == []
    assert "Flood wait error for channel 123: waiting 2 seconds (retry 1/5)" in caplog.text
    assert "Max retries reached for channel 123 due to flood wait" in caplog.text


@pytest.mark.asyncio
async def test_fetch_message_batch_error(mock_client, mock_logger, caplog):
    caplog.set_level(logging.ERROR)
    mock_client.get_messages.side_effect = Exception("API error")
    messages = await fetch_message_batch(mock_client, 123, 1000, 100, mock_logger)
    assert messages == []
    assert "Error fetching messages for channel 123: API error" in caplog.text

def test_store_messages_to_file_success(mock_config, mock_logger, tmp_path, caplog):
    caplog.set_level(logging.INFO)
    messages = [
        MagicMock(id=1001, date=datetime(2025, 4, 1, 12, 0), text="Hello", sender_id=456, action=None),
        MagicMock(id=1002, date=datetime(2025, 4, 1, 12, 1), text=None, sender_id=None, action="service")
    ]
    base_dir = tmp_path / "temp_messages"
    with patch("helper.config_manager.ConfigManager.get_with_default", return_value=str(base_dir)), \
         patch("scripts.telegram_fetch.get_formatted_timestamp", return_value="2025-04-01T12-00-00"):
        filename = store_messages_to_file(messages, 123, 1, 2, mock_config, mock_logger)
        assert filename == str(base_dir / "123" / "batch_2025-04-01T12-00-00.json")
        assert os.path.exists(filename)
        with open(filename, 'r') as f:
            data = json.load(f)
        assert len(data) == 3  # 2 messages + 1 status
        assert data[0]["message_id"] == 1001
        assert data[1]["is_service_message"] is True
        assert data[2]["status"]["batch_number"] == 1
        assert "Stored 2 messages for channel 123, batch 1, total 2 in" in caplog.text

def test_store_messages_to_file_error(mock_config, mock_logger, tmp_path, caplog):
    caplog.set_level(logging.ERROR)
    messages = [MagicMock(id=1001, date=datetime(2025, 4, 1, 12, 0), text="Hello")]
    with patch("helper.config_manager.ConfigManager.get_with_default", return_value="/invalid/path"), \
         patch("scripts.telegram_fetch.get_formatted_timestamp", return_value="2025-04-01T12-00-00"):
        filename = store_messages_to_file(messages, 123, 1, 1, mock_config, mock_logger)
        assert filename is None
        assert "Failed to store messages for channel 123" in caplog.text

def test_record_batch_metadata_success(mock_engine, mock_logger, caplog):
    caplog.set_level(logging.INFO)
    messages = [
        MagicMock(id=1001, date=datetime(2025, 4, 1, 12, 0)),
        MagicMock(id=1002, date=datetime(2025, 4, 1, 12, 1))
    ]
    msg_filename = "/path/to/batch.json"
    mock_engine.connect().__enter__().execute.return_value = None
    mock_datetime = datetime(2025, 4, 1, 12, 2)
    with patch("scripts.telegram_fetch.datetime") as mock_dt:
        mock_dt.now.return_value = mock_datetime
        success = record_batch_metadata(mock_engine, 123, msg_filename, messages, 1, mock_logger)
        assert success is True
        assert "Recorded batch 1 metadata for channel 123" in caplog.text

def test_record_batch_metadata_no_messages(mock_engine, mock_logger, caplog):
    caplog.set_level(logging.WARNING)
    success = record_batch_metadata(mock_engine, 123, "/path/to/batch.json", [], 1, mock_logger)
    assert success is False
    assert "No messages or filename to record for channel 123" in caplog.text

def test_record_batch_metadata_error(mock_engine, mock_logger, caplog):
    caplog.set_level(logging.ERROR)
    messages = [MagicMock(id=1001, date=datetime(2025, 4, 1, 12, 0))]
    msg_filename = "/path/to/batch.json"
    mock_engine.connect().__enter__().execute.side_effect = Exception("Database error")
    success = record_batch_metadata(mock_engine, 123, msg_filename, messages, 1, mock_logger)
    assert success is False
    assert "Failed to record batch metadata for channel 123: Database error" in caplog.text

def test_update_channel_status_with_messages(mock_engine, mock_logger, caplog):
    caplog.set_level(logging.INFO)
    messages = [
        MagicMock(id=1002, date=datetime(2025, 4, 1, 12, 1)),
        MagicMock(id=1001, date=datetime(2025, 4, 1, 12, 0))
    ]
    mock_engine.connect().__enter__().execute.return_value = None
    success = update_channel_status(mock_engine, 123, messages, 1, mock_logger)
    assert success is True
    assert "Updated channel 123 with new messages, reset fetch_attempts" in caplog.text

@pytest.mark.asyncio
async def test_update_channel_status_no_messages_complete(mock_engine, mock_logger, caplog):
    caplog.set_level(logging.INFO)
    messages = []
    mock_engine.connect().__enter__().execute.return_value = None
    success = update_channel_status(mock_engine, 123, messages, 4, mock_logger)
    assert success is True
    assert "Channel 123 marked complete after 5 empty fetches" in caplog.text

def test_update_channel_status_no_messages_in_progress(mock_engine, mock_logger, caplog):
    caplog.set_level(logging.INFO)
    messages = []
    mock_engine.connect().__enter__().execute.return_value = None
    success = update_channel_status(mock_engine, 123, messages, 0, mock_logger)
    assert success is True
    assert "Channel 123 updated with 1 empty fetches" in caplog.text

def test_update_channel_status_error(mock_engine, mock_logger, caplog):
    caplog.set_level(logging.ERROR)
    messages = [MagicMock(id=1001, date=datetime(2025, 4, 1, 12, 0))]
    mock_engine.connect().__enter__().execute.side_effect = Exception("Database error")
    success = update_channel_status(mock_engine, 123, messages, 0, mock_logger)
    assert success is False
    assert "Failed to update channel 123 status: Database error" in caplog.text