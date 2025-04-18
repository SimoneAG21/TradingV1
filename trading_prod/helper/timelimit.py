# helper/timelimit.py
"""
Overview:
This module provides a TimeLimitHandler class for the #SeanProjectTrading project, managing
the maximum run time for a script to ensure it doesn't exceed a configured time limit.

Purpose:
- Tracks elapsed time since script start.
- Configurable time limit via YAML configuration.
- Checks if the time limit is exceeded, logging via Logging class.

Usage:
- Instantiate: `time_limit = TimeLimitHandler(config, app_name, logger)`
- Check: `if time_limit.has_exceeded_limit(): ...`

Dependencies:
- time: For tracking elapsed time.
- helper.config_manager.ConfigManager: For time limit settings.
- helper.Logger.Logging: For logging time limit events.
"""
import time
try:
    from helper.config_manager import ConfigManager
    from helper.Logger import Logging
except ImportError as e:
    raise ImportError(f"Failed to import dependencies: {e}")

class TimeLimitHandler:
    def __init__(self, config, app_name: str, logger: Logging):
        """
        Initialize the TimeLimitHandler with configuration and logger.

        Args:
            config: Configuration object with get_with_default method.
            app_name (str): Application name (e.g., 'telegram_fetch').
            logger (Logging): Logger instance for time limit events.

        Raises:
            TypeError: If logger is not a Logging instance.
            ValueError: If max_run_time is not a positive number.
        """
        if not isinstance(logger, Logging):
            raise TypeError("logger must be a Logging instance")
        self.config = config
        self.app_name = app_name
        self.logger = logger
        
        # Get max run time (in seconds)
        self.max_run_time = self.config.get_with_default(
            "timelimit", "max_run_time_seconds", default=3600
        )
        if not isinstance(self.max_run_time, (int, float)) or self.max_run_time <= 0:
            raise ValueError("max_run_time_seconds must be a positive number")
        
        self.logger.debug(f"Time limit set to {self.max_run_time} seconds for {self.app_name}")
        self.start_time = time.time()
        self.logger.debug(f"Start time recorded: {self.start_time}")

    def has_exceeded_limit(self) -> bool:
        """
        Check if the script has exceeded the maximum run time.

        Returns:
            bool: True if elapsed time exceeds max_run_time, False otherwise.
        """
        elapsed_time = time.time() - self.start_time
        if elapsed_time > self.max_run_time:
            self.logger.info(f"Time limit of {self.max_run_time} seconds exceeded. Elapsed: {elapsed_time:.2f} seconds")
            return True
        return False

    def get_elapsed_time(self) -> float:
        """
        Get the elapsed time since the script started.

        Returns:
            float: Elapsed time in seconds.
        """
        return time.time() - self.start_time