import pytest
import os
from unittest.mock import MagicMock, patch
from helper.lockfile import LockFileHandler, LockError
from helper.Logger import Logging

@pytest.fixture
def mock_config():
    config = MagicMock()
    config.get_with_default.side_effect = lambda section, key, default: {
        ("lockfile", "base_dir"): "P:/DynaPOD/proj/trader",
        ("lockfile", "name"): "test_app.lock",
    }.get((section, key), default)
    return config

@pytest.fixture
def logger(mock_config):
    logger = Logging(mock_config, instance_id="test_lockfile")
    yield logger
    logger.close_log()

@pytest.fixture
def lock_handler(mock_config, logger):
    handler = LockFileHandler(mock_config, "test_app", logger)
    yield handler
    handler.release()  # Ensure lock is released after each test

def test_acquire_and_release(lock_handler):
    # Test acquiring the lock
    lock_handler.acquire()
    assert os.path.exists(lock_handler.lock_file_path)

    # Test releasing the lock
    lock_handler.release()
    assert not os.path.exists(lock_handler.lock_file_path)

def test_multiple_instances(lock_handler):
    # Acquire lock with first instance
    lock_handler.acquire()

    # Try to acquire with a second instance
    second_handler = LockFileHandler(lock_handler.config, "test_app", lock_handler.logger)
    with pytest.raises(LockError, match="Failed to acquire lock: another instance of test_app is running"):
        second_handler.acquire()

    # Release the first lock and try again
    lock_handler.release()
    second_handler.acquire()  # Should succeed
    second_handler.release()

def test_context_manager(lock_handler):
    # Test using LockFileHandler as a context manager
    with LockFileHandler(lock_handler.config, "test_app", lock_handler.logger) as handler:
        assert os.path.exists(handler.lock_file_path)
    assert not os.path.exists(lock_handler.lock_file_path)

def test_invalid_config_type(logger):
    with pytest.raises(AttributeError):  # Since config needs get_with_default
        LockFileHandler({}, "test_app", logger)

def test_invalid_logger_type(mock_config):
    with pytest.raises(TypeError):
        LockFileHandler(mock_config, "test_app", "not_logger")

def test_directory_creation_failure(mock_config, logger):
    # Mock os.makedirs to raise an OSError
    mock_config.get_with_default.side_effect = lambda section, key, default: {
        ("lockfile", "base_dir"): "P:/DynaPOD/proj/trader",
        ("lockfile", "name"): "test_app.lock",
    }.get((section, key), default)
    
    with patch("os.makedirs", side_effect=OSError("Permission denied")):
        with pytest.raises(OSError, match="Permission denied"):
            LockFileHandler(mock_config, "test_app", logger)