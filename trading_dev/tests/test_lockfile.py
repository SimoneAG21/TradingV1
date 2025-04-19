# tests/test_lockfile.py
import pytest
import os
from unittest.mock import MagicMock
from helper.lockfile import LockFileHandler
from helper.config_manager import ConfigManager

@pytest.fixture
def mock_config():
    config = MagicMock()
    config.get_with_default.side_effect = lambda section, key, default: {
        ("telegramHistoryRawUpdater", "fetch.lockfile.base_dir", "locks"): "custom_locks",
        ("telegramHistoryRawUpdater", "fetch.lockfile.name", "process.lock"): "custom.lock"
    }.get((section, key, default), default)
    return config

@pytest.fixture
def mock_logger():
    return MagicMock()

def test_lockfile_handler_init_correct_config(mock_config, mock_logger, tmp_path):
    lockfile_name = "test.lock"  # Passed but ignored if config specifies name
    handler = LockFileHandler(mock_config, lockfile_name, mock_logger)
    assert handler.lock_file_dir == "custom_locks"
    assert handler.lock_file_name == "custom.lock"
    assert handler.lock_file_path == os.path.join("custom_locks", "custom.lock")
    mock_config.get_with_default.assert_any_call(
        "telegramHistoryRawUpdater", "fetch.lockfile.base_dir", default="locks"
    )
    mock_config.get_with_default.assert_any_call(
        "telegramHistoryRawUpdater", "fetch.lockfile.name", default="process.lock"
    )

def test_lockfile_handler_init_default_config(mock_config, mock_logger, tmp_path):
    mock_config.get_with_default.side_effect = lambda section, key, default: default
    lockfile_name = "test.lock"
    handler = LockFileHandler(mock_config, lockfile_name, mock_logger)
    assert handler.lock_file_dir == "locks"
    assert handler.lock_file_name == "process.lock"
    assert handler.lock_file_path == os.path.join("locks", "process.lock")
    mock_config.get_with_default.assert_any_call(
        "telegramHistoryRawUpdater", "fetch.lockfile.base_dir", default="locks"
    )
    mock_config.get_with_default.assert_any_call(
        "telegramHistoryRawUpdater", "fetch.lockfile.name", default="process.lock"
    )