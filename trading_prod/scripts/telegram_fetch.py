#sscript/telegram_fetch.py


import argparse
import asyncio
import json
import logging
import os
import sys
import time
import re
import unicodedata
from datetime import datetime
from logging.handlers import RotatingFileHandler
from sqlalchemy.sql import text
from telethon.errors import FloodWaitError
from telethon.errors.common import TypeNotFoundError
from helper.config_manager import ConfigManager
from helper.Logger import Logging
from helper.telegram_client import TelegramClientHandler
from helper.database import DatabaseHandler
from helper.lockfile import LockFileHandler
from helper.timezone import get_formatted_timestamp

# Redirect stderr to a temporary file at script start, but only if running directly
if __name__ == "__main__":
    sys.stderr = open(os.path.join("logs", "telegram_fetch_stderr.log"), 'a')

def parse_arguments():
    """
    Parse command-line arguments for config file and max batches.

    Returns:
        tuple: (config_path, max_batches)
    """
    parser = argparse.ArgumentParser(description="Telegram History Fetcher")
    parser.add_argument("--config", default="config/combined_config.yaml", help="Path to config file")
    parser.add_argument("--max-batches", type=int, default=0, help="Stop each channel after N batches (0 for unlimited)")
    args = parser.parse_args()
    return args.config, args.max_batches

async def initialize_dependencies(config_path, project_root):
    """
    Initialize dependencies: config, logger, Telegram client, and database engine.

    Args:
        config_path (str): Path to the configuration file.
        project_root (str): Project root directory for resolving config paths.

    Returns:
        tuple: (config, logger, client, engine) containing initialized objects.
    """
    # Silence root logger to prevent console output
    root_logger = logging.getLogger()
    root_logger.handlers = []

    # Create a temporary logger for early errors
    temp_logger = logging.getLogger("telegram_fetch.TempLogger")
    temp_logger.setLevel(logging.DEBUG)
    temp_handler = logging.StreamHandler()
    temp_handler.setLevel(logging.CRITICAL)
    temp_handler.setFormatter(logging.Formatter("%(asctime)s - %(filename)s:%(funcName)s - %(levelname)s - %(message)s"))
    temp_logger.addHandler(temp_handler)

    try:
        config = ConfigManager(config_path, project_root=project_root)
    except Exception as e:
        temp_logger.critical(f"Failed to initialize ConfigManager: {str(e)}")
        raise

    logger = Logging(config, instance_id="telegram_fetch")
    logger.set_log_file(config.get_with_default("telegramHistoryRawUpdater", "fetch.log_file_name", default="telegram_fetch"))

    # Add secondary progress log
    log_dir = config.get_with_default("logging", "log_dir_name", default="logs")
    os.makedirs(log_dir, exist_ok=True)
    progress_log_file = os.path.join(log_dir, "telegram_fetch_progress.log")
    progress_handler = RotatingFileHandler(
        progress_log_file,
        maxBytes=config.get_with_default("logging", "log_file_max_bytes", default=10485760),
        backupCount=config.get_with_default("logging", "log_file_backup_count", default=10)
    )
    progress_handler.setLevel(logging.INFO)
    progress_handler.setFormatter(logging.Formatter("%(asctime)s - %(filename)s:%(funcName)s - %(message)s"))
    logger.logger.addHandler(progress_handler)

    # Update stderr to append to the main log file, but only if running directly
    if __name__ == "__main__":
        if sys.stderr != sys.__stderr__:
            sys.stderr.flush()  # Flush instead of closing to avoid ValueError in tests
        sys.stderr = open(os.path.join(log_dir, "telegram_fetch.log"), 'a')

    # Set console to CRITICAL, file to DEBUG, progress to INFO
    logger.logger.handlers[0].setLevel(logging.CRITICAL)  # StreamHandler
    logger.logger.handlers[1].setLevel(logging.DEBUG)    # Primary FileHandler
    logger.logger.handlers[2].setLevel(logging.INFO)     # Progress FileHandler

    # Redirect all Telethon logging to primary file handler at ERROR level
    for logger_name in logging.Logger.manager.loggerDict:
        if logger_name.startswith('telethon'):
            telethon_logger = logging.getLogger(logger_name)
            telethon_logger.handlers = []
            telethon_logger.addHandler(logger.logger.handlers[1])
            telethon_logger.setLevel(logging.ERROR)
            telethon_logger.propagate = False
            # Suppress console output explicitly
            telethon_logger.addHandler(logging.NullHandler())

    # Restore root logger
    root_logger.setLevel(logging.NOTSET)
    temp_logger.handlers = []  # Clean up temp logger

    try:
        telegram_handler = TelegramClientHandler(config, logger)
        client = await telegram_handler.get_client()
    except Exception as e:
        logger.critical(f"Failed to initialize Telegram client: {str(e)}")
        raise

    try:
        db_handler = DatabaseHandler(config, logger)
        engine = db_handler.get_engine()
    except Exception as e:
        logger.critical(f"Failed to initialize database engine: {str(e)}")
        raise

    return config, logger, client, engine

