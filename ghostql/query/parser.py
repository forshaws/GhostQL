"""
ghostql/query/parser.py
GhostQL query language parser.

Supported syntax:

  SELECT <cols> FROM <table>
    WHERE <field>='<value>' [AND <field>='<value>' ...]
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
  SELECT … WHERE field='value'   → exact match (one searchDoc per token)
  SELECT … WHERE field LIKE '…'  → similarity search (multi-token overlap)
  SELECT … JOIN table2 ON field  → in-memory hash join of two result sets

Examples:
  SELECT document FROM records WHERE name='Mills' WITH PQR FPD
  SELECT document FROM records WHERE name LIKE 'John Mills pharmacist' WITH PQR FPD
  SELECT document FROM patients JOIN prescriptions ON nhs_number WITH PQR FPD
  SELECT document, nhs FROM records WHERE nhs='4855805912' AND name='Chen' WITH PQR
"""
import re
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class ParseError(ValueError):
    """Raised when a GhostQL query cannot be parsed."""
    pass


def parse(query: str) -> Dict[str, Any]:
    """
    Parse a GhostQL query string into a structured dict.

    Returns:
        {
          'raw':         str,            # original query
          'columns':     list[str],      # requested columns
          'table':       str,            # primary table/namespace
          'conditions':  dict,           # field → value for WHERE =
          'like':        dict | None,    # {'field': str, 'text': str} for LIKE
          'join':        dict | None,    # {'table': str, 'on': str} for JOIN
          'use_pqr':     bool,
          'use_fpd':     bool,
          'mode':        str,            # 'plain' | 'PQR' | 'PQR+FPD'
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
        query = query[:join_m.start()].strip()   # remove from further parsing

    # ── WHERE ───────────────────────────────────────────────────────────────
    conditions: Dict[str, str] = {}
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
            # Standard AND-joined equality conditions
            for part in re.split(r'\s+AND\s+', where_body, flags=re.IGNORECASE):
                kv = re.match(r'(\w+)\s*=\s*[\'"]?([^\'"]+)[\'"]?', part.strip())
                if kv:
                    conditions[kv.group(1).strip()] = kv.group(2).strip()

    mode = 'PQR+FPD' if use_fpd else ('PQR' if use_pqr else 'plain')
    logger.debug(
        f"[PARSER] mode={mode}  table={table}  cols={columns}  "
        f"conds={conditions}  like={like}  join={join}"
    )

    return {
        'raw':        original,
        'columns':    columns,
        'table':      table,
        'conditions': conditions,
        'like':       like,
        'join':       join,
        'use_pqr':    use_pqr,
        'use_fpd':    use_fpd,
        'mode':       mode,
    }
