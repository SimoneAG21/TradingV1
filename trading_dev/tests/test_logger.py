#.\tests\test_logger.py

"""
Test suite for the Logging class in helper/logger.py.

Overview:
This test suite verifies the functionality of the Logging class, including instance creation,
console and file logging, log file rotation, DataFrame logging, and thread safety for
multiple instances. It uses pytest fixtures to set up a temporary directory and mock
ConfigManager for consistent testing.

Usage:
- Run all tests: `pytest tests/test_logger.py -v`
- Run specific test: `pytest tests/test_logger.py::test_instance_creation -v`
- Run with coverage: `pytest --cov=helper tests/test_logger.py`
- Discover tests: `pytest --collect-only`

Dependencies:
- pytest: Testing framework
- pytest-mock: For mocking dependencies
- pandas: For DataFrame testing
- helper.config_manager.ConfigManager: Mocked for configuration
- helper.logger.Logging: The class under test
"""
import pytest
import os
import logging
import pandas as pd
import threading
from unittest.mock import MagicMock
from helper.Logger import Logging

@pytest.fixture
def temp_dir(tmp_path):
    return tmp_path

@pytest.fixture
def mock_config():
    config = MagicMock()
    config.get_with_default.side_effect = lambda section, key, default: {
        ("logging", "logger_name"): "TestLogger",
        ("logging", "log_stream_level"): "INFO",
        ("logging", "logstream_format"): "%(name)s - %(levelname)s - %(message)s",
        ("logging", "log_dir_name"): "logs",
        ("logging", "log_file_max_bytes"): 1000,
        ("logging", "log_file_backup_count"): 2,
        ("logging", "logfile_file_format"): "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    }.get((section, key), default)
    return config

def test_instance_creation(mock_config):
    logger = Logging(mock_config, instance_id="test1")
    assert logger.logger.name == "TestLogger.test1"
    assert logger.logger.level == logging.DEBUG
    assert any(isinstance(h, logging.StreamHandler) for h in logger.logger.handlers)
    logger.close_log()

def test_multiple_instances(mock_config):
    logger1 = Logging(mock_config, instance_id="job1")
    logger2 = Logging(mock_config, instance_id="job2")
    assert logger1.logger.name == "TestLogger.job1"
    assert logger2.logger.name == "TestLogger.job2"
    assert logger1.logger is not logger2.logger
    logger1.close_log()
    logger2.close_log()

def test_set_log_file(temp_dir, mock_config):
    mock_config.get_with_default.side_effect = lambda section, key, default: str(temp_dir) if (section, key) == ("logging", "log_dir_name") else {
        ("logging", "logger_name"): "TestLogger",
        ("logging", "log_stream_level"): "INFO",
        ("logging", "logstream_format"): "%(name)s - %(levelname)s - %(message)s",
        ("logging", "log_file_max_bytes"): 1000,
        ("logging", "log_file_backup_count"): 2,
        ("logging", "logfile_file_format"): "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    }.get((section, key), default)
    
    logger = Logging(mock_config, instance_id="test")
    logger.set_log_file("test_job")
    log_file = os.path.join(temp_dir, "test_job.log")
    
    logger.info("Test message")
    assert os.path.exists(log_file)
    with open(log_file, 'r', encoding='utf-8') as f:
        content = f.read()
        assert "Test message" in content
    logger.close_log()

def test_log_file_rotation(temp_dir, mock_config):
    mock_config.get_with_default.side_effect = lambda section, key, default: str(temp_dir) if (section, key) == ("logging", "log_dir_name") else {
        ("logging", "logger_name"): "TestLogger",
        ("logging", "log_stream_level"): "INFO",
        ("logging", "logstream_format"): "%(name)s - %(levelname)s - %(message)s",
        ("logging", "log_file_max_bytes"): 100,
        ("logging", "log_file_backup_count"): 2,
        ("logging", "logfile_file_format"): "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    }.get((section, key), default)
    
    logger = Logging(mock_config, instance_id="rotation")
    logger.set_log_file("rotate_job")
    log_file = os.path.join(temp_dir, "rotate_job.log")
    
    for _ in range(10):
        logger.info("A" * 50)
    
    assert os.path.exists(log_file)
    assert any(os.path.exists(os.path.join(temp_dir, f"rotate_job.log.{i}")) for i in range(1, 3))
    logger.close_log()

def test_log_df_fld_info(mock_config):
    logger = Logging(mock_config, instance_id="df_test")
    df = pd.DataFrame({"col1": [1, 1, 2, 3], "col2": ["a", "b", "a", "c"]})
    
    from io import StringIO
    log_capture = StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setLevel(logging.INFO)
    logger.logger.addHandler(handler)
    
    logger.log_df_fld_info(df, "test_df", "col1")
    
    log_output = log_capture.getvalue()
    assert "Analyzing test_df on column col1" in log_output
    assert "Value 1 Its count is :: 2" in log_output
    assert "Value 2 Its count is :: 1" in log_output
    assert "Value 3 Its count is :: 1" in log_output
    
    logger.logger.removeHandler(handler)
    logger.close_log()

def test_log_levels(mock_config):
    logger = Logging(mock_config, instance_id="levels")
    
    from io import StringIO
    log_capture = StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setLevel(logging.DEBUG)
    logger.logger.addHandler(handler)
    
    logger.debug("Debug message")
    logger.info("Info message")
    logger.warning("Warning message")
    logger.error("Error message")
    logger.critical("Critical message")
    
    log_output = log_capture.getvalue()
    assert "Debug message" in log_output
    assert "Info message" in log_output
    assert "Warning message" in log_output
    assert "Error message" in log_output
    assert "Critical message" in log_output
    
    logger.logger.removeHandler(handler)
    logger.close_log()

def test_thread_safety(temp_dir, mock_config):
    mock_config.get_with_default.side_effect = lambda section, key, default: str(temp_dir) if (section, key) == ("logging", "log_dir_name") else {
        ("logging", "logger_name"): "TestLogger",
        ("logging", "log_stream_level"): "INFO",
        ("logging", "logstream_format"): "%(name)s - %(levelname)s - %(message)s",
        ("logging", "log_file_max_bytes"): 1000,
        ("logging", "log_file_backup_count"): 2,
        ("logging", "logfile_file_format"): "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    }.get((section, key), default)
    
    logger1 = Logging(mock_config, instance_id="thread1")
    logger2 = Logging(mock_config, instance_id="thread2")
    logger1.set_log_file("thread1_job")
    logger2.set_log_file("thread2_job")
    
    log_file1 = os.path.join(temp_dir, "thread1_job.log")
    log_file2 = os.path.join(temp_dir, "thread2_job.log")
    
    def log_thread1():
        for _ in range(5):
            logger1.info("Thread1 message")
    
    def log_thread2():
        for _ in range(5):
            logger2.info("Thread2 message")
    
    thread1 = threading.Thread(target=log_thread1)
    thread2 = threading.Thread(target=log_thread2)
    
    thread1.start()
    thread2.start()
    thread1.join()
    thread2.join()
    
    assert os.path.exists(log_file1)
    assert os.path.exists(log_file2)
    
    with open(log_file1, 'r', encoding='utf-8') as f:
        content1 = f.read()
        assert "Thread1 message" in content1
        assert "Thread2 message" not in content1
    
    with open(log_file2, 'r', encoding='utf-8') as f:
        content2 = f.read()
        assert "Thread2 message" in content2
        assert "Thread1 message" not in content2
    
    logger1.close_log()
    logger2.close_log()