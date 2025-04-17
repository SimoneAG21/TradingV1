#tests/test_database.py
import pytest
import os
from unittest.mock import patch, MagicMock
from helper.config_manager import ConfigManager
from helper.database import DatabaseHandler
from helper.Logger import Logging

@pytest.fixture
def mock_config():
    """
    Fixture providing a ConfigManager instance for database tests.

    Loads tests/combined_config_test.yaml with project_root set to the parent directory of tests/.
    """
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    config = ConfigManager('tests/combined_config_test.yaml', project_root=project_root)
    return config

@pytest.fixture
def logger(mock_config):
    """
    Fixture providing a Logging instance for database tests.
    """
    return Logging(mock_config, "MyLogger")

def test_create_engine(mock_config, logger):
    with patch("helper.database.create_engine") as mock_create_engine:
        handler = DatabaseHandler(mock_config, logger)
        expected_url = (
            "mysql+mysqlconnector://test_user:test_pass@localhost:3306/test_db"
        )
        mock_create_engine.assert_called_once_with(expected_url)

def test_get_engine(mock_config, logger):
    with patch("helper.database.create_engine") as mock_create_engine:
        mock_engine = MagicMock()
        mock_connection = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_connection
        mock_create_engine.return_value = mock_engine
        handler = DatabaseHandler(mock_config, logger)
        assert handler.get_engine() == mock_engine

def test_init_success(mock_config):
    assert mock_config.get('database', 'mysql.user') == 'test_user', "Failed to get database.mysql.user"
    assert mock_config.get('database', 'mysql.database') == 'test_db', "Failed to get database.mysql.database"

def test_init_invalid_config(logger):
    with pytest.raises(ValueError):
        config = MagicMock()
        config.get.return_value = None
        DatabaseHandler(config, logger)

def test_init_invalid_logger(mock_config):
    with pytest.raises(AttributeError):
        DatabaseHandler(mock_config, None)

def test_init_missing_config_key(mock_config, logger):
    with patch.object(mock_config, 'get', return_value=None):
        with pytest.raises(ValueError):
            DatabaseHandler(mock_config, logger)

def test_test_connection_success(mock_config, logger):
    with patch("helper.database.create_engine") as mock_create_engine:
        mock_engine = MagicMock()
        mock_connection = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_connection
        mock_create_engine.return_value = mock_engine
        handler = DatabaseHandler(mock_config, logger)

def test_test_connection_failure(mock_config, logger):
    with patch("helper.database.create_engine") as mock_create_engine:
        mock_engine = MagicMock()
        mock_engine.connect.side_effect = Exception("Connection failed")
        mock_create_engine.return_value = mock_engine
        with pytest.raises(Exception):
            handler = DatabaseHandler(mock_config, logger)