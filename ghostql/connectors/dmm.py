"""
ghostql/connectors/dmm.py
Toridion DMM associative memory connector for GhostQL.

This is the reference connector implementation.
It speaks to the TQNN DMM searchDoc / storeDoc PHP API endpoints
using multipart/form-data POST requests.

To build your own connector, subclass BaseConnector (see base.py).
"""
import re
import logging
import hashlib
import requests
import urllib3
from typing import Dict, Any, Set

from .base import BaseConnector, ConnectorResult
from ..core.config import GhostQLConfig

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger(__name__)


def _strip_timestamp(fileref: str) -> str:
    """Strip trailing ::UNIX_TIMESTAMP from a DMM filereference.
    Full:   basename::lineN::REC-ID::fpd_CODE::TIMESTAMP
    Stable: basename::lineN::REC-ID::fpd_CODE
    """
    return re.sub(r'::\d+$', '', fileref)


class DMMConnector(BaseConnector):
    """
    Toridion DMM connector.

    Translates GhostQL pattern lookups into DMM searchDoc API calls.
    All hashing is handled by the query layer before calling search().
    This connector is intentionally dumb — it only moves data.
    """

    def __init__(self, config: GhostQLConfig):
        self.api_url    = config.dmm_api_url
        self.api_key    = config.dmm_api_key
        self.api_secret = config.dmm_api_secret
        self.dataset    = config.dmm_dataset
        self.verify_ssl = config.dmm_verify_ssl
        self.timeout    = config.api_timeout

    def _post(self, fields: Dict[str, str]) -> Dict[str, Any]:
        try:
            resp = requests.post(
                self.api_url,
                data={
                    'tqnnAPIKEY':    self.api_key,
                    'tqnnAPISECRET': self.api_secret,
                    **fields,
                },
                timeout=self.timeout,
                verify=self.verify_ssl,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"[DMM] API error: {e}")
            return {'tqnn_response': 'ERROR', 'matches': 0, 'filelist': ''}

    def search(self, pattern: str, dataset: str = '') -> ConnectorResult:
        """Single searchDoc call. Returns stable (timestamp-stripped) filereferences."""
        ds = dataset or self.dataset
        logger.debug(f"[DMM] searchDoc pattern={pattern[:32]}… dataset={ds}")

        data = self._post({
            'pattern':         pattern,
            'return_filelist': '1',
            'dataset':         ds,
        })

        tqnn_resp = data.get('tqnn_response', 'ERROR')
        fileset: Set[str] = set()

        for raw in (data.get('filelist') or '').strip().split('\n'):
            raw = raw.strip()
            if raw:
                fileset.add(_strip_timestamp(raw.split()[0]))

        logger.debug(f"[DMM] → {tqnn_resp}  hits={len(fileset)}")
        return ConnectorResult(
            success=tqnn_resp == 'MATCH',
            fileset=fileset,
            response_code=tqnn_resp,
            raw=data,
        )

    def store(self, filereference: str, pattern: str, dataset: str = '') -> Dict[str, Any]:
        """Store a document reference into DMM."""
        ds = dataset or self.dataset
        logger.debug(f"[DMM] storeDoc ref={filereference[:60]}…")

        data = self._post({
            'filereference': filereference,
            'pattern':       pattern,
            'dataset':       ds,
        })

        return {
            'success':  data.get('tqnn_response') in ('STORE_OK', 'OK'),
            'response': data.get('tqnn_response', 'ERROR'),
            'raw':      data,
        }

    def ping(self) -> bool:
        """Health check using a known-safe token."""
        token   = '__ghostql_ping__'
        h1      = hashlib.sha256(token.encode()).hexdigest()
        mixed   = (token + h1)[:16]
        pattern = hashlib.sha256(mixed.encode()).hexdigest()[:16]

        result = self.search(pattern)
        reachable = result.response_code in ('MATCH', 'NO_MATCH', 'NOMATCH', '')
        logger.info(f"[DMM] ping → {'OK' if reachable else 'FAILED'} (code={result.response_code})")
        return reachable

    def name(self) -> str:
        return 'DMM (Toridion)'
