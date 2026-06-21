# GhostQL Query Language Reference — v1.0.0

GhostQL speaks a familiar SQL-like dialect designed for unstructured, schema-free associative memory. There are no tables to create, no columns to define, no migrations to run. Tables appear when you query them. Gone when you don't.

---

## Syntax overview

```
SELECT <columns>
FROM   <table>
[JOIN  <table2> ON <field>]
WHERE  <condition>
[WITH  <flags>]
```

---

## SELECT

```sql
SELECT document FROM records WHERE name='Mills' WITH PQR FPD
SELECT document, nhs FROM records WHERE nhs='4855805912' WITH PQR FPD
SELECT * FROM records WHERE name='Mills' WITH PQR FPD
```

`document`, `filename`, and `*` all return the full document reference URI.
Additional named columns return the literal value from the WHERE clause if present,
or the document reference otherwise.

---

## WHERE — equality

```sql
WHERE field='value'
WHERE field='value' AND field2='value2'
```

Each field name and value is treated as a search token. All tokens are searched independently and the result sets are ANDed — only documents matching **all** tokens are returned.

```sql
-- Four token searches, ANDed together
WHERE name='Mills' AND nhs='4855805912'
-- tokens: ['name', 'Mills', 'nhs', '4855805912']
```

---

## WHERE — LIKE (similarity search)

```sql
WHERE field LIKE 'free text query'
```

The `LIKE` operator tokenises the free text, searches for each token, and scores documents by how many tokens they match. Results are ranked by overlap percentage.

```sql
SELECT document FROM records
  WHERE notes LIKE 'Mills diabetes insulin pump annual review'
  WITH PQR FPD
```

The similarity threshold (default 40%) is set in `ghostql.conf`:
```ini
[query]
similarity_threshold = 0.4
```

Result rows include `overlap_pct` — the percentage of query tokens matched.

---

## JOIN

```sql
SELECT document FROM patients
  JOIN prescriptions ON nhs_number
  WHERE name='Mills'
  WITH PQR FPD
```

JOIN runs two independent result sets and returns the intersection — documents present in **both** the primary query results and the join-side token search. This is a content-addressed hash join: the ON field is a token that both document sets must contain.

V1.0.0 supports single JOIN only. Multi-table JOIN is on the roadmap.

---

## WITH flags

Flags appear at the end of any query:

| Flag      | Effect |
|-----------|--------|
| `PQR`     | Apply self-salting SHA-256 hashing to every token before searching. Required when the dataset was ingested with PQR enabled. |
| `FPD`     | False Positive Defence. Each token is searched twice (forward hash + reversed-input hash). Only documents in **both** result sets are genuine. Requires `PQR`. |

```sql
-- Plain text search (dataset must be plain-ingested)
SELECT document FROM records WHERE name='Mills'

-- PQR only (hashed tokens, single search per token)
SELECT document FROM records WHERE name='Mills' WITH PQR

-- PQR + FPD (full false-positive defence — recommended for production)
SELECT document FROM records WHERE name='Mills' WITH PQR FPD
```

`FPD` without `PQR` is silently ignored.

---

## PQR hashing — self-salting scheme (V1.3.0+)

When `WITH PQR` is active, every token is hashed before being sent to the connector:

```
h1     = SHA-256(token)
mixed  = token + h1          ← salt is endogenous (derived from input)
padded = mixed[:16]          ← first 16 characters
result = SHA-256(padded)[:16] ← final 16-char hex token
```

FPD additionally searches the reversed-input hash:
```
reversed_result = pqr_hash(token[::-1])   ← INPUT reversed, not hash
```

Datasets ingested with the old constant-`*` padding scheme (V1.0.x) are incompatible and require re-ingest.

---

## Commands (interactive / TCP session)

| Command   | Action |
|-----------|--------|
| `help` / `?` | Show syntax reference |
| `ping`    | Test connector health |
| `quit` / `exit` | Close connection |

---

## Result format

Results are returned as a JSON array of objects:

```json
[
  { "document": "https://example.com/records/doc.json::line1::REC-001::fpd_abc" },
  { "document": "https://example.com/records/doc.json::line2::REC-002::fpd_xyz" }
]
```

LIKE results include scoring:
```json
[
  { "document": "...", "token_hits": 4, "overlap_pct": 80.0 },
  { "document": "...", "token_hits": 3, "overlap_pct": 60.0 }
]
```

No-match responses:
```json
[{
  "status": "NO_MATCHES",
  "message": "No documents matched all 4 token(s)",
  "mode": "PQR+FPD",
  "tokens": ["name", "Mills", "nhs", "4855805912"],
  "search_summary": { "name": 12, "Mills": 8, "nhs": 5, "4855805912": 0 }
}]
```
