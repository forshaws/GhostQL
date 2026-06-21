"""
ghostql/query/pqr.py
Post-Quantum Resistant (PQR) hashing for GhostQL.

Self-Salting scheme V1.3.0+ — matches TQNN DMM storeDoc.php exactly.

Algorithm:
  1. h1     = SHA-256(input)          → 64 hex chars (endogenous salt)
  2. mixed  = input + h1              → salt appended to raw input
  3. padded = mixed[:16]              → first 16 chars
  4. token  = SHA-256(padded)[:16]    → final 16-char hex token

Properties:
  - Defeats rainbow tables (salt derived from input itself)
  - All inputs lifted into full 2^256 hash space
  - No external key material, zero storage overhead
  - Fully deterministic — same input always produces same token
  - Case-sensitive — 'Mills' ≠ 'mills'

FPD (False Positive Defence):
  Each token is stored AND searched twice:
    forward:  pqr_hash(token)
    reversed: pqr_hash(token[::-1])   ← INPUT string reversed, not hash
  Only documents present in BOTH result sets are genuine matches.

Note: Datasets ingested with V1.0.x (constant '*' padding) are incompatible
with this scheme. Re-ingest is required after upgrading to self-salting PQR.
"""
import hashlib


def pqr_hash(token: str) -> str:
    """
    Forward self-salting PQR hash.
    Returns a 16-char hex token.
    """
    s    = str(token).strip()
    h1   = hashlib.sha256(s.encode('utf-8')).hexdigest()
    mixed = (s + h1)[:16]
    return hashlib.sha256(mixed.encode('utf-8')).hexdigest()[:16]


def pqr_hash_reversed(token: str) -> str:
    """
    Reversed-input self-salting PQR hash (for FPD).
    The INPUT string is reversed before hashing — NOT the hash output.
    """
    return pqr_hash(str(token).strip()[::-1])
