import os
import urllib.parse
import yaml

class ConfigManager:
    def __init__(self, config_file="config.yaml"):
        self._data = {}
        try:
            with open(config_file, 'r') as f:
                self._data = yaml.safe_load(f) or {}
            # Process includes
            includes = self._data.get("includes", [])
            for include_file in includes:
                with open(include_file, 'r') as f:
                    include_data = yaml.safe_load(f) or {}
                    if "processes" in include_data:
                        self._data.setdefault("processes", []).extend(include_data["processes"])
            # Merge templates and conditions
            self._process_templates_and_conditions()
        except Exception as e:
            self._data = {}

    def _process_templates_and_conditions(self):
        """Merge templates and apply conditional settings based on is_test_mode."""
        processes = self._data.get("processes", [])
        templates = self._data.get("templates", {})
        is_test_mode = self.get("constants", "is_test_mode") or False
        new_processes = []
        
        for proc in processes:
            new_proc = proc.copy()
            # Apply template
            if "template" in new_proc:
                template_name = new_proc.pop("template")
                template = templates.get(template_name, {})
                for key, value in template.items():
                    if key not in new_proc:
                        new_proc[key] = value
            # Apply conditions
            if "conditions" in new_proc:
                conditions = new_proc.pop("conditions")
                env = "test" if is_test_mode else "prod"
                condition = conditions.get(env, {})
                for key, value in condition.items():
                    new_proc[key] = value
            new_processes.append(new_proc)
        
        self._data["processes"] = new_processes

    def get(self, section: str, key: str):
        if section == "database" and "DATABASE_URL" in os.environ:
            return self._parse_database_url()[key]
        value_dict = self._data.get(section, {}).get(key, {})
        if isinstance(value_dict, dict) and "value" in value_dict:
            value = value_dict["value"]
            type_str = value_dict.get("type")
            if type_str == "integer":
                return int(value)
            elif type_str == "boolean":
                return bool(value)
            elif type_str == "float":
                return float(value)
            return value
        return value_dict

    def get_with_default(self, section: str, key: str, default=None):
        if section == "database" and "DATABASE_URL" in os.environ:
            return self._parse_database_url().get(key, default)
        value_dict = self._data.get(section, {}).get(key)
        if value_dict is None:
            return default
        if isinstance(value_dict, dict) and "value" in value_dict:
            value = value_dict["value"]
            type_str = value_dict.get("type")
            if type_str == "integer":
                return int(value)
            elif type_str == "boolean":
                return bool(value)
            elif type_str == "float":
                return float(value)
            return value
        return value_dict

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
        return self._data.get(section, {})

    def get_processes(self):
        return self._data.get("processes", [])