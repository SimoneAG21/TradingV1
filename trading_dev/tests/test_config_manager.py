"""
Test suite for ConfigManager in TradingV1, verifying YAML configuration handling.

This file tests all features of helper/config_manager.py using tests/combined_config_test.yaml
and tests/processes.yaml. Ensures correct parsing and access for settings, processes, and menu
used in app.py, telegram_fetch.py, and Heroku (seanstrader).

How to Run Tests:
- All Tests: Run entire suite from project root.
  ```
  pytest tests/test_config_manager.py -v
  ```
- Single Test: Run a specific test (e.g., test_settings_parsing).
  ```
  pytest tests/test_config_manager.py::test_settings_parsing -v
  ```
- Discovery Mode: Find all tests in tests/ directory.
  ```
  pytest tests/ --collect-only
  ```
- Coverage Testing: Measure test coverage (requires pytest-cov).
  ```
  pytest tests/test_config_manager.py --cov=helper --cov-report=html
  ```
  Output: htmlcov/index.html

Environment:
- Activate virtualenv: .\venv\Scripts\activate
- Requires: pytest, pyyaml (in requirements.txt)
"""

import pytest
import os
from helper.config_manager import ConfigManager

@pytest.fixture
def config():
    """
    Fixture providing a ConfigManager instance for tests.

    Loads tests/combined_config_test.yaml, initializing settings and processes.
    Used by all tests to ensure consistent configuration.

    Example:
        def test_example(config):
            assert config.get('logging', 'log_dir_name') == 'logs'
    """
    # Set project_root to the parent directory of tests/
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    return ConfigManager('tests/combined_config_test.yaml', project_root=project_root)

def test_singleton_pattern(config):
    """
    Tests basic ConfigManager initialization and state preservation.

    Verifies ConfigManager loads settings correctly and maintains state, simulating
    singleton-like behavior (though new instances can be created for different files).
    Ensures usability in threaded jobs (telegram_fetch.py).

    Checks:
        - get('logging', 'log_dir_name') returns 'logs'.
        - Setting an attribute (test_attr) persists.
    """
    assert config.get("logging", "log_dir_name") == "logs", "Singleton not initialized"
    config.test_attr = "test"
    assert config.test_attr == "test", "State not preserved"

def test_get_with_default_isolated():
    """
    Tests get_with_default for missing keys in isolation.

    Verifies ConfigManager returns default value for non-existent keys, critical for
    robust config access in app.py. Creates a new instance to ensure no fixture state.

    Checks:
        - get_with_default('logging', 'missing', default='default') returns 'default'.
    """
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    config = ConfigManager('tests/combined_config_test.yaml', project_root=project_root)
    result = config.get_with_default("logging", "missing", default="default")
    print(f"Isolated get_with_default: {result}")
    assert result == "default", "Isolated default fallback failed"

def test_settings_parsing(config):
    """
    Tests settings retrieval from YAML sections.

    Verifies ConfigManager parses logging settings and handles missing keys gracefully,
    essential for logging setup in Heroku (seanstrader).

    Checks:
        - get('logging', 'log_dir_name') returns 'logs'.
        - get_with_default('logging', 'missing', 'default') returns 'default'.
    """
    print(f"Initial settings: {config.get_section('logging')}")
    assert config.get("logging", "log_dir_name") == "logs", "Failed to get log_dir_name"
    assert config.get_with_default("logging", "missing", "default") == "default", "Failed default fallback"

def test_type_conversion(config):
    """
    Tests type conversion of YAML settings to native Python types.

    Verifies ConfigManager converts settings based on 'type' field (e.g., integer, boolean),
    crucial for correct data handling in job logic.

    Checks:
        - get('constants', 'max_retries') is int and equals 2.
        - get('constants', 'is_test_mode') is bool and True.
    """
    assert isinstance(config.get("constants", "max_retries"), int), "max_retries not int"
    assert config.get("constants", "max_retries") == 2, "max_retries value incorrect"
    assert isinstance(config.get("constants", "is_test_mode"), bool), "is_test_mode not bool"
    assert config.get("constants", "is_test_mode") is True, "is_test_mode value incorrect"

def test_hierarchical_attributes(config):
    """
    Tests process attribute parsing using get_processes().

    Verifies ConfigManager correctly parses process attributes (e.g., interval, enabled)
    for the 'fetch' process, used in telegram_fetch.py for task scheduling.

    Checks:
        - fetch process has interval=60, enabled=True.
    """
    fetch = next(p for p in config.get_processes() if p.get("id") == "fetch")
    assert fetch["interval"]["value"] == 60, "fetch interval incorrect"
    assert fetch["enabled"]["value"] is True, "fetch enabled incorrect"

def test_hierarchical_attributes_generic(config):
    """
    Tests process attribute parsing using generic get_section().

    Verifies ConfigManager’s get_section('processes') returns the same process attributes
    as get_processes(), ensuring flexibility for future sections (e.g., meals).

    Checks:
        - fetch process has interval=60, enabled=True.
    """
    processes = config.get_section("processes")
    fetch = next(p for p in processes if p.get("id") == "fetch")
    assert fetch["interval"]["value"] == 60, "fetch interval incorrect"
    assert fetch["enabled"]["value"] is True, "fetch enabled incorrect"

def test_template_config(config):
    """
    Tests template-based process configuration.

    Verifies ConfigManager merges default_process template settings (interval, enabled)
    with process-specific overrides (priority), used for reusable process configs.

    Checks:
        - Process with priority has interval=60, enabled=True, priority='high'.
    """
    proc = next(p for p in config.get_section("processes") if p.get("priority"))
    assert proc["interval"]["value"] == 60, "Template interval not applied"
    assert proc["enabled"]["value"] is True, "Template enabled not applied"
    assert proc["priority"]["value"] == "high", "Template override incorrect"