def reload_config(config_path, project_root, logger):
    """
    Reload configuration settings from file.

    Args:
        config_path (str): Path to the configuration file.
        project_root (str): Project root directory.
        logger: Logging instance for logging reload results.

    Returns:
        ConfigManager: New ConfigManager instance with updated settings, or None on failure.
    """
    try:
        new_config = ConfigManager(config_path, project_root=project_root)
        logger.debug("Successfully reloaded configuration")
        logger.info(f"Reloaded configuration: batch_size={new_config.get_with_default('telegramHistoryRawUpdater', 'fetch.batch_size', default=100)}")
        return new_config
    except Exception as e:
        logger.error(f"Failed to reload configuration: {sanitize_text(str(e)) or 'Unknown error'}")
        return None

def fetch_active_channels(engine, logger):
    """
    Fetch active channels from the channels table.

    Args:
        engine: SQLAlchemy engine for database queries.
        logger: Logging instance for logging query results.

    Returns:
        list: List of tuples (channel_id, earliest_raw_message_id, earliest_raw_message_date, last_processed_id).
    """
    query = """
        SELECT c.ID, c.earliest_raw_message_ID, c.earliest_raw_message_date,
               (SELECT MAX(last_message_id)
                FROM channel_fetch_batches
                WHERE channel_id = c.ID) AS last_processed_id
        FROM channels c
        WHERE c.Operating = 1 AND c.Disappeared = 0
    """
    try:
        with engine.connect() as conn:
            result = conn.execute(text(query)).fetchall()
            logger.info(f"Fetched {len(result)} active channels")
            return result
    except Exception as e:
        logger.error(f"Error fetching active channels: {sanitize_text(str(e)) or 'Unknown error'}")
        return []

async def fetch_message_batch(client, channel_id, offset_id, batch_size, logger):
    """
    Fetch a batch of messages from a Telegram channel with retry logic.

    Args:
        client: Telegram client instance.
        channel_id (int): ID of the Telegram channel.
        offset_id (int): Message ID to start fetching from.
        batch_size (int): Number of messages to fetch.
        logger: Logging instance for logging fetch results.

    Returns:
        list: List of fetched messages, or empty list if no messages or error occurs.
    """
    max_retries = 5
    max_skips = 50  # Reduced to handle smaller clusters
    current_offset = offset_id
    valid_messages = []
    messages_fetched = 0
    retries = 0
    skips = 0
    while messages_fetched < batch_size:
        try:
            # Increase fetch_size after skips to find valid messages
            fetch_size = min(batch_size - messages_fetched, 100) if skips < max_skips // 2 else min(batch_size - messages_fetched, 200)
            messages = await client.get_messages(
                channel_id,
                limit=fetch_size,
                offset_id=current_offset,
                reverse=True
            )
            if not messages:
                logger.info(f"No more messages for channel {channel_id} at offset {current_offset}")
                break
            for msg in messages:
                try:
                    _ = msg.text or ""
                    valid_messages.append(msg)
                    messages_fetched += 1
                    current_offset = msg.id
                    retries = 0
                    skips = 0
                except TypeNotFoundError:
                    logger.warning(f"Skipping unreadable message in channel {channel_id} at offset {current_offset}")
                    current_offset += 1
                    skips += 1
                    retries = 0
                    continue
            if valid_messages:
                logger.debug(f"Accumulated {len(valid_messages)} valid messages for channel {channel_id} at offset {current_offset}")
            if len(messages) < fetch_size:
                break
            # Jump offset after many skips
            if skips >= max_skips:
                logger.warning(f"Reached max skips ({max_skips}) in channel {channel_id} at offset {current_offset}, jumping forward")
                current_offset += 100
                skips = 0
        except FloodWaitError as e:
            logger.warning(f"Flood wait error for channel {channel_id}: waiting {e.seconds} seconds (retry {retries+1}/{max_retries})")
            await asyncio.sleep(e.seconds)
            retries += 1
            if retries >= max_retries:
                logger.error(f"Max retries reached for channel {channel_id} due to flood wait")
                return valid_messages
        except TypeNotFoundError:
            logger.warning(f"Unreadable message data in channel {channel_id} at offset {current_offset}, skipping to next message")
            current_offset += 1
            skips += 1
            retries = 0
            continue
        except Exception as e:
            error_msg = sanitize_text(str(e)) or "Unknown error"
            logger.error(f"Error fetching messages for channel {channel_id}: {error_msg}", exc_info=True)
            retries += 1
            if retries >= max_retries:
                return valid_messages
    logger.info(f"Fetched {len(valid_messages)} valid messages for channel {channel_id} at final offset {current_offset}")
    if valid_messages:
        logger.debug(f"First message ID: {valid_messages[0].id}, Last message ID: {valid_messages[-1].id}")
    return valid_messages

