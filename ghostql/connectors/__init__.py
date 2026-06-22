"""
ghostql/connectors/__init__.py
Connector loader — resolves connector type from config and returns an instance.
"""
import importlib
import logging
from .base import BaseConnector
from ..core.config import GhostQLConfig

logger = logging.getLogger(__name__)

_BUILTIN_CONNECTORS = {
    'dmm':   ('ghostql.connectors.dmm',   'DMMConnector'),
    'local': ('ghostql.connectors.local', 'LocalFileConnector'),
}


def load_connector(config: GhostQLConfig) -> BaseConnector:
    """
    Load and instantiate the configured connector.

    Built-in connectors are resolved by name (e.g. 'dmm').
    Custom connectors can be specified as 'module.path:ClassName'.
    """
    connector_type = config.connector_type.strip()

    if connector_type in _BUILTIN_CONNECTORS:
        module_path, class_name = _BUILTIN_CONNECTORS[connector_type]
    elif ':' in connector_type:
        module_path, class_name = connector_type.rsplit(':', 1)
    else:
        raise ValueError(
            f"Unknown connector type: '{connector_type}'. "
            f"Built-ins: {list(_BUILTIN_CONNECTORS)}. "
            f"Custom: use 'my.module:MyClass' format in ghostql.conf"
        )

    logger.info(f"Loading connector: {module_path}:{class_name}")
    module = importlib.import_module(module_path)
    cls    = getattr(module, class_name)
    return cls(config)
