"""
ghostql/query/tokeniser.py
General-purpose tokeniser for GhostQL LIKE (similarity) queries.

Strips stopwords, deduplicates, enforces minimum token length.
Case is PRESERVED — PQR self-salting scheme is case-sensitive.
Stopword matching is case-insensitive.

Add domain-specific stopwords to STOPWORDS as needed.
"""

STOPWORDS = frozenset([
    # Generic English
    "this", "that", "with", "from", "they", "them", "their", "what",
    "will", "have", "been", "were", "when", "where", "which", "there",
    "some", "more", "also", "than", "then", "into", "your", "about",
    "would", "could", "should", "each", "other", "these", "those",
    # Common document/data words
    "data", "file", "document", "record", "report", "system", "user",
    "type", "date", "time", "name", "list", "item", "value", "field",
    # Medical domain (retained for Lindisfarne M1 compatibility)
    "disease", "disorder", "syndrome", "acute", "chronic", "familial",
    "stage", "and", "the", "due", "related", "associated", "secondary",
    "primary", "left", "right", "bilateral", "unilateral", "severe",
    "mild", "moderate", "late", "early", "onset",
])

MIN_TOKEN_LENGTH = 4


def tokenise(text: str) -> list[str]:
    """
    Tokenise free text into meaningful search tokens.

    - Splits on non-alpha characters
    - Filters stopwords (case-insensitive)
    - Deduplicates while preserving order
    - Enforces MIN_TOKEN_LENGTH
    - Preserves original case for PQR hashing

    Args:
        text: Any free text — query, sentence, paragraph, keyword list

    Returns:
        List of unique, meaningful tokens in original case
    """
    import re
    words = re.findall(r'[a-zA-Z]+', text)
    seen:   set[str] = set()
    tokens: list[str] = []
    for word in words:
        if (
            len(word) >= MIN_TOKEN_LENGTH
            and word.lower() not in STOPWORDS
            and word not in seen
        ):
            seen.add(word)
            tokens.append(word)
    return tokens
