import os
import fcntl
import time

class LockFileHandler:
    """
    Manages a lock file to ensure a single instance of a process runs.
    """
    def __init__(self, config, lockfile_name, logger):
        """
        Initialize LockFileHandler with configuration, lockfile name, and logger.

        Args:
            config: ConfigManager instance for accessing configuration settings.
            lockfile_name (str): Identifier for the lockfile (not used directly; config takes precedence).
            logger: Logging instance for logging lockfile operations.
        """
        self.config = config
        self.logger = logger
        self.lock_file_dir = config.get_with_default(
            "telegramHistoryRawUpdater", "fetch.lockfile.base_dir", default="locks"
        )
        # Prioritize config's lockfile name, not the passed lockfile_name
        self.lock_file_name = config.get_with_default(
            "telegramHistoryRawUpdater", "fetch.lockfile.name", default="process.lock"
        )
        self.lock_file_path = os.path.join(self.lock_file_dir, self.lock_file_name)
        os.makedirs(self.lock_file_dir, exist_ok=True)
        self.logger.debug(f"LockFileHandler initialized with lock file: {self.lock_file_path}")
        self.lock_file = None

    def acquire(self):
        """
        Attempt to acquire the lock by creating or opening the lock file.

        Raises:
            RuntimeError: If the lock cannot be acquired.
        """
        try:
            self.lock_file = open(self.lock_file_path, 'w')
            fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.logger.debug(f"Acquired lock on {self.lock_file_path}")
        except (IOError, OSError) as e:
            self.logger.error(f"Failed to acquire lock on {self.lock_file_path}: {e}")
            raise RuntimeError(f"Could not acquire lock: {e}")

    def release(self):
        """
        Release the lock and clean up the lock file.
        """
        if self.lock_file:
            try:
                fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_UN)
                self.lock_file.close()
                if os.path.exists(self.lock_file_path):
                    os.remove(self.lock_file_path)
                self.logger.debug(f"Released lock and removed {self.lock_file_path}")
            except (IOError, OSError) as e:
                self.logger.error(f"Failed to release lock on {self.lock_file_path}: {e}")
            finally:
                self.lock_file = None

    def __del__(self):
        """
        Ensure the lock is released when the object is destroyed.
        """
        self.release()