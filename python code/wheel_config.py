"""
Configuration and state management with threading safety
"""

import json
import os
import threading
from typing import Dict, Any, Optional


CONFIG_FILE = "wheel_config.json"
STATE_FILE = "wheel_state.json"

DEFAULT_CONFIG = {
    "YOUTUBE_CHANNEL_ID": "",
    "STREAMLABS_TOKEN": "",
    "PRICE_PER_SPIN": 2.0,
    "DISCOUNT_PRICE": 1.0,
    "DISCOUNT_DURATION": 300,
    "DOOM_REQUIRED": 10,
    # Total player deaths before the Hardcore world is considered "ended".
    # This value is pushed live to the Bedrock addon (and can be adjusted at runtime).
    "WORLD_END_DEATHS": 20,
    "REVIVE_PRICE": 5.0,
    "REVIVE_MIN": 5,
    "REVIVE_MAX": 100,
    "REVIVE_POINTS_COST": 1000,
    "REVIVE_POINTS_MIN": 500,
    "REVIVE_POINTS_MAX": 50000,
    "STREAMLABS_BOT_NAME": "streamlabs",
    "STREAMLABS_REVIVE_CONFIRM_MARKER": "🧬 Revive queued for",
    "YOUTUBE_DIRECT_REVIVE_ENABLED": False,
    # Randomizer/auto-spin feature
    "RANDOMIZER_ENABLED": False,
    "RANDOMIZER_INTERVAL": 30,  # seconds between auto-spins
    # Hardcore mode toggle
    "HARDCORE_MODE_ENABLED": True  # If False, disables world end and lives system
}

DEFAULT_STATE = {
    "spin_queue": [],
    "spin_history": [],
    "spin_tracker": {},
    "kill_tracker": {},
    "donation_tracker": {},
    "doom_hits": 0,
    "disabled_punishments": []
}


class ConfigManager:
    """Thread-safe configuration management"""
    
    @staticmethod
    def load() -> Dict[str, Any]:
        """Load config or create if missing, with validation"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    
                    # Validate and fill missing keys
                    for key, value in DEFAULT_CONFIG.items():
                        if key not in data:
                            data[key] = value
                    
                    return data
            except json.JSONDecodeError as e:
                print(f"⚠️ Config corrupted: {e}, creating backup and resetting")
                try:
                    import shutil
                    shutil.copy(CONFIG_FILE, f"{CONFIG_FILE}.backup")
                except Exception:
                    pass
        
        return DEFAULT_CONFIG.copy()
    
    @staticmethod
    def save(config: Dict[str, Any]) -> None:
        """Save config to file"""
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(config, f, indent=2)
        except IOError as e:
            print(f"❌ Failed to save config: {e}")
    
    @staticmethod
    def is_valid(config: Dict[str, Any]) -> bool:
        """Check if config has at least one donation source"""
        has_yt = bool(config.get("YOUTUBE_CHANNEL_ID"))
        has_sl = bool(config.get("STREAMLABS_TOKEN"))
        return has_yt or has_sl


class StateManager:
    """Thread-safe state management with lock"""
    
    _lock = threading.Lock()
    
    @staticmethod
    def load() -> Dict[str, Any]:
        """Load state from file"""
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r") as f:
                    data = json.load(f)
                    
                    # Validate required keys
                    for key, value in DEFAULT_STATE.items():
                        if key not in data:
                            data[key] = value
                    
                    return data
            except json.JSONDecodeError as e:
                print(f"⚠️ State corrupted: {e}, resetting to default")
        
        return DEFAULT_STATE.copy()
    
    @staticmethod
    def save(state: Dict[str, Any]) -> None:
        """Thread-safe save to file"""
        with StateManager._lock:
            try:
                with open(STATE_FILE, "w") as f:
                    json.dump(state, f, indent=2)
            except IOError as e:
                print(f"❌ Failed to save state: {e}")
    
    @staticmethod
    def safe_get(state: Dict[str, Any], key: str, default: Any = None) -> Any:
        """Thread-safe read from state"""
        with StateManager._lock:
            return state.get(key, default)
    
    @staticmethod
    def safe_update(state: Dict[str, Any], key: str, value: Any) -> None:
        """Thread-safe update to state"""
        with StateManager._lock:
            state[key] = value
    
    @staticmethod
    def safe_increment(state: Dict[str, Any], key: str, delta: int = 1) -> int:
        """Thread-safe increment (returns new value)"""
        with StateManager._lock:
            current = state.get(key, 0)
            new_value = current + delta
            state[key] = new_value
            return new_value
