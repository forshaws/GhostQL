"""
ghostql/connectors/base.py
Abstract base class for GhostQL data connectors.

To build a custom connector (Redis, Elasticsearch, Weaviate, etc.):

  1. Subclass BaseConnector
  2. Implement all abstract methods
  3. Set connector.type = your_module_name in ghostql.conf
  4. Drop your file into ghostql/connectors/

GhostQL will import it automatically at startup.

The connector contract is deliberately minimal:
  - search(pattern)     → set of file/document references
  - store(ref, pattern) → confirmation
  - ping()              → bool

All hashing, tokenising, and query logic lives in the query layer,
NOT in the connector. The connector is a pure retrieval primitive.
"""
from abc import ABC, abstractmethod
from typing import Set, Dict, Any


class ConnectorResult:
    """Standardised result from a single connector search call."""

    __slots__ = ('success', 'fileset', 'response_code', 'raw')

    def __init__(
        self,
        success: bool,
        fileset: Set[str],
        response_code: str = '',
        raw: Dict[str, Any] | None = None,
    ):
        self.success       = success
        self.fileset       = fileset
        self.response_code = response_code
        self.raw           = raw or {}

    def __repr__(self):
        return f"<ConnectorResult success={self.success} hits={len(self.fileset)} code={self.response_code!r}>"


class BaseConnector(ABC):
    """
    Abstract data connector for GhostQL.

    All connectors must implement:
      search(pattern)           — single pattern lookup
      store(filereference, pattern) — write a record
      ping()                    — health check

    Connectors MUST NOT implement query logic, hashing, or tokenising.
    Those belong in ghostql/query/.
    """

    @abstractmethod
    def search(self, pattern: str, dataset: str = '') -> ConnectorResult:
        """
        Search for documents matching `pattern`.

        Args:
            pattern:  The search token (already hashed by the query layer if PQR is active)
            dataset:  Optional dataset/namespace override

        Returns:
            ConnectorResult with fileset of matching document references
        """
        ...

    @abstractmethod
    def store(self, filereference: str, pattern: str, dataset: str = '') -> Dict[str, Any]:
        """
        Store a document reference with associated pattern metadata.

        Args:
            filereference: Unique document URI / path
            pattern:       JSON string or free text describing the document
            dataset:       Optional dataset/namespace override

        Returns:
            Dict with at minimum {'success': bool, 'response': str}
        """
        ...

    @abstractmethod
    def ping(self) -> bool:
        """
        Lightweight health check. Return True if the backend is reachable.
        """
        ...

    def name(self) -> str:
        """Human-readable connector name for logging."""
        return self.__class__.__name__