def sanitize_text(text):
    """
    Sanitize text to remove non-printable, binary, or malformed characters, preserving Unicode emojis.

    Args:
        text: Input string or object to sanitize.

    Returns:
        str: Sanitized string with only printable Unicode characters, or None if input is invalid.
    """
    if text is None:
        return None
    try:
        text_str = str(text)
        normalized = unicodedata.normalize('NFKC', text_str)
        sanitized = re.sub(r'[^\x20-\x7E\x0A\x0D\xA0-\uFFFF]', '', normalized)
        sanitized = sanitized.encode('ascii', errors='ignore').decode('ascii')
        return sanitized or None
    except Exception:
        return None

def store_messages_to_file(messages, channel_id, batch_count, total_messages_fetched, config, logger):
    """
    Store messages as a JSON file in a channel-specific directory.

    Args:
        messages: List of messages to store.
        channel_id (int): ID of the Telegram channel.
        batch_count (int): Batch number for naming the file.
        total_messages_fetched (int): Total messages fetched for stats.
        config: ConfigManager instance for storage settings.
        logger: Logging instance for logging storage results.

    Returns:
        str: Path to the stored JSON file, or None if storage fails.
    """
    try:
        base_dir = config.get_with_default("telegramHistoryRawUpdater", "fetch.base_dir", default="temp_messages")
        channel_dir = os.path.join(base_dir, str(channel_id))
        os.makedirs(channel_dir, exist_ok=True)
        timestamp = get_formatted_timestamp()
        msg_filename = os.path.join(channel_dir, f"batch_{timestamp}.json")

        output_data = [
            {
                "channel_id": channel_id,
                "message_id": msg.id,
                "timestamp": msg.date.strftime("%Y-%m-%d %H:%M:%S"),
                "text": sanitize_text(msg.text),
                "sender_id": msg.sender_id if msg.sender_id else None,
                "is_service_message": hasattr(msg, "action")
            }
            for msg in messages
        ]
        output_data.append({
            "channel_id": channel_id,
            "message_id": None,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "text": None,
            "sender_id": None,
            "is_service_message": False,
            "status": {
                "batch_number": batch_count,
                "total_messages_fetched": total_messages_fetched,
                "message_count_in_batch": len(messages),
                "timestamp": timestamp
            }
        })

        with open(msg_filename, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=4)
        logger.info(f"Stored {len(messages)} messages for channel {channel_id}, batch {batch_count}, total {total_messages_fetched} in {msg_filename}")
        return msg_filename
    except Exception as e:
        logger.error(f"Failed to store messages for channel {channel_id}: {sanitize_text(str(e)) or 'Unknown error'}")
        return None

