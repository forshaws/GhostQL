"""
ghostql/query/join.py
GhostQL JOIN executor — in-memory hash join of two result sets.

JOIN runs two independent SELECT queries (one per table) and joins the
resulting document reference sets by a shared field token.

Syntax:
  SELECT document FROM patients
    JOIN prescriptions ON nhs_number
    WHERE name='Mills'
    WITH PQR FPD

How it works:
  1. Execute the primary WHERE query → set A of document references
  2. Execute the join ON field as a token search → set B of document references
  3. Return the intersection: documents present in BOTH sets

This is a content-addressed hash join — there is no foreign key in the
traditional sense. The shared field is a token that both documents contain
in their associative memory entries.

V1.0.0 limitation: single JOIN only. Multi-table JOINs are on the roadmap.
Contributions welcome — see CONTRIBUTING.md.
"""
import logging
from typing import Dict, List, Any

from ..connectors.base import BaseConnector
from .select import execute_select

logger = logging.getLogger(__name__)


def execute_join(
    parsed: Dict[str, Any],
    connector: BaseConnector,
    dataset: str = '',
    max_results: int = 50,
) -> List[Dict[str, Any]]:
    """
    Execute a JOIN query.

    Args:
        parsed:      Output of query.parser.parse() with join != None
        connector:   Active BaseConnector instance
        dataset:     Dataset/namespace override
        max_results: Cap on returned rows

    Returns:
        List of result dicts from the intersection of both result sets.
    """
    join    = parsed['join']
    use_pqr = parsed['use_pqr']
    use_fpd = parsed['use_fpd']

    if not join:
        return [{'error': 'execute_join called without JOIN clause in parsed query'}]

    join_field = join['on']
    join_table = join['table']

    logger.info(f"[JOIN] primary={parsed['table']}  join={join_table}  on={join_field}")

    # ── Step 1: primary SELECT ────────────────────────────────────────────────
    primary_results = execute_select(parsed, connector, dataset, max_results)

    if not primary_results or primary_results[0].get('status') == 'NO_MATCHES':
        logger.info("[JOIN] primary query returned no results")
        return primary_results

    primary_refs = {r.get('document', '') for r in primary_results if 'document' in r}

    # ── Step 2: JOIN field token search ──────────────────────────────────────
    # Treat the ON field itself as a WHERE token against the join table
    join_parsed = {
        **parsed,
        'table':      join_table,
        'conditions': {join_field: join_field},   # search for the field name as token
        'join':       None,
    }
    join_results = execute_select(join_parsed, connector, dataset, max_results * 10)

    if not join_results or join_results[0].get('status') == 'NO_MATCHES':
        logger.info("[JOIN] join-side query returned no results")
        return [{
            'status':  'NO_MATCHES',
            'message': f"JOIN on '{join_field}' returned no results from '{join_table}'",
        }]

    join_refs = {r.get('document', '') for r in join_results if 'document' in r}

    # ── Step 3: Intersect ────────────────────────────────────────────────────
    matched = primary_refs & join_refs
    logger.info(
        f"[JOIN] primary={len(primary_refs)}  join={len(join_refs)}  ∩={len(matched)}"
    )

    if not matched:
        return [{
            'status':  'NO_MATCHES',
            'message': f"No documents matched both sides of JOIN ON '{join_field}'",
            'primary_hits': len(primary_refs),
            'join_hits':    len(join_refs),
        }]

    return [
        {'document': ref, 'join': join_table, 'on': join_field}
        for ref in sorted(matched)[:max_results]
    ]
