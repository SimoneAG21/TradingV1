"""
Overview:
This module provides utility functions for Telegram operations in the #SeanProjectTrading project.

Purpose:
- Provides reusable functions for fetching Telegram messages.
- Reusable across scripts that interact with the Telegram API.

Dependencies:
- telethon: For Telegram client functionality.
- helper.Logger.Logging: For logging fetch events.
"""
from typing import List, Optional, Any
from telethon.errors import FloodWaitError
import asyncio

try:
    from helper.Logger import Logging
except ImportError as e:
    raise ImportError(f"Failed to import dependencies: {e}")

async def fetch_message_batch(
    client: Any,
    channel_id: str,
    offset_id: int,
    batch_size: int,
    logger: Optional[Logging] = None,
    offset_date: Optional[Any] = None
) -> List[Any]:
    """
    Fetch a batch of messages from a Telegram channel.

    Args:
        client (Any): The Telegram client (Telethon client instance).
        channel_id (str): The ID of the Telegram channel.
        offset_id (int): The message ID to start fetching from.
        batch_size (int): The number of messages to fetch in this batch.
        logger (Optional[Logging]): Logger instance for logging fetch events.
        offset_date (Optional[Any]): Filter messages newer than this date (default: None).

    Returns:
        List[Any]: A list of fetched messages, or an empty list if an error occurs.
    """
    try:
        messages = await client.get_messages(
            channel_id,
            limit=batch_size,
            offset_id=offset_id,
            offset_date=offset_date,  # Filter messages newer than this date
            reverse=True
        )
        if logger is not None:
            logger.info(f"Fetched {len(messages)} messages for channel {channel_id}")
        return messages
    except FloodWaitError as e:
        if logger is not None:
            logger.warning(f"Flood wait error for channel {channel_id}: waiting {e.seconds} seconds...")
        await asyncio.sleep(e.seconds)
        return []
    except Exception as e:
        if logger is not None:
            logger.error(f"Error fetching messages for channel {channel_id}: {e}")
        return []