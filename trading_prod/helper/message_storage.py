# helper/message_storage.py
"""
Overview:
This module provides a MessageStorageHandler class for the TradingV1 project, managing the storage
of Telegram messages and their metadata in the file system and database.

Purpose:
- Stores Telegram messages as JSON files in a temporary directory.
- Downloads associated media (photos, videos, documents) and links them to messages.
- Logs batch statistics and updates the database with batch metadata and channel information.
- Integrates with the `telegram_data` schema (tables: `channel_fetch_batches`, `channels`).

Usage:
- Instantiate: `storage = MessageStorageHandler(config, logger, engine)`
- Store messages: `await storage.store_messages(messages, channel_id, client)`

Dependencies:
- json: For serializing message data to JSON.
- os: For file and directory operations.
- sqlalchemy.sql.text: For SQL queries.
- helper.timezone: For timestamp formatting and timezone conversion.
"""
import json
import os
from typing import List, Any, Optional
from sqlalchemy.sql import text
from sqlalchemy.engine import Engine

try:
    from helper.config_manager import ConfigManager
    from helper.Logger import Logging
    from helper.timezone import get_formatted_timestamp, to_local_time
except ImportError as e:
    raise ImportError(f"Failed to import dependencies: {e}")

class MessageStorageHandler:
    def __init__(self, config: ConfigManager, logger: Logging, engine: Engine) -> None:
        """
        Initialize the MessageStorageHandler with configuration, logger, and database engine.

        Args:
            config (ConfigManager): Configuration object with message storage settings.
            logger (Logging): Logger instance for logging storage events.
            engine (Engine): SQLAlchemy engine for database operations.

        Raises:
            TypeError: If logger is not a Logging instance or engine is not an Engine instance.
        """
        if not isinstance(logger, Logging):
            raise TypeError("logger must be a Logging instance")
        if not isinstance(engine, Engine):
            raise TypeError("engine must be a SQLAlchemy Engine instance")

        self.config = config
        self.logger = logger
        self.engine = engine

        # Get temporary storage directory from config
        self.temp_dir = self.config.get_with_default(
            "message_storage", "temp_dir", default="temp_messages"
        )
        self.media_subdir = self.config.get_with_default(
            "message_storage", "media_subdir", default="media"
        )

    async def store_messages(self, messages: List[Any], channel_id: str, client: Any) -> None:
        """
        Store messages in the file system and update the database.

        Args:
            messages (List[Any]): List of Telegram messages to store.
            channel_id (str): ID of the Telegram channel.
            client (Any): Telegram client for downloading media.

        Raises:
            OSError: If file operations (directory creation, file writing) fail.
            Exception: If database operations fail.
        """
        # Set up directories
        channel_dir = os.path.join(self.temp_dir, str(channel_id))
        media_dir = os.path.join(channel_dir, self.media_subdir)
        os.makedirs(channel_dir, exist_ok=True)
        os.makedirs(media_dir, exist_ok=True)

        timestamp = get_formatted_timestamp()
        msg_filename = os.path.join(channel_dir, f"batch_{timestamp}.json")
        stats_filename = os.path.join(channel_dir, f"batch_{timestamp}_stats.json")

        # Process messages
        temp_data = []
        for msg in messages:
            msg_data = {
                "channel_id": channel_id,
                "message_id": msg.id,
                "timestamp": to_local_time(msg.date).isoformat(),
                "text": msg.text if msg.text else None,
                "sender_id": msg.sender_id if msg.sender_id else None,
                "reply_to_msg_id": msg.reply_to_msg_id if msg.reply_to_msg_id else None,
                "media": None
            }
            if msg.media:
                try:
                    ext = ".bin"
                    if msg.photo:
                        ext = ".jpg"
                    elif msg.video:
                        ext = ".mp4"
                    elif msg.document and msg.document.attributes:
                        ext = "." + msg.document.attributes[-1].file_name.split('.')[-1]

                    # Include channel_id in media filename to avoid conflicts
                    media_path = os.path.join(media_dir, f"{channel_id}_{msg.id}_{timestamp}{ext}")
                    await client.download_media(msg, file=media_path)
                    msg_data["media"] = {
                        "path": media_path,
                        "type": "photo" if msg.photo else ("video" if msg.video else "document"),
                        "size": os.path.getsize(media_path) if os.path.exists(media_path) else 0
                    }
                except Exception as e:
                    self.logger.error(f"Error downloading media for msg {msg.id} in channel {channel_id}: {e}")
            temp_data.append(msg_data)

        # Store messages as JSON
        try:
            with open(msg_filename, 'w') as f:
                json.dump(temp_data, f, indent=4)
            self.logger.info(f"Stored {len(temp_data)} messages in {msg_filename}")
        except OSError as e:
            self.logger.error(f"Error storing messages for channel {channel_id}: {e}")
            raise

        # Store batch stats
        if messages:
            stat_data = {
                "channel_id": channel_id,
                "batch_timestamp": timestamp,
                "first_message_id": messages[0].id,
                "first_timestamp": to_local_time(messages[0].date).isoformat(),
                "last_message_id": messages[-1].id,
                "last_timestamp": to_local_time(messages[-1].date).isoformat(),
                "message_count": len(messages)
            }
            try:
                with open(stats_filename, 'w') as f:
                    json.dump(stat_data, f, indent=4)
                self.logger.info(f"Saved batch stats to {stats_filename}")
            except OSError as e:
                self.logger.error(f"Error saving batch stats for channel {channel_id}: {e}")
                raise

            # Update database within a transaction
            try:
                with self.engine.connect() as conn:
                    # Begin transaction
                    with conn.begin():
                        # Insert into channel_fetch_batches
                        conn.execute(
                            text("""
                                INSERT INTO channel_fetch_batches (
                                    channel_id, batch_timestamp, message_file_path,
                                    first_message_id, first_timestamp,
                                    last_message_id, last_timestamp, message_count
                                ) VALUES (
                                    :channel_id, :batch_timestamp, :message_file_path,
                                    :first_message_id, :first_timestamp,
                                    :last_message_id, :last_timestamp, :message_count
                                )
                            """),
                            {
                                "channel_id": channel_id,
                                "batch_timestamp": timestamp,
                                "message_file_path": msg_filename,
                                "first_message_id": messages[0].id,
                                "first_timestamp": to_local_time(messages[0].date).isoformat(),
                                "last_message_id": messages[-1].id,
                                "last_timestamp": to_local_time(messages[-1].date).isoformat(),
                                "message_count": len(messages)
                            }
                        )
                        self.logger.info(f"Stored batch metadata in channel_fetch_batches for channel {channel_id}")

                        # Update channels table
                        result = conn.execute(
                            text("SELECT earliest_raw_message_ID FROM channels WHERE ID = :id"),
                            {"id": channel_id}
                        ).fetchone()
                        is_first_run = result is None or result[0] is None

                        if is_first_run:
                            conn.execute(
                                text("""
                                    UPDATE channels
                                    SET earliest_raw_message_ID = :earliest_id,
                                        earliest_raw_message_date = :earliest_date,
                                        latest_raw_message_ID = :latest_id,
                                        latest_raw_message_date = :latest_date,
                                        latest_batch_raw_run = :batch_run_time,
                                        FetchStatus = 1
                                    WHERE ID = :id
                                """),
                                {
                                    "earliest_id": messages[0].id,
                                    "earliest_date": to_local_time(messages[0].date).isoformat(),
                                    "latest_id": messages[-1].id,
                                    "latest_date": to_local_time(messages[-1].date).isoformat(),
                                    "batch_run_time": get_formatted_timestamp(),
                                    "id": channel_id
                                }
                            )
                            self.logger.info(f"First run: Set earliest ID {messages[0].id} at {to_local_time(messages[0].date)}, latest ID {messages[-1].id} at {to_local_time(messages[-1].date)}, batch run at {get_formatted_timestamp()} for channel {channel_id}")
                        else:
                            conn.execute(
                                text("""
                                    UPDATE channels
                                    SET latest_raw_message_ID = :latest_id,
                                        latest_raw_message_date = :latest_date,
                                        latest_batch_raw_run = :batch_run_time
                                    WHERE ID = :id
                                """),
                                {
                                    "latest_id": messages[-1].id,
                                    "latest_date": to_local_time(messages[-1].date).isoformat(),
                                    "batch_run_time": get_formatted_timestamp(),
                                    "id": channel_id
                                }
                            )
                            self.logger.info(f"Updated latest ID {messages[-1].id} at {to_local_time(messages[-1].date)}, batch run at {get_formatted_timestamp()} for channel {channel_id}")
            except Exception as e:
                self.logger.error(f"Error storing batch metadata in channel_fetch_batches for channel {channel_id}: {e}")
                raise