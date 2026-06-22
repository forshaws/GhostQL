"""
ghostql/connectors/local.py
GhostQL Local File Connector

Queries a pre-built PQR+FPD index stored as a local JSON file.
No DMM credentials required — ideal for demos, development, and testing.

The index is built by demo/build_demo_index.py and committed to the repo.
End users can query it immediately after cloning:

  [connector]
  type = local

  [local]
  index_path = demo/demo_index.json

This connector is read-only for the demo.
store() is a no-op — implement persistence if you want a writable local connector.
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, Set

from .base import BaseConnector, ConnectorResult
from ..core.config import GhostQLConfig

logger = logging.getLogger(__name__)


class LocalFileConnector(BaseConnector):
    """
    Local PQR+FPD index connector.
    Loads demo/demo_index.json into memory at startup and serves
    searchDoc-equivalent lookups entirely from RAM. O(1) per lookup.
    """

    def __init__(self, config: GhostQLConfig):
        if config._cfg.has_section('local'):
            raw_path = config._cfg['local'].get('index_path', 'demo/demo_index.json')
        else:
            raw_path = 'demo/demo_index.json'

        self.index_path = Path(raw_path)
        if not self.index_path.is_absolute():
            # Resolve relative to repo root (two levels up from this file)
            self.index_path = Path(__file__).parent.parent.parent / self.index_path

        self._index: Dict[str, list] = {}
        self._meta:  Dict[str, Any]  = {}
        self._load()

    def _load(self):
        if not self.index_path.exists():
            raise FileNotFoundError(
                f"GhostQL local connector: index not found at {self.index_path}\n"
                f"Run:  python demo/build_demo_index.py"
            )
        logger.info(f"[LOCAL] Loading index from {self.index_path}")
        with open(self.index_path) as f:
            data = json.load(f)
        self._meta  = data.get('meta', {})
        self._index = data.get('index', {})
        logger.info(
            f"[LOCAL] Loaded {self._meta.get('records','?')} records  "
            f"index_entries={len(self._index):,}"
        )

    def search(self, pattern: str, dataset: str = '') -> ConnectorResult:
        refs = self._index.get(pattern, [])
        logger.debug(f"[LOCAL] search pattern={pattern[:16]}  hits={len(refs)}")
        return ConnectorResult(
            success       = bool(refs),
            fileset       = set(refs),
            response_code = 'MATCH' if refs else 'NO_MATCH',
        )

    def store(self, filereference: str, pattern: str, dataset: str = '') -> Dict[str, Any]:
        """No-op for the demo connector."""
        logger.debug(f"[LOCAL] store (no-op)  ref={filereference[:60]}")
        return {'success': True, 'response': 'OK'}

    def ping(self) -> bool:
        ok = bool(self._index)
        logger.info(f"[LOCAL] ping → {'OK' if ok else 'FAILED'}  entries={len(self._index):,}")
        return ok

    def name(self) -> str:
        return f"Local Demo ({self._meta.get('records','?')} records)"
