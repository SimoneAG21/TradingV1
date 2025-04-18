# helper/lockfile.py
"""
Overview:
This module provides a LockFileHandler class for the #SeanProjectTrading project, managing
lock files to prevent multiple instances of a script from running simultaneously.

Purpose:
- Ensures only one instance of a script runs at a time.
- Configurable lock file path via YAML configuration, stored under project base directory.
- Automatically releases and deletes the lock file on script completion or failure.
- Cross-platform support using portalocker for file locking.

Usage:
- Instantiate: `lock_handler = LockFileHandler(config, app_name, logger)`
- Acquire lock: `lock_handler.acquire()` (raises LockError if lock fails)
- Release lock: `lock_handler.release()` (called automatically on script exit)

Dependencies:
- portalocker: For cross-platform file locking.
- os: For file and directory operations.
- helper.config_manager.ConfigManager: For reading lock file path from config.
- helper.Logger.Logging: For logging lock events.
"""
import os
import portalocker
from typing import Optional

try:
    from helper.config_manager import ConfigManager
    from helper.Logger import Logging
except ImportError as e:
    raise ImportError(f"Failed to import dependencies: {e}")

class LockError(Exception):
    """Raised when lock acquisition fails."""
    pass

class LockFileHandler:
    def __init__(self, config: ConfigManager, app_name: str, logger: Logging) -> None:
        """
        Initialize the LockFileHandler with configuration and logger.

        Args:
            config (ConfigManager): Configuration object with get_with_default method.
            app_name (str): Name of the application (e.g., 'telegramHistoryFetcherCatchUp').
            logger (Logging): Logger instance for logging lock events.

        Raises:
            TypeError: If logger is not a Logging instance.
            OSError: If the lock file directory cannot be created.
        """
        if not isinstance(logger, Logging):
            raise TypeError("logger must be a Logging instance")

        self.config = config
        self.app_name = app_name
        self.logger = logger
        
        # Get project base directory and lock file name from config
        project_base_dir = self.config.get_with_default(
            "lockfile", "base_dir", default="/home/sean/shared/trading_dev/"
        )
        lock_file_name = self.config.get_with_default(
            "lockfile", "name", default=f"{app_name}.lock"
        )
        
        # Construct lock file path: project_base_dir/locks/lock_file_name
        self.lock_file_dir = os.path.join(project_base_dir, "locks")
        self.lock_file_path = os.path.join(self.lock_file_dir, lock_file_name)
        
        # Create locks directory if it doesn't exist
        try:
            os.makedirs(self.lock_file_dir, exist_ok=True)
        except OSError as e:
            self.logger.error(f"Failed to create lock file directory {self.lock_file_dir}: {e}")
            raise
        
        self.lock_fd: Optional[object] = None

    def acquire(self) -> None:
        """
        Attempt to acquire the lock by creating/opening the lock file and locking it.
        If the lock cannot be acquired, raises LockError.

        Raises:
            LockError: If another instance is already running (lock cannot be acquired).
            OSError: If the lock file cannot be opened or locked.
        """
        self.logger.info(f"Attempting to acquire lock at {self.lock_file_path}")
        try:
            self.lock_fd = open(self.lock_file_path, 'w')
            portalocker.lock(self.lock_fd, portalocker.LOCK_EX | portalocker.LOCK_NB)
            self.logger.info(f"Successfully acquired lock at {self.lock_file_path}")
        except portalocker.exceptions.LockException as e:
            self.logger.info(f"Another instance of {self.app_name} is running. Cannot acquire lock.")
            if self.lock_fd is not None:
                self.lock_fd.close()
            raise LockError(f"Failed to acquire lock: another instance of {self.app_name} is running") from e
        except OSError as e:
            self.logger.error(f"Error acquiring lock for {self.app_name}: {e}")
            if self.lock_fd is not None:
                self.lock_fd.close()
            raise

    def release(self) -> None:
        """
        Release the lock by unlocking the file, closing it, and deleting it from the file system.

        Raises:
            OSError: If the lock file cannot be unlocked or deleted.
        """
        if self.lock_fd is not None:
            try:
                portalocker.unlock(self.lock_fd)
                self.lock_fd.close()
                if os.path.exists(self.lock_file_path):
                    os.remove(self.lock_file_path)
                    self.logger.info(f"Deleted lock file at {self.lock_file_path}")
                self.logger.info(f"Released lock for {self.app_name}")
            except OSError as e:
                self.logger.error(f"Error releasing lock for {self.app_name}: {e}")
                raise
            finally:
                self.lock_fd = None

    def __enter__(self) -> "LockFileHandler":
        """
        Context manager entry: acquire the lock.

        Returns:
            LockFileHandler: The instance itself.
        """
        self.acquire()
        return self

    def __exit__(self, exc_type: Optional[type], exc_val: Optional[Exception], exc_tb: Optional[object]) -> None:
        """
        Context manager exit: release the lock, even if an exception occurs.
        """
        self.release()