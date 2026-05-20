from pydantic import BaseModel
from typing import Dict, Any
import yaml
from pathlib import Path

current_dir = Path(__file__).parent

class ConfigModel(BaseModel):
    """Pydantic config model for validation"""
    csv_url: str
    history_repo: str
    history_path: str
    history_days: int
    cache_ttl_seconds: int
    fallback_to_last_known_good: bool
    stale_threshold_hours: int
    critically_stale_threshold_hours: int
    expected_min_rows: int
    expected_min_columns: int

def read_config_file(path: str) -> Dict[str, Any]:
    """Read and parse a YAML config file"""
    config_path = current_dir.parent / path
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def get_config() -> ConfigModel:
    """Get and validate configuration"""
    try:
        config_data = read_config_file('config/openedx/data_source.yaml')
        return ConfigModel(**config_data)
    except Exception as e:
        raise ValueError(f"Config validation failed: {str(e)}")