"""
ghostql/query/parser.py
GhostQL query language parser.

Supported syntax:

  SELECT <cols> FROM <table>
    WHERE <field>='<value>' [AND <field>='<value>' ...] [OR <field>='<value>' ...]
    [JOIN <table2> ON <field>]
    [WITH PQR [FPD]]

  SELECT <cols> FROM <table>
    WHERE <field> LIKE '<text>'
    [WITH PQR [FPD]]

Flags (WITH clause):
  PQR     — Apply self-salting PQR hashing to each token before searching.
             Required when the dataset was ingested with PQR enabled.
  FPD     — False Positive Defence. Requires PQR. Each token is searched
             forward AND reversed; only documents in BOTH sets are returned.
             FPD without PQR is silently ignored.

Query types:
  SELECT … WHERE field='value'                    → exact match
  SELECT … WHERE field='v1' AND field2='v2'       → AND intersection
  SELECT … WHERE field='v1' OR field='v2'         → OR union
  SELECT … WHERE f1='v1' AND f2='v2' OR f3='v3'  → mixed (AND binds tighter)
  SELECT … WHERE field LIKE '…'                   → similarity search
  SELECT … JOIN table2 ON field                   → in-memory hash join

Operator precedence (matches MySQL standard):
  AND binds tighter than OR.
  WHERE name='Mills' AND dlbl='Retinal' OR dlbl='Diabetes'
  = (name='Mills' AND dlbl='Retinal') OR (dlbl='Diabetes')

Examples:
  SELECT document FROM records WHERE name='Mills' WITH PQR FPD
  SELECT document FROM records WHERE name='Mills' OR name='Chen' WITH PQR FPD
  SELECT document FROM records WHERE name='Mills' AND dlbl='Retinal' OR dlbl='Diabetes' WITH PQR FPD
  SELECT document FROM records WHERE name LIKE 'John Mills pharmacist' WITH PQR FPD
  SELECT document FROM patients JOIN clinical ON nhs WHERE name='Mills' WITH PQR FPD
"""
import re
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


class ParseError(ValueError):
    """Raised when a GhostQL query cannot be parsed."""
    pass


def _parse_conditions(where_body: str) -> List[Dict[str, str]]:
    """
    Parse a WHERE body into a list of OR groups, each group being
    a dict of AND conditions.

    Operator precedence: AND binds tighter than OR (MySQL standard).

    'name=Mills AND dlbl=Retinal OR dlbl=Diabetes'
    → [
        {'name': 'Mills', 'dlbl': 'Retinal'},   # AND group 1
        {'dlbl': 'Diabetes'},                    # AND group 2
      ]

    Returns list of condition dicts — one dict per OR group.
    """
    or_groups = []

    # Split on OR first (lower precedence)
    or_parts = re.split(r'\s+OR\s+', where_body, flags=re.IGNORECASE)

    for or_part in or_parts:
        group: Dict[str, str] = {}
        # Split each OR group on AND (higher precedence)
        and_parts = re.split(r'\s+AND\s+', or_part.strip(), flags=re.IGNORECASE)
        for part in and_parts:
            kv = re.match(r'(\w+)\s*=\s*[\'"]?([^\'"]+)[\'"]?', part.strip())
            if kv:
                group[kv.group(1).strip()] = kv.group(2).strip()
        if group:
            or_groups.append(group)

    return or_groups


def parse(query: str) -> Dict[str, Any]:
    """
    Parse a GhostQL query string into a structured dict.

    Returns:
        {
          'raw':        str,              # original query
          'columns':    list[str],        # requested columns
          'table':      str,              # primary table/namespace
          'or_groups':  list[dict],       # list of AND condition groups (OR between groups)
          'conditions': dict,             # first AND group (backward compat)
          'like':       dict | None,      # {'field': str, 'text': str} for LIKE
          'join':       dict | None,      # {'table': str, 'on': str} for JOIN
          'use_pqr':    bool,
          'use_fpd':    bool,
          'mode':       str,              # 'plain' | 'PQR' | 'PQR+FPD'
        }
    """
    original = query.strip()
    logger.debug(f"[PARSER] {original}")

    # ── Strip WITH flags ────────────────────────────────────────────────────
    use_pqr = use_fpd = False
    with_m = re.search(r'\bWITH\s+([\w\s]+)$', original, re.IGNORECASE)
    if with_m:
        flags   = with_m.group(1).upper().split()
        use_pqr = 'PQR' in flags
        use_fpd = 'FPD' in flags and use_pqr
        query   = original[:with_m.start()].strip()
    else:
        query = original

    # ── SELECT cols ─────────────────────────────────────────────────────────
    col_m = re.search(r'SELECT\s+(.+?)\s+FROM', query, re.IGNORECASE)
    if not col_m:
        raise ParseError("Missing SELECT … FROM clause")
    columns = [c.strip() for c in col_m.group(1).split(',')]

    # ── FROM table ──────────────────────────────────────────────────────────
    from_m = re.search(r'FROM\s+(\w+)', query, re.IGNORECASE)
    if not from_m:
        raise ParseError("Missing FROM clause")
    table = from_m.group(1)

    # ── JOIN ────────────────────────────────────────────────────────────────
    join = None
    join_m = re.search(r'JOIN\s+(\w+)\s+ON\s+(\w+)', query, re.IGNORECASE)
    if join_m:
        join  = {'table': join_m.group(1), 'on': join_m.group(2)}
        # Remove JOIN clause but preserve WHERE
        query = (query[:join_m.start()] + ' ' + query[join_m.end():]).strip()

    # ── WHERE ───────────────────────────────────────────────────────────────
    or_groups: List[Dict[str, str]] = []
    like: Dict[str, str] | None = None

    where_m = re.search(r'WHERE\s+(.+)$', query, re.IGNORECASE)
    if where_m:
        where_body = where_m.group(1).strip()

        # LIKE clause: field LIKE 'text'
        like_m = re.search(
            r'(\w+)\s+LIKE\s+[\'"]([^\'"]+)[\'"]',
            where_body,
            re.IGNORECASE
        )
        if like_m:
            like = {'field': like_m.group(1), 'text': like_m.group(2)}
        else:
            or_groups = _parse_conditions(where_body)

    # Backward compat — first AND group as 'conditions'
    conditions = or_groups[0] if or_groups else {}

    mode = 'PQR+FPD' if use_fpd else ('PQR' if use_pqr else 'plain')
    logger.debug(
        f"[PARSER] mode={mode}  table={table}  cols={columns}  "
        f"or_groups={or_groups}  like={like}  join={join}"
    )

    return {
        'raw':        original,
        'columns':    columns,
        'table':      table,
        'or_groups':  or_groups,
        'conditions': conditions,   # backward compat
        'like':       like,
        'join':       join,
        'use_pqr':    use_pqr,
        'use_fpd':    use_fpd,
        'mode':       mode,
    }
