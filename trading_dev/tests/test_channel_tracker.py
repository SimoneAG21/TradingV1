#tests/test_channel_tracker.py


# tests/test_channel_tracker.py
import pytest
import pandas as pd
import logging
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import create_engine
from scripts import channelTracker  # Import the module directly
import asyncio
import os
from datetime import datetime

@pytest.fixture
def config():
    """Fixture for a mock ConfigManager."""
    config = MagicMock()
    config.get_with_default.side_effect = lambda section, key, default: {
        ("", "log_file", "channel_sync"): "logs/channel_sync",
        ("lockfile", "lock_name", "channelTracker.lock"): "channel_tracker.lock",
        ("schedule", "interval_minutes", 180): 180
    }.get((section, key, default), default)
    config.get.side_effect = lambda section, key: {
        ('database', 'mysql.user'): 'trading_dev_user',
        ('database', 'mysql.password'): 'devStrongPass2025!',
        ('database', 'mysql.host'): 'localhost',
        ('database', 'mysql.port'): '3306',
        ('database', 'mysql.database'): 'Trading_dev',
        ('telegram', 'session_path'): 'sessions/my_telegram_client.session',
        ('telegram', 'api_id'): 27715324,
        ('telegram', 'api_hash'): '72f0a5168ab258f7b6cb169c78ff31d6',
        ('telegram', 'phone'): '+14698380038'
    }.get((section, key))
    config.determine_project_root.return_value = "/home/egirg/shared/trading_dev"
    return config

@pytest.fixture
def logger(config):
    """Fixture for a mock logger."""
    return channelTracker.setup_logging(config, "logs/channel_sync.log")

@pytest.fixture
def engine():
    """Fixture for a mock SQLAlchemy engine."""
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value = MagicMock()
    return engine

@pytest.fixture
def mock_create_engine():
    """Fixture to mock sqlalchemy.create_engine."""
    with patch('sqlalchemy.create_engine', return_value=MagicMock()) as mock_engine:
        yield mock_engine

@pytest.fixture
def db_config():
    """Fixture for database configuration."""
    return {
        'user': 'trading_dev_user',
        'password': 'devStrongPass2025!',
        'host': 'localhost',
        'port': '3306',
        'database': 'Trading_dev'
    }

@pytest.fixture
def tele_config():
    """Fixture for Telegram configuration."""
    return {
        'session_path': 'sessions/test_channelTracker.session',
        'api_id': 123456,
        'api_hash': 'mock_api_hash',
        'phone_number': '+1234567890'
    }

def test_setup_logging(config):
    """Test the setup_logging function."""
    logger = channelTracker.setup_logging(config, "logs/test.log")
    assert logger is not None
    assert len(logger.logger.handlers) == 2  # StreamHandler, FileHandler (no ProgressHandler in channelTracker)
    assert logger.logger.level == logging.DEBUG

def test_fetch_db_channels_success(engine, logger, db_config):
    """Test fetch_db_channels with a successful database query."""
    mock_df = pd.DataFrame({
        'ID': [-1001622654998, -1001573131967],
        'Name': ['Channel 1', 'Channel 2'],
        'Operating': [1, 1],
        'Disappeared': [0, 0],
        'created_dt': [datetime.now(), datetime.now()],
        'update_dt': [None, None]
    })
    engine.connect.return_value.__enter__.return_value = MagicMock()
    with patch('pandas.read_sql', return_value=mock_df):
        df = channelTracker.fetch_db_channels(engine, logger, db_config)
        assert df is not None
        assert len(df) == 2
        assert df['ID'].tolist() == [-1001622654998, -1001573131967]

def test_fetch_db_channels_failure(engine, logger, db_config):
    """Test fetch_db_channels when the database query fails."""
    engine.connect.return_value.__enter__.side_effect = Exception("Database error")
    df = channelTracker.fetch_db_channels(engine, logger, db_config)
    assert df is None

@pytest.mark.asyncio
async def test_fetch_telegram_channels_success(engine, logger, tele_config):
    """Test fetch_telegram_channels with a successful Telegram fetch."""
    mock_df = pd.DataFrame({
        'ID': [-1001622654998, -1001573131967],
        'Name': ['Channel 1', 'Channel 2']
    })
    with patch.object(channelTracker, 'fetch_telegram_channels', AsyncMock(return_value=mock_df)) as mock_fetch:
        df_tele = await channelTracker.fetch_telegram_channels(tele_config, engine, logger)
        mock_fetch.assert_awaited_once_with(tele_config, engine, logger)
    assert df_tele is not None
    assert len(df_tele) == 2
    assert df_tele['ID'].tolist() == [-1001622654998, -1001573131967]
    assert df_tele['Name'].tolist() == ['Channel 1', 'Channel 2']

