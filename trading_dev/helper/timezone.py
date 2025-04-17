# helper/timezone.py
from datetime import datetime
import pytz
try:
    from helper.config_manager import ConfigManager
except ImportError:
    ConfigManager = None

def get_local_now(config: ConfigManager = None):
    """
    Get the current time in the configured or default local timezone.

    Args:
        config (ConfigManager, optional): ConfigManager instance for timezone settings.

    Returns:
        datetime: Current time in the local timezone.
    """
    tz_name = config.get_with_default("timezone", "name", default="America/Chicago") if config else "America/Chicago"
    local_tz = pytz.timezone(tz_name)
    return datetime.now(local_tz)

def to_local_time(dt: datetime, config: ConfigManager = None):
    """
    Convert a datetime to the local timezone. Naive datetimes are assumed to be UTC.

    Args:
        dt (datetime): Datetime object to convert.
        config (ConfigManager, optional): ConfigManager instance for timezone settings.

    Returns:
        datetime: Datetime in the local timezone.

    Raises:
        TypeError: If dt is not a datetime object.
    """
    if not isinstance(dt, datetime):
        raise TypeError("dt must be a datetime object")
    tz_name = config.get_with_default("timezone", "name", default="America/Chicago") if config else "America/Chicago"
    local_tz = pytz.timezone(tz_name)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=pytz.UTC)
    return dt.astimezone(local_tz)

def get_formatted_timestamp(dt: datetime = None, config: ConfigManager = None):
    """
    Generate a formatted timestamp string from a datetime object (or current time if None).
    Format: YYYY-MM-DDThh-mm-ss (replaces ':' with '-').

    Args:
        dt (datetime, optional): Datetime object to format. If None, uses current time.
        config (ConfigManager, optional): ConfigManager instance for timezone settings.

    Returns:
        str: Formatted timestamp string (e.g., '2025-04-01T12-00-00').

    Raises:
        TypeError: If dt is not a datetime object.
    """
    if dt is not None and not isinstance(dt, datetime):
        raise TypeError("dt must be a datetime object")
    if dt is None:
        dt = get_local_now(config)
    return dt.isoformat().replace(":", "-")