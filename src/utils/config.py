"""YAML configuration loader."""

from pathlib import Path
from typing import Any, Dict, Union
import yaml


def load_config(config_path: Union[str, Path] = "config.yaml") -> Dict[str, Any]:
    """Load configuration dictionary from YAML."""
    path = Path(config_path)
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
