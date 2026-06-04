import json
import os
from pathlib import Path

DEFAULT_CONFIG = {
    "llm": {
        "provider": "ollama",
        "endpoint": "http://localhost:11434",
        "model": "llama3",
        "timeout": 60,
        "max_tokens": 2048,
        "temperature": 0.7
    }
}

class ConfigManager:
    def __init__(self, config_dir=None):
        if config_dir is None:
            config_dir = Path.home() / ".config" / "iico"
        self.config_dir = Path(config_dir)
        self.config_file = self.config_dir / "config.json"
        self._config = DEFAULT_CONFIG.copy()
        self.load()

    def load(self):
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    user_config = json.load(f)
                    # Merge with default config
                    self._config["llm"].update(user_config.get("llm", {}))
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

    def get(self, section, key):
        return self._config.get(section, {}).get(key)
    
    def set(self, section, key, value):
        if section not in self._config:
            self._config[section] = {}
        self._config[section][key] = value
        self.save()

config_manager = ConfigManager()