def record_batch_metadata(engine, channel_id, msg_filename, messages, batch_count, logger):
    """
    Record batch metadata in the channel_fetch_batches table.

    Args:
        engine: SQLAlchemy engine for database queries.
        channel_id (int): ID of the Telegram channel.
        msg_filename (str): Path to the stored JSON file.
        messages: List of messages in the batch.
        batch_count (int): Batch number for tracking.
        logger: Logging instance for logging database results.

    Returns:
        bool: True if metadata is recorded successfully, False otherwise.
    """
    if not messages or not msg_filename:
        logger.warning(f"No messages or filename to record for channel {channel_id}")
        return False
    try:
        with engine.connect() as conn:
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
                    "batch_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "message_file_path": msg_filename,
                    "first_message_id": messages[0].id,
                    "first_timestamp": messages[0].date.strftime("%Y-%m-%d %H:%M:%S"),
                    "last_message_id": messages[-1].id,
                    "last_timestamp": messages[-1].date.strftime("%Y-%m-%d %H:%M:%S"),
                    "message_count": len(messages)
                }
            )
            conn.commit()
        logger.info(f"Recorded batch {batch_count} metadata for channel {channel_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to record batch metadata for channel {channel_id}: {sanitize_text(str(e)) or 'Unknown error'}")
        return False

def update_channel_status(engine, channel_id, messages, fetch_attempts, logger):
    """
    Update channel status in the channels table based on fetch results.

    Args:
        engine: SQLAlchemy engine for database queries.
        channel_id (int): ID of the Telegram channel.
        messages: List of fetched messages (may be empty).
        fetch_attempts (int): Number of consecutive empty fetches.
        logger: Logging instance for logging update results.

    Returns:
        bool: True if status is updated successfully, False otherwise.
    """
    try:
        with engine.connect() as conn:
            if messages:
                conn.execute(
                    text("""
                        UPDATE channels
                        SET earliest_raw_message_ID = :earliest_id,
                            earliest_raw_message_date = :earliest_date,
                            latest_raw_message_ID = :latest_id,
                            latest_raw_message_date = :latest_date,
                            FetchStatus = 1,
                            fetch_attempts = 0
                        WHERE ID = :id
                    """),
                    {
                        "earliest_id": messages[-1].id,
                        "earliest_date": messages[-1].date.strftime("%Y-%m-%d %H:%M:%S"),
                        "latest_id": messages[0].id,
                        "latest_date": messages[0].date.strftime("%Y-%m-%d %H:%M:%S"),
                        "id": channel_id
                    }
                )
                logger.info(f"Updated channel {channel_id} with new messages, reset fetch_attempts")
            else:
                fetch_attempts += 1
                max_attempts = 5
                if fetch_attempts >= max_attempts:
                    conn.execute(
                        text("""
                            UPDATE channels
                            SET FetchStatus = 2,
                                fetch_attempts = :fetch_attempts
                            WHERE ID = :id
                        """),
                        {"fetch_attempts": fetch_attempts, "id": channel_id}
                    )
                    logger.info(f"Channel {channel_id} marked complete after {fetch_attempts} empty fetches")
                else:
                    conn.execute(
                        text("""
                            UPDATE channels
                            SET FetchStatus = 1,
                                fetch_attempts = :fetch_attempts
                            WHERE ID = :id
                        """),
                        {"fetch_attempts": fetch_attempts, "id": channel_id}
                    )
                    logger.info(f"Channel {channel_id} updated with {fetch_attempts} empty fetches")
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to update channel {channel_id} status: {sanitize_text(str(e)) or 'Unknown error'}")
        return False

