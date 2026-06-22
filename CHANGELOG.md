# Changelog

All notable changes to GhostQL will be documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [1.0.0] — 2025-06-22

### Added
- Initial open-source release
- GhostQL TCP server with newline-delimited JSON protocol
- GhostQL query language v1.0.0:
  - `SELECT … WHERE field='value'` — exact token intersection
  - `SELECT … WHERE field LIKE 'text'` — similarity search with overlap scoring
  - `SELECT … JOIN table2 ON field` — in-memory hash join
  - `WITH PQR` — self-salting SHA-256 PQR hashing per token
  - `WITH PQR FPD` — False Positive Defence (forward ∩ reversed-input hash)
- Modular connector architecture (`ghostql/connectors/base.py`)
- Toridion DMM reference connector (`ghostql/connectors/dmm.py`)
- Secure `ghostql.conf` configuration (no hardcoded credentials)
- Environment variable overrides for CI/CD
- PHP example client (`examples/query_ghostql.php`)
- Python example client (`examples/query_ghostql.py`)
- MIT licence

### Architecture
- Query logic fully separated from connector logic
- Each query type is a standalone module (`select.py`, `like.py`, `join.py`)
- Tokeniser and PQR hashing are independent, importable modules
- Drop-in custom connectors via `module:ClassName` config format

---

*GhostQL is built on [Toridion DMM](https://toridion.com) associative memory technology.*
