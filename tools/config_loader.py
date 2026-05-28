"""Configuration loader for dynamically reading strategy parameters."""

import os
import json
from typing import Any, Dict
from engine.logger import logger

CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config",
    "strategies.json"
)


def load_config() -> Dict[str, Any]:
    """Load configuration from config/strategies.json.

    Falls back to safe defaults if file is not found or malformed.
    """
    if not os.path.exists(CONFIG_PATH):
        logger.warning(f"Config file not found at {CONFIG_PATH}. Using empty default config.")
        return {}

    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to parse strategies.json: {e}. Using empty default config.")
        return {}


def get_strategy_params(strategy_key: str) -> Dict[str, Any]:
    """Get dynamic parameters for a specific strategy from config."""
    config = load_config()
    return config.get("strategies", {}).get(strategy_key, {})


def get_universe_params(universe_key: str) -> Dict[str, Any]:
    """Get dynamic parameters for a specific universe from config."""
    config = load_config()
    return config.get("universes", {}).get(universe_key, {})
