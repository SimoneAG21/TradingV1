# .\helper\Logger.py

"""
Overview:
This module provides a `Logging` class for the #SeanProjectTrading project, managing 
centralized logging with file rotation and console output. It integrates with `ConfigManager` 
for configuration, supports custom log levels, formats, and DataFrame analysis logging, 
and allows multiple instances for thread-specific log files.

Purpose:
- Enables thread-specific logging with separate log files for each process.
- Provides file-based logging with rotation and console output based on configuration.
- Offers a utility to log DataFrame field information with timing.

Usage:
- Instantiate: `logger = Logging(config, instance_id="job1")` (pass a ConfigManager and optional instance ID).
- Set log file: `logger.set_log_file("job_name")` to start file logging.
- Use methods like `debug(msg)`, `info(msg)`, etc., to log messages.
- Use `log_df_fld_info(df, name, column)` for DataFrame analysis logging.
- Call `logger.close_log()` to clean up handlers when done.

Dependencies:
- `logging`: Core Python logging module.
- `os`: For directory and file path handling.
- `logging.handlers.RotatingFileHandler`: For log file rotation.
- `threading`: For thread-safe logging.
- `helper.config_manager.ConfigManager`: For logging configuration.
- `helper.timer.measure_time`: For timing the DataFrame logging method.
"""
import logging
import os
import threading
from logging.handlers import RotatingFileHandler
try:
    from helper.config_manager import ConfigManager
    from helper.timer import measure_time
except ImportError as e:
    print(f"Error importing modules: {e}")
    raise

class Logging:
    _lock = threading.Lock()

    def __init__(self, config: ConfigManager, instance_id: str = None):
        """
        Initialize a Logging instance with thread-specific configuration.

        Args:
            config (ConfigManager): A ConfigManager instance with the desired config file.
            instance_id (str, optional): Unique identifier for the logger instance.

        Raises:
            ValueError: If no config is provided.
        """
        if config is None:
            raise ValueError("A ConfigManager instance is required for Logging initialization")
        self.config = config
        self.instance_id = instance_id or f"logger_{id(self)}"
        self.logger = None
        self._initialize_logger()

    def _initialize_logger(self):
        """
        Initialize the logger with configuration, setting up console logging only.

        Raises:
            Exception: If logger initialization fails.
        """
        try:
            logger_name = self.config.get_with_default("logging", "logger_name", default="MyLogger")
            if self.instance_id:
                logger_name = f"{logger_name}.{self.instance_id}"
            self.logger = logging.getLogger(logger_name)
            self.logger.setLevel(logging.DEBUG)

            if not self.logger.handlers:
                stream_level = self.config.get_with_default("logging", "log_stream_level", default="INFO").upper()
                stream_level = getattr(logging, stream_level, logging.INFO)
                stream_handler = logging.StreamHandler()
                stream_handler.setLevel(stream_level)
                stream_formatter = logging.Formatter(
                    self.config.get_with_default(
                        "logging",
                        "logstream_format",
                        default="%(filename)s:%(funcName)s - %(levelname)s - %(message)s"
                    )
                )
                stream_handler.setFormatter(stream_formatter)
                self.logger.addHandler(stream_handler)

                self.logger.debug("Logger initialized with console output only; file logging deferred to set_log_file")
        except Exception as e:
            print(f"Error initializing logger: {e}")
            raise

    def set_log_file(self, job_name: str):
        """
        Set a job-specific log file name and initialize file handlers thread-safely.

        Args:
            job_name (str): The name of the job (e.g., "telegram_fetch_dev") to use as the log file base.

        Notes:
            Switches logging to `logs/{job_name}.log`, replacing any existing file handler.
        """
        with self._lock:
            log_dir = self.config.get_with_default("logging", "log_dir_name", default="logs")
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, f"{job_name}.log")
            has_file_handler = any(isinstance(h, RotatingFileHandler) for h in self.logger.handlers)
            if has_file_handler:
                for handler in self.logger.handlers[:]:
                    if isinstance(handler, RotatingFileHandler):
                        handler.close()
                        self.logger.removeHandler(handler)
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=self.config.get_with_default("logging", "log_file_max_bytes", default=10485760),
                backupCount=self.config.get_with_default("logging", "log_file_backup_count", default=10),
                encoding="utf-8"
            )
            file_handler.setLevel(logging.DEBUG)
            file_formatter = logging.Formatter(
                self.config.get_with_default(
                    "logging",
                    "logfile_file_format",
                    default="%(asctime)s - %(filename)s:%(funcName)s - %(levelname)s - %(message)s"
                )
            )
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)
            self.logger.debug(f"Switched to log file: {log_file}")

    @measure_time
    def log_df_fld_info(self, df, name: str, column: str, logger=None):
        """
        Log DataFrame field information with timing.

        Args:
            df: DataFrame to analyze.
            name (str): Name of the DataFrame or analysis context.
            column (str): Column to analyze.
            logger: Optional logger to use; defaults to self.logger.
        """
        if logger is None:
            logger = self.logger
        logger.info(f"Analyzing {name} on column {column}")
        value_counts = df[column].value_counts()
        for value, count in value_counts.items():
            logger.info(f"Value {value} Its count is :: {count}")

    def debug(self, msg: str):
        """Log a debug message."""
        msg = msg.encode('ascii', 'ignore').decode('ascii') if isinstance(msg, str) else str(msg)
        self.logger.debug(msg)

    def info(self, msg: str):
        """Log an info message."""
        self.logger.info(msg)

    def warning(self, msg: str):
        """Log a warning message."""
        self.logger.warning(msg)

    def error(self, msg: str, exc_info=None):
        """Log an error message, optionally with exception stack trace."""
        self.logger.error(msg, exc_info=exc_info)

    def critical(self, msg: str):
        """Log a critical message."""
        self.logger.critical(msg)

    def log(self, level: int, msg: str):
        """Log a message at the specified level."""
        self.logger.log(level, msg)

    def close_log(self):
        """
        Clean up logger handlers for this instance.

        Notes:
            Removes and closes all handlers for the instance's logger.
        """
        with self._lock:
            if self.logger:
                for handler in self.logger.handlers[:]:
                    handler.close()
                    self.logger.removeHandler(handler)
                self.logger = None