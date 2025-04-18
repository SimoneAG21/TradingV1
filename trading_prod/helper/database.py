#helper/database.py
from sqlalchemy import create_engine

class DatabaseHandler:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.engine = None
        if all(self.config.get('database', 'mysql.' + key) for key in ['user', 'password', 'host', 'database']):
            self._create_engine()
            self._test_connection()
        else:
            self.logger.error("Missing required database configuration keys")
            raise ValueError("Missing required database configuration keys")

    def _create_engine(self):
        try:
            connection_string = (
                f"mysql+mysqlconnector://"
                f"{self.config.get('database', 'mysql.user')}:{self.config.get('database', 'mysql.password')}@"
                f"{self.config.get('database', 'mysql.host')}:{self.config.get('database', 'mysql.port')}/"
                f"{self.config.get('database', 'mysql.database')}"
            )
            self.logger.info(f"Creating SQLAlchemy engine with connection string: {connection_string}")
            self.engine = create_engine(connection_string)
            self.logger.info(f"Engine created: {self.engine}")
        except Exception as e:
            self.logger.error(f"Failed to create SQLAlchemy engine: {e}")
            raise

    def _test_connection(self):
        try:
            with self.engine.connect() as conn:
                self.logger.info(f"Connection to {self.config.get('database', 'mysql.database')} successful!")
        except Exception as e:
            self.logger.error(f"Error connecting to MySQL: {e}")
            raise

    def get_engine(self):
        return self.engine