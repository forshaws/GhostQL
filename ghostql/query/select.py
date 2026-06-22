"""
ghostql/query/select.py
GhostQL SELECT executor — WHERE equality queries with AND/OR support.

Operator precedence matches MySQL standard: AND binds tighter than OR.

  WHERE name='Mills' AND dlbl='Retinal' OR dlbl='Diabetes'
  = (name='Mills' AND dlbl='Retinal') OR (dlbl='Diabetes')

Execution:
  1. For each OR group → flatten field/value pairs into tokens → AND intersect
  2. Union all OR group results together
  3. Deduplicate and return

Single AND group (no OR):
  WHERE name='Mills' AND nhs='4855805912'
  → tokens: ['name','Mills','nhs','4855805912'] → intersect → results

Mixed AND/OR:
  WHERE name='Mills' AND dlbl='Retinal' OR dlbl='Diabetes'
  → group1: ['name','Mills','dlbl','Retinal'] → intersect → set A
  → group2: ['dlbl','Diabetes'] → intersect → set B
  → union(A, B) → results
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

    plain:    raw token → one connector.search() call
    PQR:      sha256-self-salt(token) → one call
    PQR+FPD:  forward hash ∩ reversed-input hash → two calls, intersect
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


def _execute_and_group(
    conditions: Dict[str, str],
    connector: BaseConnector,
    use_pqr: bool,
    use_fpd: bool,
    dataset: str,
) -> tuple[Set[str], Dict[str, int]]:
    """
    Execute a single AND group — intersect all token filesets.
    Returns (fileset, search_summary).
    """
    tokens = []
    for field, value in conditions.items():
        tokens.append(field)
        tokens.append(value)

    master_set: Set[str] | None = None
    summary: Dict[str, int] = {}

    for token in tokens:
        token_set = _search_token(connector, token, use_pqr, use_fpd, dataset)
        summary[token] = len(token_set)
        logger.debug(f"[SELECT] '{token}' → {len(token_set)} hit(s)")

        master_set = token_set if master_set is None else master_set & token_set
        logger.debug(f"[SELECT] running AND total: {len(master_set)}")

        if master_set is not None and len(master_set) == 0:
            break

    return (master_set or set(), summary)


def execute_select(
    parsed: Dict[str, Any],
    connector: BaseConnector,
    dataset: str = '',
    max_results: int = 50,
) -> List[Dict[str, Any]]:
    """
    Execute a WHERE equality query with full AND/OR support.

    Args:
        parsed:      Output of query.parser.parse()
        connector:   Active BaseConnector instance
        dataset:     Dataset/namespace override
        max_results: Cap on returned rows

    Returns:
        List of result dicts, each containing at minimum {'document': str}
    """
    or_groups  = parsed.get('or_groups', [])
    columns    = parsed['columns']
    use_pqr    = parsed['use_pqr']
    use_fpd    = parsed['use_fpd']
    mode       = parsed['mode']

    # Backward compat — if no or_groups, fall back to conditions
    if not or_groups:
        conditions = parsed.get('conditions', {})
        if conditions:
            or_groups = [conditions]

    if not or_groups:
        return [{'error': 'No WHERE conditions provided'}]

    logger.info(
        f"[SELECT] {len(or_groups)} OR group(s)  mode={mode}  "
        f"groups={or_groups}"
    )

    # ── Execute each OR group and union the results ───────────────────────────
    master_set:    Set[str]       = set()
    all_summaries: Dict[str, int] = {}
    total_tokens = 0

    for i, group in enumerate(or_groups):
        group_set, summary = _execute_and_group(
            group, connector, use_pqr, use_fpd, dataset
        )
        logger.info(f"[SELECT] OR group {i+1}: {len(group_set)} hit(s)  conds={group}")
        master_set |= group_set          # UNION
        all_summaries.update(summary)
        total_tokens += len(group) * 2   # field + value per condition

    logger.info(f"[SELECT] union total: {len(master_set)} unique result(s)")

    if not master_set:
        return [{
            'status':         'NO_MATCHES',
            'message':        f"No documents matched any of the {len(or_groups)} condition group(s)",
            'mode':           mode,
            'or_groups':      or_groups,
            'search_summary': all_summaries,
        }]

    # ── Build result rows ─────────────────────────────────────────────────────
    # Merge all conditions across groups for column value lookup
    all_conditions: Dict[str, str] = {}
    for group in or_groups:
        all_conditions.update(group)

    results = []
    for ref in sorted(master_set)[:max_results]:
        row: Dict[str, Any] = {}
        for col in columns:
            if col.lower() in ('document', 'filename', '*'):
                row['document'] = ref
            elif col in all_conditions:
                row[col] = all_conditions[col]
            else:
                row[col] = ref
        if 'document' not in row:
            row['document'] = ref
        results.append(row)

    logger.info(f"[SELECT] → {len(results)} result(s)")
    return results
