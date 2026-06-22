"""
ghostql/query/__init__.py
Query dispatcher — routes parsed queries to the correct executor module.

Executors:
  select.py — WHERE equality (exact token intersection)
  like.py   — WHERE field LIKE 'text' (similarity / fuzzy)
  join.py   — JOIN two result sets ON a shared field token

Adding a new query type:
  1. Create ghostql/query/your_type.py with an execute_* function
  2. Add a routing condition in dispatch() below
  3. Document the syntax in query/parser.py and docs/query-language.md
"""
import logging
from typing import Dict, List, Any

from ..connectors.base import BaseConnector
from ..core.config import GhostQLConfig
from .parser import parse, ParseError
from .select import execute_select
from .like import execute_like
from .join import execute_join

logger = logging.getLogger(__name__)


def dispatch(
    query: str,
    connector: BaseConnector,
    config: GhostQLConfig,
) -> List[Dict[str, Any]]:
    """
    Parse a GhostQL query string and dispatch to the appropriate executor.

    Args:
        query:     Raw GhostQL query string from the client
        connector: Active BaseConnector instance
        config:    GhostQLConfig (for threshold, max_results, etc.)

    Returns:
        List of result dicts

    Raises:
        ParseError if the query cannot be parsed
    """
    parsed = parse(query)

    dataset = config.dmm_dataset   # connectors may override per-call

    if parsed['join']:
        logger.info(f"[DISPATCH] JOIN  table={parsed['table']}  join={parsed['join']}")
        return execute_join(parsed, connector, dataset, config.max_results)

    if parsed['like']:
        logger.info(f"[DISPATCH] LIKE  text={parsed['like']['text'][:60]}")
        return execute_like(
            parsed, connector, dataset,
            threshold=config.similarity_threshold,
            max_results=config.max_results,
        )

    logger.info(f"[DISPATCH] SELECT  conds={parsed['conditions']}")
    return execute_select(parsed, connector, dataset, config.max_results)
