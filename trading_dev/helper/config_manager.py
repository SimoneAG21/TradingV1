import os
import urllib.parse
import yaml
import traceback

class ConfigManager:
    @staticmethod
    def determine_project_root(env_var_name=None, cli_project_root=None, fallback_path=None):
        """
        Determine the project root directory based on provided inputs.

        Args:
            env_var_name (str, optional): Name of the environment variable to check (e.g., 'CHTRKR_ROOT').
            cli_project_root (str, optional): Project root path from command-line parameters.
            fallback_path (str, optional): Fallback path to use if other methods fail.

        Returns:
            str: Absolute path to the project root.

        Raises:
            ValueError: If no valid project_root can be determined.
        """
        if cli_project_root:
            project_root = os.path.abspath(cli_project_root)
            print(f"Using project_root from CLI: {project_root}")
            return project_root
        if env_var_name and env_var_name in os.environ:
            project_root = os.path.abspath(os.environ[env_var_name])
            print(f"Using project_root from environment variable {env_var_name}: {project_root}")
            return project_root
        if fallback_path:
            project_root = os.path.abspath(fallback_path)
            print(f"Using project_root from fallback path: {project_root}")
            return project_root
        raise ValueError("No valid project_root provided (must specify CLI parameter, environment variable, or fallback path)")

    def __init__(self, config_file="config.yaml", project_root=None):
        if project_root is None:
            raise ValueError("project_root must be provided")
        self.project_root = os.path.abspath(project_root)
        print(f"Using project_root: {self.project_root}")
        self._data = {}
        try:
            # Resolve config_file relative to project root if not absolute
            if not os.path.isabs(config_file):
                config_file = os.path.join(self.project_root, config_file)
            print(f"Loading config file: {config_file}")
            with open(config_file, 'r') as f:
                primary_data = yaml.safe_load(f) or {}
            self._data = primary_data.copy()
            # Process includes
            includes = self._data.get("includes", [])
            for include_file in includes:
                # Resolve include path relative to project root
                include_path = os.path.join(self.project_root, include_file)
                print(f"Loading include file: {include_path}")
                with open(include_path, 'r') as f:
                    include_data = yaml.safe_load(f) or {}
                    # Merge processes
                    if "processes" in include_data:
                        self._data.setdefault("processes", []).extend(include_data["processes"])
                    # Merge include_data, preserving primary_data keys
                    for key, value in include_data.items():
                        if key not in self._data or key == "processes":
                            self._data[key] = value
                        elif isinstance(value, dict) and isinstance(self._data[key], dict):
                            # Deep merge for nested dictionaries
                            self._data[key].update(value)
            # Ensure primary top-level keys are preserved
            for key, value in primary_data.items():
                if key != "includes" and key not in self._data:
                    self._data[key] = value
                elif key != "includes" and not isinstance(self._data[key], dict):
                    self._data[key] = value
            # Merge templates and conditions
            self._process_templates_and_conditions()
        except Exception as e:
            self._data = {}
            print(f"Error loading config file {config_file}: {e}")
            traceback.print_exc()

    def _process_templates_and_conditions(self):
        """Merge templates and apply conditional settings based on is_test_mode."""
        try:
            processes = self._data.get("processes", [])
            templates = self._data.get("templates", {})
            print(f"Processes: {processes}")
            print(f"Templates: {templates}")
            is_test_mode = self.get_with_default("constants", "is_test_mode", default=False)
            print(f"is_test_mode: {is_test_mode} (type: {type(is_test_mode)})")
            new_processes = []

            for proc in processes:
                new_proc = proc.copy()
                print(f"Processing process: {new_proc}")
                # Apply template
                if "template" in new_proc:
                    template_name = new_proc.pop("template")
                    template = templates.get(template_name, {})
                    print(f"Applying template {template_name}: {template}")
                    for key, value in template.items():
                        if key not in new_proc:
                            new_proc[key] = value
                # Apply conditions
                if "conditions" in new_proc:
                    conditions = new_proc.pop("conditions")
                    env = "test" if is_test_mode else "prod"
                    print(f"Applying conditions for env: {env}")
                    condition = conditions.get(env, {})
                    print(f"Condition: {condition}")
                    for key, value in condition.items():
                        new_proc[key] = value
                new_processes.append(new_proc)

            self._data["processes"] = new_processes
            print(f"New processes: {new_processes}")
        except Exception as e:
            print(f"Error in _process_templates_and_conditions: {e}")
            traceback.print_exc()

    def get(self, section: str, key: str):
        """
        Retrieve a configuration value for the given section and key, supporting nested keys.

        Args:
            section (str): The configuration section (e.g., 'database'). Use '' for top-level keys.
            key (str): The key, which may include dots for nesting (e.g., 'mysql.user').

        Returns:
            The value if found, else an empty dict.
        """
        print(f"Getting section: {section}, key: {key}")
        if section == "database" and "DATABASE_URL" in os.environ:
            return self._parse_database_url().get(key, {})
        if section == '':
            # Handle top-level keys
            section_data = self._data
        else:
            section_data = self._data.get(section, {})
        # Handle nested keys (e.g., 'mysql.user')
        keys = key.split('.')
        value = section_data
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k, {})
            else:
                print(f"Returning empty dict for {section}.{key}")
                return {}
        # Handle typed values (e.g., {'value': 'logs', 'type': 'string'})
        if isinstance(value, dict) and "value" in value:
            result = value["value"]
            type_str = value.get("type")
            if type_str == "integer":
                return int(result)
            elif type_str == "boolean":
                return bool(result)
            elif type_str == "float":
                return float(result)
            return result
        print(f"Returning value: {value} for {section}.{key}")
        return value

    def get_with_default(self, section: str, key: str, default=None):
        """
        Retrieve a configuration value with a default, supporting nested keys.

        Args:
            section (str): The configuration section (e.g., 'database'). Use '' for top-level keys.
            key (str): The key, which may include dots for nesting (e.g., 'mysql.user').
            default: The default value if the key is not found.

        Returns:
            The value if found, else the default.
        """
        print(f"Getting section: {section}, key: {key} with default: {default}")
        if section == "database" and "DATABASE_URL" in os.environ:
            return self._parse_database_url().get(key, default)
        if section == '':
            # Handle top-level keys
            section_data = self._data
        else:
            section_data = self._data.get(section, {})
        # Handle nested keys (e.g., 'mysql.user')
        keys = key.split('.')
        value = section_data
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k, {})
            else:
                print(f"Returning default: {default} for {section}.{key}")
                return default
        # Handle typed values (e.g., {'value': 'logs', 'type': 'string'})
        if isinstance(value, dict) and "value" in value:
            result = value["value"]
            type_str = value.get("type")
            if type_str == "integer":
                return int(result)
            elif type_str == "boolean":
                return bool(result)
            elif type_str == "float":
                return float(result)
            return result
        print(f"Returning value: {value if value != {} else default} for {section}.{key}")
        return value if value != {} else default

    def _parse_database_url(self):
        if "DATABASE_URL" not in os.environ:
            return {}
        url = urllib.parse.urlparse(os.environ["DATABASE_URL"])
        return {
            "user": url.username,
            "password": url.password,
            "host": url.hostname,
            "port": str(url.port) if url.port else "5432",
            "database": url.path.lstrip("/"),
        }

    def get_section(self, section: str):
        print(f"Getting section: {section}")
        return self._data.get(section, {})

    def get_processes(self):
        print("Getting processes")
        return self._data.get("processes", [])