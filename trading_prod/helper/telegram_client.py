import os
from telethon import TelegramClient
from helper.Logger import Logging

class TelegramClientHandler:
    def __init__(self, config, logger: Logging):
        self.config = config
        self.logger = logger
        self.client = None

    async def get_client(self):
        if self.client is not None:
            return self.client

        api_id = self.config.get_with_default("telegram", "api_id", None)
        api_hash = self.config.get_with_default("telegram", "api_hash", None)
        phone = self.config.get_with_default("telegram", "phone", None)
        session_path = self.config.get_with_default("telegram", "session_path", None)

        for key, value in [("api_id", api_id), ("api_hash", api_hash), ("phone", phone), ("session_path", session_path)]:
            if value is None:
                raise ValueError(f"Missing required Telegram config key: {key}")

        # Ensure the sessions directory exists
        session_dir = os.path.dirname(session_path)
        if session_dir and not os.path.exists(session_dir):
            os.makedirs(session_dir, exist_ok=True)

        try:
            self.client = TelegramClient(session_path, api_id, api_hash)
            await self.client.start(phone=phone)
            self.logger.info(f"Telegram connection established for phone {phone[-4:]}.")
            return self.client
        except Exception as e:
            self.logger.error(f"Error initializing Telegram client for phone {phone[-4:]}: {e}")
            self.client = None
            raise

    async def disconnect(self):
        if self.client is None:
            return

        try:
            await self.client.disconnect()
            self.logger.info(f"Telegram connection closed.")
        except Exception as e:
            self.logger.error(f"Error disconnecting Telegram client: {e}")
            raise
        finally:
            self.client = None