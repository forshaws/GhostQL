"""
ghostql/query/select.py
GhostQL SELECT executor — WHERE equality queries.

Flattens all field names and values from the WHERE clause into a token list,
searches each token via the connector, and ANDs the result sets together.

WHERE name='Mills' AND nhs='4855805912'
→ tokens: ['name', 'Mills', 'nhs', '4855805912']
→ search each → intersect all filesets → return matching document refs

This mirrors the DMM IDE multi-search pattern exactly.
"""
import logging
from typing import Dict, List, Set, Any

from ..connectors.base import BaseConnector
from .pqr import pqr_hash, pqr_hash_reversed

logger = logging.getLogger(__name__)


def _search_token(
    connector: BaseConnector,
    token: str,
    use_pqr: bool,
    use_fpd: bool,
    dataset: str,
) -> Set[str]:
    """
    Search a single token, applying PQR and FPD as configured.

    plain:     raw token → one connector.search() call
    PQR:       sha256-self-salt(token) → one call
    PQR+FPD:   forward hash ∩ reversed-input hash → two calls, intersect
    """
    if not use_pqr:
        result = connector.search(token, dataset)
        return result.fileset

    fwd = connector.search(pqr_hash(token), dataset)
    if not use_fpd:
        return fwd.fileset

    rev = connector.search(pqr_hash_reversed(token), dataset)
    intersection = fwd.fileset & rev.fileset
    logger.debug(
        f"[FPD] '{token}'  fwd={len(fwd.fileset)}  "
        f"rev={len(rev.fileset)}  ∩={len(intersection)}"
    )
    return intersection


def execute_select(
    parsed: Dict[str, Any],
    connector: BaseConnector,
    dataset: str = '',
    max_results: int = 50,
) -> List[Dict[str, Any]]:
    """
    Execute a WHERE equality query.

    Args:
        parsed:      Output of query.parser.parse()
        connector:   Active BaseConnector instance
        dataset:     Dataset/namespace override (falls back to connector default)
        max_results: Cap on returned rows

    Returns:
        List of result dicts, each containing at minimum {'document': str}
    """
    conditions = parsed['conditions']
    columns    = parsed['columns']
    use_pqr    = parsed['use_pqr']
    use_fpd    = parsed['use_fpd']
    mode       = parsed['mode']

    if not conditions:
        return [{'error': 'No WHERE conditions provided'}]

    # Flatten: field1, value1, field2, value2, …
    tokens = []
    for field, value in conditions.items():
        tokens.append(field)
        tokens.append(value)

    logger.info(f"[SELECT] {len(tokens)} token(s)  mode={mode}  tokens={tokens}")

    master_set: Set[str] | None = None
    search_summary: Dict[str, int] = {}

    for token in tokens:
        token_set = _search_token(connector, token, use_pqr, use_fpd, dataset)
        search_summary[token] = len(token_set)
        logger.debug(f"[SELECT] '{token}' → {len(token_set)} hit(s)")

        master_set = token_set if master_set is None else master_set & token_set
        logger.debug(f"[SELECT] running AND total: {len(master_set)}")

        if master_set is not None and len(master_set) == 0:
            break

    if not master_set:
        return [{
            'status':         'NO_MATCHES',
            'message':        f"No documents matched all {len(tokens)} token(s)",
            'mode':           mode,
            'tokens':         tokens,
            'search_summary': search_summary,
        }]

    results = []
    for ref in sorted(master_set)[:max_results]:
        row: Dict[str, Any] = {}
        for col in columns:
            if col.lower() in ('document', 'filename', '*'):
                row['document'] = ref
            elif col in conditions:
                row[col] = conditions[col]
            else:
                row[col] = ref
        if 'document' not in row:
            row['document'] = ref
        results.append(row)

    logger.info(f"[SELECT] → {len(results)} result(s)")
    return results
