"""
Configuration loader for the cookbook application.
"""
import yaml
from pathlib import Path

# Default configuration
DEFAULT_CONFIG = {
    'spell_check': {
        'similarity_threshold': 70
    },
    'database': {
        'path': 'data/recipes.db'
    },
    'embeddings': {
        'model': 'nomic-embed-text',
        'cache_dir': 'embeddings_cache'
    },
    'staging': {
        'addable_dir': 'addable',
        'editable_dir': 'editable'
    }
}

_config = None


def load_config():
    """Load configuration from config.yaml, falling back to defaults."""
    global _config
    if _config is not None:
        return _config
    
    config_path = Path(__file__).parent.parent / 'config' / 'config.yaml'
    
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                _config = yaml.safe_load(f)
                # Merge with defaults to ensure all keys exist
                _config = _merge_config(DEFAULT_CONFIG, _config)
        except Exception as e:
            print(f"Warning: Failed to load config.yaml: {e}. Using defaults.", file=__import__('sys').stderr)
            _config = DEFAULT_CONFIG.copy()
    else:
        _config = DEFAULT_CONFIG.copy()
    
    return _config


def _merge_config(default, user):
    """Merge user config with defaults, recursively."""
    result = default.copy()
    for key, value in user.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _merge_config(result[key], value)
        else:
            result[key] = value
    return result


def get_config():
    """Get the current configuration."""
    if _config is None:
        load_config()
    return _config


def get_similarity_threshold():
    """Get the spell-check similarity threshold."""
    config = get_config()
    return config.get('spell_check', {}).get('similarity_threshold', 70)


def get_database_path():
    """Get the database file path."""
    config = get_config()
    db_path = config.get('database', {}).get('path', 'data/recipes.db')
    # Make path relative to project root
    project_root = Path(__file__).parent.parent
    return project_root / db_path