def test_conditional_config(config):
    """
    Tests conditional process configuration based on environment.

    Verifies ConfigManager applies test environment settings (is_test_mode=true)
    for processes with conditions, critical for test vs. prod behavior.

    Checks:
        - Process with mode has interval=30, mode='debug'.
    """
    proc = next(p for p in config.get_section("processes") if p.get("mode"))
    assert proc["interval"]["value"] == 30, "Test condition interval incorrect"
    assert proc["mode"]["value"] == "debug", "Test condition mode incorrect"

def test_embedded_sql(config):
    """
    Tests embedded SQL query storage in processes.

    Verifies ConfigManager correctly parses SQL queries within processes,
    used for database interactions (e.g., telegram_messages.sql).

    Checks:
        - Process has sql.fetch_messages starting with 'SELECT *'.
    """
    proc = next(p for p in config.get_section("processes") if p.get("sql"))
    assert "sql" in proc, "SQL not parsed"
    assert proc["sql"]["fetch_messages"].startswith("SELECT *"), "SQL query incorrect"

def test_external_include(config):
    """
    Tests inclusion of external process files.

    Verifies ConfigManager merges processes from processes.yaml (e.g., sync process),
    ensuring modularity for additional configs.

    Checks:
        - sync process has interval=300, timeout=600.
    """
    sync = next(p for p in config.get_section("processes") if p.get("id") == "sync")
    assert sync["interval"]["value"] == 300, "Sync interval incorrect"
    assert sync["timeout"]["value"] == 600, "Sync timeout incorrect"

def test_menu_structure(config):
    """
    Tests menu structure parsing for UI navigation.

    Verifies ConfigManager correctly parses hierarchical menu settings,
    ensuring Trading.Start.amount is accessible for Flask UI (app.py).

    Checks:
        - menu.Main exists, Trading.Start.amount.default=50.0.
    """
    menu = config.get_section("menu")
    assert "Main" in menu, "Main menu missing"
    assert menu["Main"]["Trading"]["Start"]["params"]["amount"]["default"] == 50.0, "Trading Start amount incorrect"

def test_nested_key_access(config):
    """
    Tests nested key access using dot notation.

    Verifies ConfigManager correctly retrieves nested configuration values
    (e.g., database.mysql.user), essential for scripts like channelTracker.py.

    Checks:
        - get('database', 'mysql.user') returns 'test_user'.
        - get('database', 'mysql.port') returns 3306.
        - get('database', 'mysql.missing') returns {}.
        - get_with_default('database', 'mysql.missing', 'default') returns 'default'.
    """
    assert config.get("database", "mysql.user") == "test_user", "Failed to get nested mysql.user"
    assert config.get("database", "mysql.port") == 3306, "Failed to get nested mysql.port"
    assert config.get("database", "mysql.missing") == {}, "Failed to return {} for missing nested key"
    assert config.get_with_default("database", "mysql.missing", "default") == "default", "Failed default fallback for nested key"

def test_determine_project_root_cli():
    """
    Tests determine_project_root with a CLI-provided project root.

    Verifies that the method returns the normalized CLI project root path when provided.

    Checks:
        - Returns normalized path from cli_project_root.
    """
    cli_root = "/home/egirg/shared/trading_dev"
    result = ConfigManager.determine_project_root(
        env_var_name="CHTRKR_ROOT",
        cli_project_root=cli_root,
        fallback_path="/tmp/fallback"
    )
    expected = os.path.abspath(cli_root)
    assert result == expected, f"Expected CLI root {expected}, got {result}"

def test_determine_project_root_env_var():
    """
    Tests determine_project_root with an environment variable.

    Verifies that the method returns the normalized environment variable path when set.

    Checks:
        - Returns normalized path from CHTRKR_ROOT environment variable.
    """
    os.environ["CHTRKR_ROOT"] = "/home/egirg/shared/trading_dev"
    try:
        result = ConfigManager.determine_project_root(
            env_var_name="CHTRKR_ROOT",
            cli_project_root=None,
            fallback_path="/tmp/fallback"
        )
        expected = os.path.abspath("/home/egirg/shared/trading_dev")
        assert result == expected, f"Expected env var root {expected}, got {result}"
    finally:
        del os.environ["CHTRKR_ROOT"]

def test_determine_project_root_fallback():
    """
    Tests determine_project_root with a fallback path.

    Verifies that the method returns the normalized fallback path when no CLI or env var is provided.

    Checks:
        - Returns normalized path from fallback_path.
    """
    fallback = "/home/egirg/shared/trading_dev"
    result = ConfigManager.determine_project_root(
        env_var_name="CHTRKR_ROOT",
        cli_project_root=None,
        fallback_path=fallback
    )
    expected = os.path.abspath(fallback)
    assert result == expected, f"Expected fallback root {expected}, got {result}"

def test_determine_project_root_error():
    """
    Tests determine_project_root with no valid inputs.

    Verifies that the method raises a ValueError when no CLI, env var, or fallback is provided.

    Checks:
        - Raises ValueError with appropriate message.
    """
    with pytest.raises(ValueError) as exc_info:
        ConfigManager.determine_project_root(
            env_var_name="CHTRKR_ROOT",
            cli_project_root=None,
            fallback_path=None
        )
    assert str(exc_info.value) == "No valid project_root provided (must specify CLI parameter, environment variable, or fallback path)", "Unexpected error message"