import pytest
import time
import asyncio
import logging
import threading
import pandas as pd
from unittest.mock import MagicMock
from helper.timer import measure_time
from helper.Logger import Logging

@pytest.fixture
def mock_config():
    config = MagicMock()
    config.get_with_default.side_effect = lambda section, key, default: {
        ("logging", "logger_name"): "TestLogger",
        ("logging", "log_stream_level"): "DEBUG",
        ("logging", "logstream_format"): "%(name)s - %(levelname)s - %(message)s",
        ("logging", "log_dir_name"): "logs",
        ("logging", "log_file_max_bytes"): 1000,
        ("logging", "log_file_backup_count"): 2,
        ("logging", "logfile_file_format"): "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    }.get((section, key), default)
    return config

@pytest.fixture
def logger(mock_config):
    logger = Logging(mock_config, instance_id="test_timer")
    yield logger
    logger.close_log()

def test_sync_function_timing(logger):
    @measure_time
    def sync_task():
        time.sleep(0.1)
        return "done"
    
    from io import StringIO
    log_capture = StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setLevel(logging.DEBUG)
    logger.logger.addHandler(handler)
    
    result = sync_task(logger=logger)
    log_output = log_capture.getvalue()
    
    assert result == "done"
    assert "Function 'sync_task' took" in log_output
    assert "seconds" in log_output
    logger.logger.removeHandler(handler)

def test_async_function_timing(logger):
    @measure_time
    async def async_task():
        await asyncio.sleep(0.1)
        return "done"
    
    from io import StringIO
    log_capture = StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setLevel(logging.DEBUG)
    logger.logger.addHandler(handler)
    
    result = asyncio.run(async_task(logger=logger))
    log_output = log_capture.getvalue()
    
    assert result == "done"
    assert "Function 'async_task' took" in log_output
    assert "seconds" in log_output
    logger.logger.removeHandler(handler)

def test_no_logger():
    @measure_time
    def no_log_task():
        time.sleep(0.1)
        return "done"
    
    result = no_log_task()
    assert result == "done"

def test_thread_safety(mock_config):
    logger1 = Logging(mock_config, instance_id="thread1")
    logger2 = Logging(mock_config, instance_id="thread2")
    
    @measure_time
    def thread_task():
        time.sleep(0.1)
        return "done"
    
    from io import StringIO
    log_capture1 = StringIO()
    log_capture2 = StringIO()
    handler1 = logging.StreamHandler(log_capture1)
    handler2 = logging.StreamHandler(log_capture2)
    handler1.setLevel(logging.DEBUG)
    handler2.setLevel(logging.DEBUG)
    logger1.logger.addHandler(handler1)
    logger2.logger.addHandler(handler2)
    
    def run_task1():
        for _ in range(3):
            thread_task(logger=logger1)
    
    def run_task2():
        for _ in range(3):
            thread_task(logger=logger2)
    
    thread1 = threading.Thread(target=run_task1)
    thread2 = threading.Thread(target=run_task2)
    
    thread1.start()
    thread2.start()
    thread1.join()
    thread2.join()
    
    log_output1 = log_capture1.getvalue()
    log_output2 = log_capture2.getvalue()
    
    assert "Function 'thread_task' took" in log_output1
    assert "Function 'thread_task' took" in log_output2
    assert log_output1.count("thread_task") == 3
    assert log_output2.count("thread_task") == 3
    
    logger1.logger.removeHandler(handler1)
    logger2.logger.removeHandler(handler2)
    logger1.close_log()
    logger2.close_log()

def test_short_function_precision(logger):
    @measure_time
    def fast_task():
        return "done"
    
    from io import StringIO
    log_capture = StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setLevel(logging.DEBUG)
    logger.logger.addHandler(handler)
    
    result = fast_task(logger=logger)
    log_output = log_capture.getvalue()
    
    assert result == "done"
    assert "Function 'fast_task' took" in log_output
    assert float(log_output.split("took")[1].split("seconds")[0].strip()) < 0.001
    logger.logger.removeHandler(handler)