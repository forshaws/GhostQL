# GhostQL Query Language Reference — v1.1.0

GhostQL speaks a familiar SQL-like dialect designed for unstructured, schema-free associative memory. There are no tables to create, no columns to define, no migrations to run. Tables appear when you query them. Gone when you don't.

---

## Syntax overview

```
SELECT <columns>
FROM   <table>
[JOIN  <table2> ON <field>]
WHERE  <condition> [AND <condition> ...] [OR <condition> ...]
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
-- Four token searches, ANDed together — pinpoints a single record
WHERE name='Mills' AND nhs='4855805912'
```

---

## WHERE — OR

```sql
WHERE field='value' OR field='value2'
```

OR returns the **union** of both result sets — documents matching either condition.

```sql
-- Find all Mills OR all Chen patients
WHERE name='Mills' OR name='Chen'

-- Find records with diabetes OR patients on Metformin
WHERE dlbl='Diabetes' OR mlbl='Metformin'
```

---

## WHERE — Mixed AND/OR

AND and OR can be combined. **AND binds tighter than OR** — matching MySQL standard precedence.

```sql
WHERE name='Mills' AND dlbl='Retinal' OR dlbl='Diabetes'
```

Evaluates as:

```
(name='Mills' AND dlbl='Retinal') OR (dlbl='Diabetes')
```

Returns: all Mills patients with Retinal diagnosis, PLUS all Diabetes patients.

```sql
-- Two independent AND groups, unioned together
WHERE name='Mills' AND dlbl='Retinal' OR name='Chen' AND dlbl='Diabetes'
```

Evaluates as:

```
(name='Mills' AND dlbl='Retinal') OR (name='Chen' AND dlbl='Diabetes')
```

---

## WHERE — LIKE (similarity search)

```sql
WHERE field LIKE 'free text query'
```

The `LIKE` operator tokenises the free text, searches for each token, and scores documents by how many tokens they match. Results are ranked by overlap percentage.

```sql
SELECT document FROM records
  WHERE dlbl LIKE 'Retinal detachment'
  WITH PQR FPD
```

The similarity threshold (default 30%) is set in `ghostql.conf`:
```ini
[query]
similarity_threshold = 0.3
```

Result rows include `overlap_pct` — the percentage of query tokens matched.

**Important:** `LIKE` returns the top N results by score, not all matches. Use exact `=` when you need guaranteed complete results. Use `LIKE` for discovery and relevance-ranked search.

---

## JOIN

```sql
SELECT document FROM patients
  JOIN clinical ON nhs
  WHERE name='Mills'
  WITH PQR FPD
```

JOIN runs two independent result sets and returns documents from the join-side dataset whose shared field value (`nhs`) links them to records in the primary result set.

How it works:
1. Execute the primary WHERE query against `patients` → get matching patient refs
2. Extract the `nhs` field value from each matched patient record
3. Search `clinical` for each NHS number
4. Return matching clinical records

V1.1.0 supports single JOIN only. Multi-table JOIN is on the roadmap.

**Note:** JOIN requires the source JSONL file to be accessible locally for field value extraction. It works with the local connector out of the box. DMM-backed JOIN support requires `tqnn_get` retrieval — on the roadmap.

---

## WITH flags

Flags appear at the end of any query:

| Flag | Effect |
|------|--------|
| `PQR` | Apply self-salting SHA-256 hashing to every token before searching. Required when the dataset was ingested with PQR enabled. |
| `FPD` | False Positive Defence. Each token is searched twice (forward hash + reversed-input hash). Only documents in **both** result sets are genuine. Requires `PQR`. |

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

## Result format

Results are returned as a JSON array of objects:

```json
[
  { "document": "records_0001.jsonl::line19::REC-00010019::fpd_518837c0" },
  { "document": "records_0001.jsonl::line44::REC-00010044::fpd_3a7bc112" }
]
```

Each `document` value is a filereference — a pointer to the source record. Your application uses these to fetch the actual content from the source file, API, or storage system. GhostQL finds the references; your app fetches the content.

LIKE results include scoring:
```json
[
  { "document": "...", "token_hits": 2, "overlap_pct": 100.0 },
  { "document": "...", "token_hits": 1, "overlap_pct": 50.0 }
]
```

No-match responses:
```json
[{
  "status": "NO_MATCHES",
  "message": "No documents matched any of the 2 condition group(s)",
  "mode": "PQR+FPD",
  "or_groups": [{"name": "Mills"}, {"name": "Chen"}],
  "search_summary": { "name": 0, "Mills": 50, "Chen": 32 }
}]
```

---

## Commands (interactive / TCP session)

| Command | Action |
|---------|--------|
| `help` / `?` | Show syntax reference |
| `ping` | Test connector health |
| `quit` / `exit` | Close connection |

---

## Complete examples

```sql
-- Exact match
SELECT document FROM records WHERE name='Mills' WITH PQR FPD

-- Pinpoint a single record
SELECT document FROM records WHERE name='Mills' AND nhs='4855805912' WITH PQR FPD

-- OR union
SELECT document FROM records WHERE name='Mills' OR name='Chen' WITH PQR FPD

-- OR across different fields
SELECT document FROM records WHERE dlbl='Diabetes' OR mlbl='Metformin' WITH PQR FPD

-- Mixed AND/OR (AND binds tighter)
SELECT document FROM records WHERE name='Mills' AND dlbl='Retinal' OR dlbl='Diabetes' WITH PQR FPD

-- LIKE similarity search
SELECT document FROM records WHERE dlbl LIKE 'Retinal detachment' WITH PQR FPD

-- JOIN across two datasets
SELECT document FROM patients JOIN clinical ON nhs WHERE name='Mills' WITH PQR FPD
```

---

## Operator precedence summary

| Operator | Precedence | Behaviour |
|----------|-----------|-----------|
| `AND` | High | Intersects result sets — all conditions must match |
| `OR` | Low | Unions result sets — either condition can match |
| `LIKE` | n/a | Similarity scoring — ranked by token overlap |

AND always evaluates before OR. Use parentheses support (roadmap) to override.
