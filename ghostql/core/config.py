"""
ghostql/core/config.py
Secure configuration loader for GhostQL.

Reads ghostql.conf (INI format). Never hardcodes credentials.
Environment variables override config file values for CI/CD use:

  GHOSTQL_DMM_API_KEY, GHOSTQL_DMM_API_SECRET, GHOSTQL_DMM_DATASET
  GHOSTQL_SERVER_PASSWORD
  GHOSTQL_DMM_API_URL
"""
import configparser
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULTS = {
    'server': {
        'host': '0.0.0.0',
        'port': '5051',
        'username': 'admin',
        'password': '',
    },
    'connector': {
        'type': 'dmm',
    },
    'dmm': {
        'api_url': 'https://tqnn.local/v1/document/search/searchDoc.php',
        'api_key': '',
        'api_secret': '',
        'dataset': '',
        'verify_ssl': 'true',
    },
    'query': {
        'similarity_threshold': '0.4',
        'max_results': '50',
        'api_timeout': '15',
    },
    'logging': {
        'level': 'info',
        'file': '',
    },
}

_ENV_MAP = {
    ('dmm', 'api_key'):    'GHOSTQL_DMM_API_KEY',
    ('dmm', 'api_secret'): 'GHOSTQL_DMM_API_SECRET',
    ('dmm', 'dataset'):    'GHOSTQL_DMM_DATASET',
    ('dmm', 'api_url'):    'GHOSTQL_DMM_API_URL',
    ('server', 'password'): 'GHOSTQL_SERVER_PASSWORD',
}


class GhostQLConfig:
    """Parsed, validated GhostQL configuration."""

    def __init__(self, path: str | Path | None = None):
        self._cfg = configparser.ConfigParser()

        # Apply defaults
        for section, values in _DEFAULTS.items():
            self._cfg[section] = values

        # Load file
        conf_path = Path(path) if path else self._find_config()
        if conf_path and conf_path.exists():
            logger.info(f"Loading config from {conf_path}")
            self._cfg.read(conf_path)
        else:
            logger.warning("No ghostql.conf found — using defaults and environment variables only")

        # Environment overrides
        for (section, key), env_var in _ENV_MAP.items():
            val = os.environ.get(env_var)
            if val:
                self._cfg[section][key] = val

        self._validate()

    def _find_config(self) -> Path | None:
        """Search for ghostql.conf in cwd, then parent dirs."""
        here = Path.cwd()
        for candidate in [here, here.parent, Path(__file__).parent.parent]:
            p = candidate / 'ghostql.conf'
            if p.exists():
                return p
        return None

    def _validate(self):
        required = [('dmm', 'api_key'), ('dmm', 'api_secret'), ('server', 'password')]
        missing = [f"{s}.{k}" for s, k in required if not self._cfg[s].get(k)]
        if missing:
            raise ValueError(
                f"GhostQL config missing required values: {', '.join(missing)}\n"
                f"Copy ghostql.conf.example to ghostql.conf and fill in your credentials."
            )

    # ── Accessors ─────────────────────────────────────────────────────────────

    @property
    def server_host(self) -> str:
        return self._cfg['server']['host']

    @property
    def server_port(self) -> int:
        return int(self._cfg['server']['port'])

    @property
    def server_username(self) -> str:
        return self._cfg['server']['username']

    @property
    def server_password(self) -> str:
        return self._cfg['server']['password']

    @property
    def connector_type(self) -> str:
        return self._cfg['connector']['type']

    @property
    def dmm_api_url(self) -> str:
        return self._cfg['dmm']['api_url']

    @property
    def dmm_api_key(self) -> str:
        return self._cfg['dmm']['api_key']

    @property
    def dmm_api_secret(self) -> str:
        return self._cfg['dmm']['api_secret']

    @property
    def dmm_dataset(self) -> str:
        return self._cfg['dmm']['dataset']

    @property
    def dmm_verify_ssl(self) -> bool:
        return self._cfg['dmm'].getboolean('verify_ssl', fallback=True)

    @property
    def similarity_threshold(self) -> float:
        return float(self._cfg['query']['similarity_threshold'])

    @property
    def max_results(self) -> int:
        return int(self._cfg['query']['max_results'])

    @property
    def api_timeout(self) -> int:
        return int(self._cfg['query']['api_timeout'])

    @property
    def log_level(self) -> str:
        return self._cfg['logging']['level'].upper()

    @property
    def log_file(self) -> str:
        return self._cfg['logging']['file']
