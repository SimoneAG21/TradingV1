# helper/database.py
"""
Overview:
This module provides a DatabaseHandler class for the #SeanProjectTrading project, managing
database connections using SQLAlchemy.

Purpose:
- Encapsulates database connection setup and testing.
- Reusable across scripts that need database access.

Usage:
- Instantiate: `db_handler = DatabaseHandler(config, logger)`
- Get engine: `engine = db_handler.get_engine()`

Dependencies:
- `sqlalchemy`: For database connections.
- `helper.config_manager.ConfigManager`: For reading database settings.
- `helper.Logger.Logging`: For logging database events.
"""
# helper/database.py
from sqlalchemy import create_engine

class DatabaseHandler:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.engine = None
        if all(self.config.get('database', key) for key in ['user', 'password', 'host', 'database']):
            self._create_engine()
            self._test_connection()
        else:
            self.logger.error("Missing required database configuration keys")
            raise ValueError("Missing required database configuration keys")

    def _create_engine(self):
        try:
            connection_string = (
                f"mysql+mysqlconnector://"
                f"{self.config.get('database', 'user')}:"
                f"{self.config.get('database', 'password')}@"
                f"{self.config.get('database', 'host')}/"
                f"{self.config.get('database', 'database')}"
            )
            self.engine = create_engine(connection_string)
            self.logger.info(f"Database engine created for {self.config.get('database', 'database')}")
        except Exception as e:
            self.logger.error(f"Error creating SQLAlchemy engine: {e}")
            raise

    def _test_connection(self):
        try:
            with self.engine.connect() as conn:
                self.logger.info(f"Connection to {self.config.get('database', 'database')} successful!")
        except Exception as e:
            self.logger.error(f"Error connecting to MySQL: {e}")
            raise

    def get_engine(self):
        return self.engine