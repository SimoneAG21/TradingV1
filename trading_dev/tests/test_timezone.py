import pytest
from datetime import datetime
import pytz
from unittest.mock import MagicMock
from helper.timezone import get_local_now, to_local_time, get_formatted_timestamp

@pytest.fixture
def mock_config():
    config = MagicMock()
    config.get_with_default.side_effect = lambda section, key, default: {
        ("timezone", "name"): "America/Chicago",
    }.get((section, key), default)
    return config

def test_get_local_now(mock_config):
    now = get_local_now(mock_config)
    assert isinstance(now, datetime)
    assert now.tzinfo is not None
    assert str(now.tzinfo) == "America/Chicago"

def test_get_local_now_default():
    now = get_local_now()
    assert isinstance(now, datetime)
    assert now.tzinfo is not None
    assert str(now.tzinfo) == "America/Chicago"

def test_to_local_time_aware(mock_config):
    utc_dt = datetime(2025, 4, 1, 12, 0, tzinfo=pytz.UTC)
    local_dt = to_local_time(utc_dt, mock_config)
    assert local_dt.tzinfo is not None
    assert str(local_dt.tzinfo) == "America/Chicago"
    assert local_dt.hour == 7  # UTC 12:00 is Chicago 07:00 (CDT)

def test_to_local_time_naive(mock_config):
    naive_dt = datetime(2025, 4, 1, 12, 0)
    local_dt = to_local_time(naive_dt, mock_config)
    assert local_dt.tzinfo is not None
    assert str(local_dt.tzinfo) == "America/Chicago"
    assert local_dt.hour == 7  # Assumes UTC, converts to Chicago

def test_to_local_time_invalid_type(mock_config):
    with pytest.raises(TypeError):
        to_local_time("not a datetime", mock_config)

def test_get_formatted_timestamp(mock_config):
    dt = datetime(2025, 4, 1, 12, 0, tzinfo=pytz.timezone("America/Chicago"))
    timestamp = get_formatted_timestamp(dt, mock_config)
    assert timestamp.startswith("2025-04-01T12-00-00")

def test_get_formatted_timestamp_none(mock_config):
    timestamp = get_formatted_timestamp(None, mock_config)
    assert len(timestamp) >= 19  # At least YYYY-MM-DDThh-mm-ss
    assert "T" in timestamp
    assert timestamp.count("-") >= 5  # Date and time separators

def test_get_formatted_timestamp_invalid_type(mock_config):
    with pytest.raises(TypeError):
        get_formatted_timestamp("not a datetime", mock_config)