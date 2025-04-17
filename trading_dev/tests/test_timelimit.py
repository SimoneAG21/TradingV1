import pytest
import time
import logging
from unittest.mock import MagicMock
from helper.timelimit import TimeLimitHandler
from helper.Logger import Logging

@pytest.fixture
def mock_config():
    config = MagicMock()
    config.get_with_default.side_effect = lambda section, key, default: {
        ("timelimit", "max_run_time_seconds"): 2,  # Short for testing
    }.get((section, key), default)
    return config

@pytest.fixture
def logger(mock_config):
    logger = Logging(mock_config, instance_id="test_timelimit")
    yield logger
    logger.close_log()

def test_init(mock_config, logger):
    handler = TimeLimitHandler(mock_config, "test_app", logger)
    assert handler.app_name == "test_app"
    assert handler.max_run_time == 2
    assert isinstance(handler.start_time, float)

def test_init_invalid_config_type(logger):
    with pytest.raises(AttributeError):  # No get_with_default method
        TimeLimitHandler({}, "test_app", logger)

def test_init_invalid_logger(mock_config):
    with pytest.raises(TypeError):
        TimeLimitHandler(mock_config, "test_app", "not_logger")

def test_init_invalid_max_run_time(mock_config, logger):
    mock_config.get_with_default.side_effect = lambda section, key, default: -1
    with pytest.raises(ValueError):
        TimeLimitHandler(mock_config, "test_app", logger)

def test_has_exceeded_limit(mock_config, logger):
    handler = TimeLimitHandler(mock_config, "test_app", logger)
    assert not handler.has_exceeded_limit()  # Before limit
    time.sleep(2.1)  # Exceed 2-second limit
    assert handler.has_exceeded_limit()

def test_has_exceeded_limit_logging(mock_config, logger):
    handler = TimeLimitHandler(mock_config, "test_app", logger)
    time.sleep(2.1)
    
    from io import StringIO
    log_capture = StringIO()
    log_handler = logging.StreamHandler(log_capture)
    log_handler.setLevel(logging.INFO)
    logger.logger.addHandler(log_handler)
    
    handler.has_exceeded_limit()
    log_output = log_capture.getvalue()
    assert "Time limit of 2 seconds exceeded" in log_output
    logger.logger.removeHandler(log_handler)

def test_get_elapsed_time(mock_config, logger):
    handler = TimeLimitHandler(mock_config, "test_app", logger)
    time.sleep(0.1)
    elapsed = handler.get_elapsed_time()
    assert 0.09 <= elapsed <= 0.15  # Approximate range