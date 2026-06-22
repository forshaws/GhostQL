# GhostQL Demo Dataset

500 synthetic NHS-style patient records, pre-indexed with PQR+FPD,
ready to query with zero credentials.

## Files

| File | Description |
|------|-------------|
| `records.jsonl` | Human-readable source records (500 lines) |
| `demo_index.json` | Pre-built PQR+FPD search index (committed to repo) |
| `build_demo_index.py` | Rebuilds both files from scratch |

## Record format

```json
{
  "id":    "REC-00000001",
  "name":  "Oliver Smith",
  "nhs":   "9605828065",
  "email": "oliver123@gmail.com",
  "dob":   "1969-02-24",
  "visit": "2021-11-07",
  "diag":  "73211009",
  "dlbl":  "Diabetes mellitus",
  "med":   "372614000",
  "mlbl":  "Metformin",
  "gp":    "Parkway Medical Centre",
  "town":  "Newcastle upon Tyne",
  "fmt":   "HL7"
}
```

## Quick start

1. Set the connector in `ghostql.conf`:

```ini
[connector]
type = local
```

2. Start the server:

```bash
python -m ghostql.server
```

3. Run example queries:

```bash
python examples/query_ghostql.py
# or
php examples/query_ghostql.php
```

## Example queries

```sql
-- Find all patients named Mills
SELECT document FROM records WHERE name='Mills' WITH PQR FPD

-- Narrow to a specific patient by NHS number
SELECT document FROM records WHERE name='Mills' AND nhs='4855805912' WITH PQR FPD

-- Find patients with diabetes
SELECT document FROM records WHERE dlbl='Diabetes' WITH PQR FPD

-- Similarity search across diagnosis labels
SELECT document FROM records WHERE dlbl LIKE 'heart failure cardiac' WITH PQR FPD

-- Find patients at a specific practice
SELECT document FROM records WHERE gp='Parkway' WITH PQR FPD
```

## Rebuilding the index

The `demo_index.json` is committed so users don't need to rebuild.
If you want to regenerate (e.g. after changing SEED or RECORD_COUNT):

```bash
python demo/build_demo_index.py
```

This is deterministic — same seed always produces identical records and index.

## Moving to DMM

When you're ready to query millions of real records against Toridion DMM,
change one line in `ghostql.conf`:

```ini
[connector]
type = dmm
```

Everything else — your queries, your clients, your code — stays identical.
That's the point.