async def main():
    """
    Main service loop to fetch and store messages from Telegram channels in a round-robin fashion.
    """
    try:
        config_path, max_batches = parse_arguments()
        project_root = "/home/egirg/shared/trading_prod"
        config, logger, client, engine = await initialize_dependencies(config_path, project_root)
    except Exception as e:
        print(f"Initialization failed: {str(e)}")
        print("Check logs/telegram_fetch.log for details.")
        logging.getLogger("telegram_fetch.TempLogger").critical(f"Initialization failed: {str(e)}")
        sys.exit(1)

    lockfile_name = config.get_with_default("telegramHistoryRawUpdater", "fetch.lockfile.name", default="telegram_fetch.lock")
    lock_handler = LockFileHandler(config, lockfile_name, logger)

    try:
        lock_handler.acquire()
        logger.info(f"Telegram fetcher started with max_batches={max_batches}")
        print("Telegram fetcher started. Remove locks/telegram_fetch.lock to stop gracefully.")

        # Initial config load
        batch_size = config.get_with_default("telegramHistoryRawUpdater", "fetch.batch_size", default=100)
        sleep_seconds = config.get_with_default("telegramHistoryRawUpdater", "fetch.sleep_seconds", default=5)
        pause_seconds = config.get_with_default("telegramHistoryRawUpdater", "fetch.pause_seconds", default=1)
        config_reload_interval = 600  # Reload every 10 minutes (600 seconds)
        last_config_reload = time.time()
        logger.debug(f"Initial settings: batch_size={batch_size}, sleep_seconds={sleep_seconds}, pause_seconds={pause_seconds}, max_batches={max_batches}")

        # Track channel states
        channel_states = {}  # {channel_id: (offset_id, fetch_attempts, batch_count, total_messages_fetched)}

        while True:
            # Check lock file more responsively
            if not os.path.exists(lock_handler.lock_file_path):
                logger.info("Lock file removed, stopping service")
                break

            # Reload config every 10 minutes
            if time.time() - last_config_reload >= config_reload_interval:
                new_config = reload_config(config_path, project_root, logger)
                if new_config:
                    config = new_config
                    batch_size = config.get_with_default("telegramHistoryRawUpdater", "fetch.batch_size", default=100)
                    sleep_seconds = config.get_with_default("telegramHistoryRawUpdater", "fetch.sleep_seconds", default=5)
                    pause_seconds = config.get_with_default("telegramHistoryRawUpdater", "fetch.pause_seconds", default=1)
                    logger.debug(f"Reloaded settings: batch_size={batch_size}, sleep_seconds={sleep_seconds}, pause_seconds={pause_seconds}")
                last_config_reload = time.time()

            channels = fetch_active_channels(engine, logger)
            if not channels:
                logger.info(f"No active channels found, sleeping for {sleep_seconds} seconds")
                await asyncio.sleep(sleep_seconds)
                continue

            any_messages_fetched = False
            active_channels = []
            for channel in channels:
                channel_id = channel[0]
                last_processed_id = channel[3]
                if channel_id not in channel_states:
                    channel_states[channel_id] = (last_processed_id if last_processed_id else 0, 0, 0, 0)
                offset_id, fetch_attempts, batch_count, total_messages_fetched = channel_states[channel_id]

                # Skip channels that reached max_batches
                if max_batches > 0 and batch_count >= max_batches:
                    logger.info(f"Channel {channel_id} reached max_batches limit ({max_batches}), skipping")
                    continue

                active_channels.append(channel)
                logger.debug(f"Processing channel {channel_id} with offset {offset_id}, fetch_attempts {fetch_attempts}")
                messages = await fetch_message_batch(client, channel_id, offset_id, batch_size, logger)
                if messages:
                    batch_count += 1
                    total_messages_fetched += len(messages)
                    any_messages_fetched = True
                    msg_filename = store_messages_to_file(messages, channel_id, batch_count, total_messages_fetched, config, logger)
                    if msg_filename:
                        record_batch_metadata(engine, channel_id, msg_filename, messages, batch_count, logger)
                    update_channel_status(engine, channel_id, messages, fetch_attempts, logger)
                    offset_id = messages[-1].id
                    fetch_attempts = 0
                else:
                    update_channel_status(engine, channel_id, messages, fetch_attempts, logger)
                    fetch_attempts += 1

                channel_states[channel_id] = (offset_id, fetch_attempts, batch_count, total_messages_fetched)
                await asyncio.sleep(pause_seconds)

                # Check lock file after each channel
                if not os.path.exists(lock_handler.lock_file_path):
                    logger.info("Lock file removed during channel processing, stopping service")
                    return

            if not any_messages_fetched:
                logger.info(f"No new messages fetched for any channel, sleeping for {sleep_seconds} seconds")
                await asyncio.sleep(sleep_seconds)
            if not active_channels:
                logger.info("All channels reached max_batches limit or are complete, stopping service")
                break

    except Exception as e:
        logger.error(f"Unexpected error in service loop: {sanitize_text(str(e)) or 'Unknown error'}", exc_info=True)
        print(f"Error: Check logs/telegram_fetch.log for details.")
    finally:
        lock_handler.release()
        await client.disconnect()
        logger.info("Telegram fetcher stopped")
        print("Telegram fetcher stopped gracefully.")
        if __name__ == "__main__" and sys.stderr != sys.__stderr__:
            sys.stderr.close()
            sys.stderr = sys.__stderr__
        sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())