# Contributing to GhostQL

Thank you for your interest in GhostQL. This is an early-stage open-source project and contributions are very welcome — whether that's a bug report, a new connector, a query type, or documentation improvements.

## Quick orientation

```
ghostql/
├── core/           Config loading, logging — rarely needs changing
├── connectors/     Data backends — great place to contribute
│   ├── base.py     The contract every connector must implement
│   └── dmm.py      Reference implementation (Toridion DMM)
└── query/          Query logic — modular by design
    ├── parser.py   SQL-like syntax → structured dict
    ├── select.py   WHERE equality queries
    ├── like.py     LIKE similarity / fuzzy search
    ├── join.py     In-memory JOIN
    └── pqr.py      PQR hashing (self-salting SHA-256)
```

## Building a new connector

The most impactful contribution is a new data connector — Redis, Weaviate, Milvus, Elasticsearch, a plain filesystem, whatever makes sense for your use case.

1. Read `ghostql/connectors/base.py` — the `BaseConnector` abstract class is the entire contract
2. Create `ghostql/connectors/your_backend.py`
3. Implement `search()`, `store()`, and `ping()`
4. Add your connector to the `_BUILTIN_CONNECTORS` dict in `ghostql/connectors/__init__.py`
5. Add an example to `examples/`
6. Open a PR

The key rule: **connectors must not implement query logic**. No hashing, no tokenising, no scoring. Those live in `ghostql/query/`. The connector is a pure retrieval primitive.

## Adding a query type

1. Create `ghostql/query/your_type.py` with an `execute_*` function
2. Add routing in `ghostql/query/__init__.py` → `dispatch()`
3. Add syntax documentation to `ghostql/query/parser.py` and `docs/query-language.md`
4. Add a test case to `examples/query_ghostql.php` and `examples/query_ghostql.py`

## Reporting issues

Please open a GitHub Issue with:
- GhostQL version
- Python version
- Connector type
- The query that failed (anonymise any sensitive data)
- The error or unexpected output

## Code style

- Python 3.11+, type hints throughout
- Docstrings on all public functions and classes
- Keep modules focused — one responsibility per file
- No credentials in code, ever

## Roadmap ideas (looking for contributors)

- `ghostql/connectors/redis.py` — Redis as associative backend
- `ghostql/connectors/weaviate.py` — vector store connector
- `ghostql/connectors/filesystem.py` — plain-text file ingest
- Multi-table JOIN support
- Native Python client library (no raw TCP)
- `GROUP BY` aggregation
- WebSocket interface alongside TCP
- PyPI package

## Licence

By contributing you agree your code will be released under the MIT licence.
