#tests/test_channel_tracker.py
import pytest
import os
import logging
import pandas as pd
from unittest.mock import patch, MagicMock, AsyncMock
from helper.config_manager import ConfigManager
from helper.database import DatabaseHandler
from helper.Logger import Logging
from scripts.channelTracker import main

@pytest.fixture
def mock_config():
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    return ConfigManager('tests/combined_config_test.yaml', project_root=project_root)

@pytest.fixture
def logger(mock_config):
    return Logging(mock_config, "MyLogger")

@pytest.fixture
def mock_engine():
    engine = MagicMock()
    connection = MagicMock()
    engine.connect.return_value.__enter__.return_value = connection
    return engine

@pytest.fixture
def mock_telegram_client():
    client = AsyncMock()
    client.is_user_authorized.return_value = True
    client.get_dialogs.return_value = [MockDialog()]
    client.connect.return_value = None
    client.disconnect.return_value = None
    client.is_connected = MagicMock(return_value=True)
    return client

class MockDialog:
    def __init__(self):
        self.is_channel = True
        self.id = 123
        self.name = "TestChannel"

def test_channel_tracker_success(mock_config, logger, mock_engine, mock_telegram_client, caplog):
    caplog.set_level(logging.INFO)
    mock_db_data = pd.DataFrame(columns=['ID', 'Name', 'Operating', 'Disappeared', 'created_dt', 'update_dt'])
    with patch("scripts.channelTracker.create_engine", return_value=mock_engine), \
         patch("scripts.channelTracker.TelegramClient", return_value=mock_telegram_client), \
         patch("pandas.read_sql", return_value=mock_db_data), \
         patch("pandas.DataFrame.to_sql", return_value=None), \
         patch("helper.config_manager.ConfigManager.get_with_default", side_effect=lambda section, key, default: "test_channel_sync" if section == "" and key == "log_file" else default), \
         patch("sys.argv", ["channelTracker.py", "--project-root", "/home/egirg/shared/trading_dev"]):
        main()
        mock_engine.connect.assert_called()
        mock_telegram_client.get_dialogs.assert_called()
        assert "Stored 1 channels in temp_channels" in caplog.text
        assert "Inserted 1 new channels" in caplog.text
        assert "Channels table updated successfully" in caplog.text

def test_channel_tracker_db_failure(mock_config, logger, mock_telegram_client, caplog):
    caplog.set_level(logging.ERROR)
    with patch("scripts.channelTracker.create_engine", side_effect=Exception("DB Error")), \
         patch("scripts.channelTracker.TelegramClient", return_value=mock_telegram_client), \
         patch("pandas.read_sql", return_value=pd.DataFrame(columns=['ID', 'Name', 'Operating', 'Disappeared', 'created_dt', 'update_dt'])), \
         patch("pandas.DataFrame.to_sql", return_value=None), \
         patch("helper.config_manager.ConfigManager.get_with_default", side_effect=lambda section, key, default: "test_channel_sync" if section == "" and key == "log_file" else default), \
         patch("sys.argv", ["channelTracker.py", "--project-root", "/home/egirg/shared/trading_dev"]):
        with pytest.raises(SystemExit):
            main()
        assert "Failed to create SQLAlchemy engine: DB Error" in caplog.text

def test_channel_tracker_empty_channels(mock_config, logger, mock_engine, mock_telegram_client, caplog):
    caplog.set_level(logging.INFO)
    mock_db_data = pd.DataFrame(columns=['ID', 'Name', 'Operating', 'Disappeared', 'created_dt', 'update_dt'])
    with patch("scripts.channelTracker.create_engine", return_value=mock_engine), \
         patch("scripts.channelTracker.TelegramClient", return_value=mock_telegram_client), \
         patch("pandas.read_sql", return_value=mock_db_data), \
         patch("pandas.DataFrame.to_sql", return_value=None), \
         patch("helper.config_manager.ConfigManager.get_with_default", side_effect=lambda section, key, default: "test_channel_sync" if section == "" and key == "log_file" else default), \
         patch("sys.argv", ["channelTracker.py", "--project-root", "/home/egirg/shared/trading_dev"]):
        mock_telegram_client.get_dialogs.return_value = []
        main()
        assert "Stored 0 channels in temp_channels" in caplog.text
        assert "Cannot update channels: database or Telegram data missing." in caplog.text

def test_channel_tracker_telegram_auth_failure(mock_config, logger, mock_engine, mock_telegram_client, caplog):
    caplog.set_level(logging.ERROR)
    with patch("scripts.channelTracker.create_engine", return_value=mock_engine), \
         patch("scripts.channelTracker.TelegramClient", return_value=mock_telegram_client), \
         patch("pandas.read_sql", return_value=pd.DataFrame(columns=['ID', 'Name', 'Operating', 'Disappeared', 'created_dt', 'update_dt'])), \
         patch("pandas.DataFrame.to_sql", return_value=None), \
         patch("helper.config_manager.ConfigManager.get_with_default", side_effect=lambda section, key, default: "test_channel_sync" if section == "" and key == "log_file" else default), \
         patch("sys.argv", ["channelTracker.py", "--project-root", "/home/egirg/shared/trading_dev"]):
        mock_telegram_client.is_user_authorized.return_value = False
        mock_telegram_client.start.side_effect = Exception("Auth failed")
        main()
        assert "Error fetching Telegram channels: Auth failed" in caplog.text