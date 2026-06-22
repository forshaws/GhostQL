# GhostQL Connector Development Guide

GhostQL separates query logic from data retrieval through a simple connector interface. You can connect GhostQL to any data backend — associative memory, vector stores, search engines, filesystems — by implementing three methods.

---

## The contract

```python
# ghostql/connectors/base.py

class BaseConnector(ABC):

    def search(self, pattern: str, dataset: str = '') -> ConnectorResult:
        """Single pattern lookup. Returns a set of document references."""
        ...

    def store(self, filereference: str, pattern: str, dataset: str = '') -> dict:
        """Write a document reference with associated metadata."""
        ...

    def ping(self) -> bool:
        """Return True if the backend is reachable."""
        ...
```

That's it. GhostQL handles everything else: parsing, hashing, tokenising, scoring, joining.

---

## ConnectorResult

```python
ConnectorResult(
    success       = True,
    fileset       = {'doc::line1::ID::fpd_abc', 'doc::line2::ID::fpd_xyz'},
    response_code = 'MATCH',   # backend-specific status string
    raw           = {...}      # raw backend response for debugging
)
```

`fileset` is a `Set[str]` of document reference strings — whatever your backend uses as a unique document identifier. GhostQL ANDs these sets across tokens; the format doesn't matter as long as it's consistent.

---

## Step-by-step: build a connector

### 1. Create your file

```
ghostql/connectors/my_backend.py
```

### 2. Subclass BaseConnector

```python
from ghostql.connectors.base import BaseConnector, ConnectorResult
from ghostql.core.config import GhostQLConfig

class MyBackendConnector(BaseConnector):

    def __init__(self, config: GhostQLConfig):
        # Read any custom config your backend needs
        # You can extend GhostQLConfig or read from a [my_backend] section
        self.endpoint = config._cfg.get('my_backend', {}).get('endpoint', '')

    def search(self, pattern: str, dataset: str = '') -> ConnectorResult:
        # Call your backend with `pattern` — already hashed if PQR is active
        results = my_backend_client.lookup(pattern)
        return ConnectorResult(
            success  = bool(results),
            fileset  = set(results),
        )

    def store(self, filereference: str, pattern: str, dataset: str = '') -> dict:
        ok = my_backend_client.put(filereference, pattern)
        return {'success': ok, 'response': 'OK' if ok else 'ERROR'}

    def ping(self) -> bool:
        try:
            return my_backend_client.health_check()
        except Exception:
            return False

    def name(self) -> str:
        return 'My Backend'
```

### 3. Register your connector

Add to `ghostql/connectors/__init__.py`:

```python
_BUILTIN_CONNECTORS = {
    'dmm':        ('ghostql.connectors.dmm',        'DMMConnector'),
    'my_backend': ('ghostql.connectors.my_backend', 'MyBackendConnector'),
}
```

Or use the custom format in `ghostql.conf` without touching the core code:

```ini
[connector]
type = my_package.my_module:MyBackendConnector
```

### 4. Configure

Add a section to `ghostql.conf.example` for your backend's credentials.

---

## The golden rule

**Connectors must not implement query logic.**

No hashing, no tokenising, no scoring, no AND/OR logic. The connector receives a single pattern (already processed by the query layer) and returns a set of document references. That's the entire job.

If you find yourself writing hashing code in a connector, move it to `ghostql/query/pqr.py`.

---

## Reference implementation

See `ghostql/connectors/dmm.py` — the Toridion DMM connector is the canonical example of a well-behaved GhostQL connector.

---

## Ideas for new connectors

| Backend | Notes |
|---------|-------|
| Redis | Use `SCAN` + key pattern matching |
| Weaviate | Map `search()` to a vector similarity query |
| Milvus | Similar to Weaviate |
| Elasticsearch | Map to a `term` query |
| SQLite | Full-text search via FTS5 |
| Filesystem | Walk directories, match filenames/content |
| Docling | Direct ingest pipeline integration |

PRs welcome — see `CONTRIBUTING.md`.
