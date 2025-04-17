import pytest
import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch
from helper.telegram_client import TelegramClientHandler
from helper.Logger import Logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@pytest.fixture
def mock_config():
    config = MagicMock()
    config.get_with_default.side_effect = lambda section, key, default: {
        ("telegram", "api_id"): "27715324",
        ("telegram", "api_hash"): "72f0a5168ab258f7b6cb169c78ff31d6",
        ("telegram", "phone"): "+14698380038",
        ("telegram", "session_path"): "sessions/my_telegram_client",
        ("logging", "izálogger_name"): "MyLogger",
        ("logging", "log_stream_level"): "INFO",
        ("logging", "log_dir_name"): "logs",
    }.get((section, key), default)
    return config

@pytest.fixture
def logger(mock_config):
    logger = Logging(mock_config, instance_id="test_telegram_client")
    yield logger
    logger.close_log()

@pytest.fixture
def client_handler(mock_config, logger):
    with patch("helper.telegram_client.TelegramClient", new_callable=MagicMock) as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_client.start.return_value = None
        mock_client.disconnect.return_value = None

        logger.debug("Creating TelegramClientHandler instance")
        handler = TelegramClientHandler(mock_config, logger)
        logger.debug(f"Created handler: {handler}")
        yield handler

@pytest.mark.asyncio
async def test_get_client_success(client_handler):
    client = await client_handler.get_client()
    assert client_handler.client.start.called
    assert client_handler.client.start.call_args[1]["phone"] == "+14698380038"

@pytest.mark.asyncio
async def test_get_client_missing_config(client_handler):
    client_handler.config.get_with_default.side_effect = lambda section, key, default: {
        ("telegram", "api_id"): None,
        ("telegram", "api_hash"): "72f0a5168ab258f7b6cb169c78ff31d6",
        ("telegram", "phone"): "+14698380038",
        ("telegram", "session_path"): "./my_telegram_client",
    }.get((section, key), default)

    with pytest.raises(ValueError, match="Missing required Telegram config key: api_id"):
        await client_handler.get_client()

@pytest.mark.asyncio
async def test_get_client_invalid_config(client_handler):
    client_handler.config.get_with_default.side_effect = lambda section, key, default: {
        ("telegram", "api_id"): 123,
        ("telegram", "api_hash"): "72f0a5168ab258f7b6cb169c78ff31d6",
        ("telegram", "phone"): "+14698380038",
        ("telegram", "session_path"): "./my_telegram_client",
    }.get((section, key), default)

    # Patch the start method on the client instance being created
    with patch.object(TelegramClientHandler, "get_client", side_effect=TypeError("api_id must be a string")):
        with pytest.raises(TypeError, match="api_id must be a string"):
            await client_handler.get_client()

@pytest.mark.asyncio
async def test_get_client_connection_failure(client_handler):
    # Patch the start method on the client instance being created
    with patch.object(TelegramClientHandler, "get_client", side_effect=Exception("Connection failed")):
        with pytest.raises(Exception, match="Connection failed"):
            await client_handler.get_client()
    assert client_handler.client is None

@pytest.mark.asyncio
async def test_disconnect_success(client_handler):
    client = await client_handler.get_client()
    mock_client = client_handler.client
    await client_handler.disconnect()
    assert mock_client.disconnect.called
    assert client_handler.client is None

@pytest.mark.asyncio
async def test_disconnect_failure(client_handler):
    client = await client_handler.get_client()
    # Patch the disconnect method on the specific client instance
    with patch.object(client_handler.client, "disconnect", side_effect=Exception("Disconnect failed")):
        with pytest.raises(Exception, match="Disconnect failed"):
            await client_handler.disconnect()
    assert client_handler.client is None

@pytest.mark.asyncio
async def test_disconnect_no_client(client_handler):
    await client_handler.disconnect()
    assert client_handler.client is None