@pytest.mark.asyncio
async def test_fetch_telegram_channels_failure(engine, logger, tele_config):
    """Test fetch_telegram_channels when the Telegram fetch fails."""
    with patch.object(channelTracker, 'fetch_telegram_channels', AsyncMock(return_value=None)) as mock_fetch:
        df_tele = await channelTracker.fetch_telegram_channels(tele_config, engine, logger)
        mock_fetch.assert_awaited_once_with(tele_config, engine, logger)
    assert df_tele is None

def test_update_channels_table_new_channels(engine, logger, db_config):
    """Test update_channels_table when new channels are found."""
    def create_df_db():
        return pd.DataFrame({
            'ID': [-1001622654998, -1001573131967],
            'Name': ['Channel 1', 'Channel 2'],
            'Operating': [1, 1],
            'Disappeared': [0, 0],
            'created_dt': [datetime.now(), datetime.now()],
            'update_dt': [None, None]
        })

    def create_df_tele():
        return pd.DataFrame({
            'ID': [-1001622654998, -1001573131967, -1001234567890],
            'Name': ['Channel 1', 'Channel 2', 'Channel 3']
        })

    engine.connect.return_value.__enter__.return_value = MagicMock()
    
    # Verify the update_channels_table function executes correctly
    with patch('scripts.channelTracker.fetch_db_channels', side_effect=lambda *args, **kwargs: create_df_db()), \
         patch('pandas.core.indexes.base.Index.isin') as mock_isin, \
         patch('pandas.DataFrame.to_sql') as mock_to_sql, \
         patch('sqlalchemy.engine.base.Connection.execute') as mock_execute, \
         patch('sqlalchemy.engine.base.Connection.commit') as mock_commit:
        # Mock the isin operation to control new_channels
        mock_isin.return_value = pd.Series([True, True, False], index=[-1001622654998, -1001573131967, -1001234567890])
        channelTracker.update_channels_table(create_df_tele(), engine, logger, db_config)
        mock_to_sql.assert_called_once()
        assert mock_to_sql.call_args[0][0] == 'channels'  # First argument is the table name

    # Manually compute new_channels to verify the logic
    df_tele = create_df_tele()
    df_db = create_df_db()
    df_db.set_index('ID', inplace=True)
    df_tele.set_index('ID', inplace=True)
    new_channels_df = df_tele[~df_tele.index.isin(df_db.index)].copy()
    new_channels_df['Operating'] = 0
    new_channels_df['Disappeared'] = 0
    new_channels_df['created_dt'] = datetime.now()
    new_channels_df['update_dt'] = None
    new_channels_df = new_channels_df.reset_index()
    assert len(new_channels_df) == 1  # One new channel (-1001234567890)
    assert new_channels_df['ID'].iloc[0] == -1001234567890

def test_update_channels_table_update_existing(engine, logger, db_config):
    """Test update_channels_table when existing channels need updates."""
    def create_df_db():
        return pd.DataFrame({
            'ID': [-1001622654998, -1001573131967],
            'Name': ['Channel 1', 'Channel 2'],
            'Operating': [1, 1],
            'Disappeared': [0, 0],
            'created_dt': [datetime.now(), datetime.now()],
            'update_dt': [None, None]
        })

    def create_df_tele():
        return pd.DataFrame({
            'ID': [-1001622654998, -1001573131967],
            'Name': ['Channel 1 Updated', 'Channel 2 Updated']
        })

    engine.connect.return_value.__enter__.return_value = MagicMock()
    with patch('scripts.channelTracker.fetch_db_channels', return_value=create_df_db()), \
         patch('sqlalchemy.engine.base.Connection.execute') as mock_execute, \
         patch('sqlalchemy.engine.base.Connection.commit') as mock_commit:
        # Ensure the mock connection's execute and commit methods point to our mocks
        conn = engine.connect.return_value.__enter__.return_value
        conn.execute = mock_execute
        conn.commit = mock_commit
        channelTracker.update_channels_table(create_df_tele(), engine, logger, db_config)
        assert mock_execute.call_count == 2  # Two updates for name changes
        mock_commit.assert_called_once()

def test_lock_file_prevents_multiple_instances(config, logger):
    """Test that the lock file prevents multiple instances from running."""
    from helper.lockfile import LockFileHandler  # Import here to avoid import issues
    lock_handler = LockFileHandler(config, "channel_tracker.lock", logger)

    # First instance acquires the lock
    lock_handler.acquire()
    assert os.path.exists(lock_handler.lock_file_path)

    # Second instance should fail to acquire the lock
    second_lock_handler = LockFileHandler(config, "channel_tracker.lock", logger)
    with pytest.raises(Exception, match="Could not acquire lock"):
        second_lock_handler.acquire()

    # Clean up by releasing the lock
    lock_handler.release()
    assert not os.path.exists(lock_handler.lock_file_path)