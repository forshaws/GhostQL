"""
ghostql/query/like.py
GhostQL LIKE executor — similarity / fuzzy search.

WHERE field LIKE 'free text query'

The LIKE operator tokenises the free text, searches DMM for each token,
counts per-document token hits, ranks by overlap fraction, and returns
only documents that meet the configured similarity threshold.

This is the intelligence layer — DMM itself remains a pure primitive.
Each searchDoc call sees only a single PQR-hashed token; the scoring
and ranking happen entirely here in GhostQL.

Example:
  SELECT document FROM records
    WHERE notes LIKE 'diabetes insulin pump management'
    WITH PQR FPD

  → tokens: ['diabetes', 'insulin', 'pump', 'management']
  → 4 searchDoc calls (× 2 if FPD)
  → documents scored by token overlap
  → results sorted highest-overlap-first
"""
import logging
from typing import Dict, List, Set, Any

from ..connectors.base import BaseConnector
from .pqr import pqr_hash, pqr_hash_reversed
from .tokeniser import tokenise

logger = logging.getLogger(__name__)


def _search_token_set(
    connector: BaseConnector,
    token: str,
    use_pqr: bool,
    use_fpd: bool,
    dataset: str,
) -> Set[str]:
    if not use_pqr:
        return connector.search(token, dataset).fileset

    fwd = connector.search(pqr_hash(token), dataset).fileset
    if not use_fpd:
        return fwd

    rev = connector.search(pqr_hash_reversed(token), dataset).fileset
    intersection = fwd & rev
    logger.debug(f"[FPD] '{token}'  fwd={len(fwd)}  rev={len(rev)}  ∩={len(intersection)}")
    return intersection


def execute_like(
    parsed: Dict[str, Any],
    connector: BaseConnector,
    dataset: str = '',
    threshold: float = 0.4,
    max_results: int = 20,
) -> List[Dict[str, Any]]:
    """
    Execute a LIKE similarity query.

    Args:
        parsed:      Output of query.parser.parse() with like != None
        connector:   Active BaseConnector instance
        dataset:     Dataset/namespace override
        threshold:   Minimum token overlap fraction (0.0 – 1.0)
        max_results: Maximum results to return

    Returns:
        List of result dicts sorted by overlap_pct descending.
        Each dict: {'document': str, 'token_hits': int, 'overlap_pct': float}
    """
    like    = parsed['like']
    use_pqr = parsed['use_pqr']
    use_fpd = parsed['use_fpd']
    mode    = parsed['mode']

    if not like:
        return [{'error': 'execute_like called without LIKE clause in parsed query'}]

    text   = like['text']
    tokens = tokenise(text)

    if not tokens:
        return [{
            'status':  'NO_TOKENS',
            'message': 'No searchable tokens found in LIKE text',
            'text':    text,
        }]

    logger.info(f"[LIKE] mode={mode}  tokens={tokens}  threshold={threshold}")

    hit_counts: Dict[str, int] = {}
    searched = 0

    for token in tokens:
        try:
            refs = _search_token_set(connector, token, use_pqr, use_fpd, dataset)
        except Exception as e:
            logger.warning(f"[LIKE] token '{token}' failed: {e}")
            continue

        searched += 1
        seen_this_token: Set[str] = set()
        for ref in refs:
            if ref not in seen_this_token:
                seen_this_token.add(ref)
                hit_counts[ref] = hit_counts.get(ref, 0) + 1

    if searched == 0:
        return [{'status': 'NO_MATCHES', 'message': 'All token searches failed', 'mode': mode}]

    cutoff = searched * threshold
    matched = [
        {
            'document':    ref,
            'token_hits':  hits,
            'overlap_pct': round((hits / searched) * 100, 1),
        }
        for ref, hits in hit_counts.items()
        if hits >= cutoff
    ]
    matched.sort(key=lambda r: r['token_hits'], reverse=True)
    matched = matched[:max_results]

    logger.info(f"[LIKE] → {len(matched)} result(s) above {threshold*100:.0f}% threshold")

    if not matched:
        return [{
            'status':         'NO_MATCHES',
            'message':        f"No documents met the {threshold*100:.0f}% similarity threshold",
            'mode':           mode,
            'tokens_used':    tokens,
            'tokens_searched': searched,
        }]

    return matched
