import json
import os
import copy
from pathlib import Path

DEFAULT_CONFIG = {
    "active_provider": "ollama",
    "providers": {
        "ollama": {
            "endpoint": "http://localhost:11434",
            "model": "llama3",
            "temperature": 0.7
        },
        "openai": {
            "endpoint": "http://127.0.0.1:3000/v1",
            "model": "llama3",
            "temperature": 0.7
        }
    }
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
                    
                    # Migración de configuración vieja a nueva
                    if "llm" in user_config:
                        llm_cfg = user_config["llm"]
                        prov = llm_cfg.get("provider", "ollama")
                        self._config["active_provider"] = prov
                        self._config["providers"][prov]["endpoint"] = llm_cfg.get("endpoint", self._config["providers"][prov]["endpoint"])
                        self._config["providers"][prov]["model"] = llm_cfg.get("model", self._config["providers"][prov]["model"])
                    else:
                        self._config["active_provider"] = user_config.get("active_provider", "ollama")
                        for p in ["ollama", "openai"]:
                            if p in user_config.get("providers", {}):
                                self._config["providers"][p].update(user_config["providers"][p])
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

    def get_active_provider(self):
        return self._config["active_provider"]
        
    def set_active_provider(self, provider_name):
        self._config["active_provider"] = provider_name
        self.save()

    def get_provider_config(self, provider_name=None):
        if not provider_name:
            provider_name = self.get_active_provider()
        return self._config["providers"].get(provider_name, {})
    
    def set_provider_config(self, key, value, provider_name=None):
        if not provider_name:
            provider_name = self.get_active_provider()
        if provider_name not in self._config["providers"]:
            self._config["providers"][provider_name] = {}
        self._config["providers"][provider_name][key] = value
        self.save()

config_manager = ConfigManager()
