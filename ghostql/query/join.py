"""
ghostql/query/join.py
GhostQL JOIN executor — cross-dataset join via shared field token.

Syntax:
  SELECT document FROM patients JOIN clinical ON nhs
    WHERE name='Mills' WITH PQR FPD

How it works:
  1. Execute the primary WHERE query against the primary table
     → get a set of matching patient filereferences
  2. From those filereferences, extract the shared field value
     by searching the source JSONL file for the ON field
  3. Search the join table for each extracted value
  4. Return matching filereferences from the join table

This is a genuine cross-dataset join — the ON field is a real
shared value (e.g. NHS number) that links records across two
separate datasets indexed into the same unified index.

V1.0.0: single JOIN only. Multi-table JOIN on the roadmap.
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Any

from ..connectors.base import BaseConnector
from .select import execute_select
from .pqr import pqr_hash, pqr_hash_reversed

logger = logging.getLogger(__name__)


def _load_source_records(source_file: str) -> List[dict]:
    """
    Load records from the source JSONL file referenced in a filereference.
    Searches for the file relative to cwd and common demo paths.
    """
    candidates = [
        Path(source_file),
        Path('demo') / source_file,
        Path(__file__).parent.parent.parent / 'demo' / source_file,
    ]
    for path in candidates:
        if path.exists():
            with open(path) as f:
                return [json.loads(line) for line in f if line.strip()]
    return []


def _get_field_value(fileref: str, field: str, source_records: List[dict]) -> str | None:
    """
    Extract the value of `field` from the record identified by `fileref`.
    Matches by line number embedded in the filereference.
    e.g. patients.jsonl::line406::REC-00000406::fpd_401bd774::
    """
    import re
    m = re.search(r'::line(\d+)::', fileref)
    if not m:
        return None
    line_num = int(m.group(1))
    if 1 <= line_num <= len(source_records):
        return str(source_records[line_num - 1].get(field, '')).strip()
    return None


def execute_join(
    parsed: Dict[str, Any],
    connector: BaseConnector,
    dataset: str = '',
    max_results: int = 50,
) -> List[Dict[str, Any]]:
    """
    Execute a JOIN query across two datasets.

    Args:
        parsed:      Output of query.parser.parse() with join != None
        connector:   Active BaseConnector instance
        dataset:     Dataset/namespace override
        max_results: Cap on returned rows

    Returns:
        List of result dicts from the join-side dataset.
    """
    join       = parsed['join']
    use_pqr    = parsed['use_pqr']
    use_fpd    = parsed['use_fpd']

    if not join:
        return [{'error': 'execute_join called without JOIN clause'}]

    join_field = join['on']
    join_table = join['table']
    primary_table = parsed['table']

    logger.info(f"[JOIN] {primary_table} → {join_table}  on={join_field}")

    # ── Step 1: Primary SELECT ────────────────────────────────────────────────
    primary_results = execute_select(parsed, connector, dataset, max_results * 10)

    if not primary_results or primary_results[0].get('status') == 'NO_MATCHES':
        logger.info("[JOIN] primary query returned no results")
        return primary_results

    primary_refs = [r.get('document', '') for r in primary_results if 'document' in r]
    logger.info(f"[JOIN] primary hits: {len(primary_refs)}")

    # ── Step 2: Extract shared field values from primary results ──────────────
    # Load the source JSONL to look up field values by line number
    source_file = f"{primary_table}.jsonl"
    source_records = _load_source_records(source_file)

    if not source_records:
        logger.warning(f"[JOIN] Could not load source file: {source_file}")
        return [{
            'status':  'NO_MATCHES',
            'message': f"JOIN: could not load source dataset '{primary_table}.jsonl'",
        }]

    # Extract the join field value from each primary result
    join_values = set()
    for ref in primary_refs:
        val = _get_field_value(ref, join_field, source_records)
        if val:
            join_values.add(val)

    logger.info(f"[JOIN] extracted {len(join_values)} unique '{join_field}' value(s)")

    if not join_values:
        return [{
            'status':  'NO_MATCHES',
            'message': f"JOIN: field '{join_field}' not found in '{primary_table}' records",
        }]

    # ── Step 3: Search join table for each extracted value ────────────────────
    matched: set = set()

    for value in join_values:
        fwd = connector.search(pqr_hash(value), dataset)
        fwd_refs = {r for r in fwd.fileset if join_table in r}

        if use_fpd:
            rev = connector.search(pqr_hash_reversed(value), dataset)
            rev_refs = {r for r in rev.fileset if join_table in r}
            hits = fwd_refs & rev_refs
        else:
            hits = fwd_refs

        matched |= hits
        logger.debug(f"[JOIN] '{value}' → {len(hits)} hit(s) in {join_table}")

    logger.info(f"[JOIN] → {len(matched)} matched in {join_table}")

    if not matched:
        return [{
            'status':  'NO_MATCHES',
            'message': f"No '{join_table}' records found matching '{join_field}' values from '{primary_table}'",
            'primary_hits':   len(primary_refs),
            'join_values':    len(join_values),
        }]

    return [
        {'document': ref, 'join': join_table, 'on': join_field}
        for ref in sorted(matched)[:max_results]
    ]
