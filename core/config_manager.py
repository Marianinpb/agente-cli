import json
import os
import copy
from pathlib import Path

DEFAULT_CONFIG = {
    "active_model_id": "",
    "providers": [
        {"name": "default_ollama", "type": "ollama", "endpoint": "http://localhost:11434"}
    ],
    "settings": {}
}

class ConfigManager:
    def __init__(self, config_dir=None):
        if config_dir is None:
            config_dir = Path.home() / ".config" / "iico"
        self.config_dir = Path(config_dir)
        self.config_file = self.config_dir / "config.json"
        self._config = copy.deepcopy(DEFAULT_CONFIG)
        self.load()

    def load(self):
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    user_config = json.load(f)
                    
                    if "providers" in user_config and isinstance(user_config["providers"], list):
                        self._config["providers"] = user_config["providers"]
                    elif "providers" in user_config and isinstance(user_config["providers"], dict):
                        # Migración del formato anterior (dict) a lista
                        new_providers = []
                        for name, data in user_config["providers"].items():
                            p_type = user_config.get("active_provider", "ollama") if name == user_config.get("active_provider") else "openai"
                            if "11434" in data.get("endpoint", ""): p_type = "ollama"
                            new_providers.append({"name": name, "type": p_type, "endpoint": data.get("endpoint", "")})
                        self._config["providers"] = new_providers

                    self._config["active_model_id"] = user_config.get("active_model_id", "")
                    if "settings" in user_config:
                        self._config["settings"] = user_config["settings"]
            except Exception as e:
                print(f"Error loading config: {e}")
        else:
            self.save()

    def save(self):
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")

    def get_providers(self):
        return self._config["providers"]
        
    def add_provider(self, name, p_type, endpoint):
        for p in self._config["providers"]:
            if p["endpoint"] == endpoint:
                p["name"] = name
                p["type"] = p_type
                self.save()
                return
        self._config["providers"].append({"name": name, "type": p_type, "endpoint": endpoint})
        self.save()

    def get_active_model_id(self):
        return self._config["active_model_id"]
        
    def set_active_model_id(self, model_id):
        self._config["active_model_id"] = model_id
        self.save()

    def get_settings(self):
        return self._config.get("settings", {})
        
    def set_settings(self, settings: dict):
        self._config["settings"] = settings
        self.save()

config_manager = ConfigManager()
