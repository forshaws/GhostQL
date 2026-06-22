#!/usr/bin/env python3
"""
demo/build_demo_index.py
GhostQL Demo Dataset Builder

Generates 500 synthetic NHS-style patient records and builds a local
PQR+FPD search index that the LocalFileConnector can query without
any DMM credentials.

Usage:
  python demo/build_demo_index.py

Output:
  demo/records.jsonl      — human-readable source records
  demo/demo_index.json    — pre-built PQR+FPD search index

The demo_index.json is committed to the repo so end users can run
the demo immediately without rebuilding:

  [connector]
  type = local

Then: python -m ghostql.server
"""
import json
import hashlib
import random
from pathlib import Path

SEED         = 42
RECORD_COUNT = 500
OUTPUT_DIR   = Path(__file__).parent

# ── Synthetic data pools ──────────────────────────────────────────────────────

FORENAMES = [
    'Oliver','George','Harry','Noah','Jack','Leo','Charlie','Alfie','Theo','Arthur',
    'Oscar','Henry','Archie','Joshua','Ethan','James','William','Thomas','Max','Alexander',
    'Muhammad','Isaac','Lucas','Harrison','Edward','Jacob','Dylan','Luca','Elijah','Mason',
    'Amelia','Olivia','Isla','Ava','Mia','Isabella','Sophia','Grace','Lily','Freya',
    'Emily','Poppy','Ella','Elsie','Evelyn','Charlotte','Sienna','Daisy','Ivy','Alice',
    'Florence','Sophie','Rosie','Ruby','Aria','Scarlett','Willow','Layla','Luna','Eleanor',
    'Mohammed','Omar','Adam','Ayaan','Ibrahim','Yusuf','Amir','Hamza','Zain','Idris',
    'Ananya','Priya','Divya','Kavya','Meera','Aisha','Fatima','Zahra','Noor','Hana',
    'Chen','Li','Wang','Zhang','Liu','Yang','Huang','Zhao','Wu','Zhou',
    'Rahul','Rohan','Arjun','Kiran','Vikram','Nikhil','Amit','Sanjay','Rajesh','Deepak',
]

SURNAMES = [
    'Smith','Jones','Williams','Taylor','Brown','Davies','Evans','Wilson','Thomas','Roberts',
    'Johnson','Lewis','Walker','Robinson','Wood','Thompson','White','Watson','Jackson','Wright',
    'Green','Harris','Cooper','King','Lee','Martin','Clarke','James','Morgan','Hughes',
    'Edwards','Hill','Moore','Clark','Harrison','Scott','Young','Morris','Hall','Ward',
    'Turner','Carter','Phillips','Mitchell','Patel','Adams','Campbell','Anderson','Allen','Cook',
    'Bailey','Parker','Collins','Rogers','Bennett','Henderson','Gray','Richardson','Cox','Howard',
    'Khan','Ali','Ahmed','Hussain','Sheikh','Malik','Chaudhry','Iqbal','Mirza','Qureshi',
    'Singh','Kaur','Kumar','Sharma','Verma','Gupta','Mehta','Shah','Joshi','Nair',
    'Okafor','Mensah','Diallo','Nkosi','Kamara','Osei','Asante','Boateng','Adjei','Owusu',
    'Mills','Barnes','Wells','Grant','Spencer','Powell','Griffin','Reed','Murray','Ford',
]

DIAGNOSES = [
    ('73211009',  'Diabetes mellitus'),
    ('38341003',  'Hypertension'),
    ('44054006',  'Type 2 diabetes'),
    ('13645005',  'COPD'),
    ('22298006',  'Myocardial infarction'),
    ('230265002', 'Familial Alzheimer disease'),
    ('34000006',  "Crohn's disease"),
    ('415068001', 'Deep vein thrombosis'),
    ('9014002',   'Psoriasis'),
    ('13213009',  'Congenital heart disease'),
    ('84114007',  'Heart failure'),
    ('40275004',  'Contact dermatitis'),
    ('195967001', 'Asthma'),
    ('59621000',  'Essential hypertension'),
    ('21897009',  'Generalised anxiety disorder'),
    ('35489007',  'Depressive disorder'),
    ('69896004',  'Rheumatoid arthritis'),
]

MEDICATIONS = [
    ('372614000', 'Metformin'),
    ('372687004', 'Omeprazole'),
    ('372682005', 'Atorvastatin'),
    ('387517004', 'Warfarin'),
    ('372756006', 'Donepezil'),
    ('373225007', 'Amlodipine'),
    ('372675006', 'Amoxicillin'),
    ('387206009', 'Salbutamol'),
    ('386878004', 'Sertraline'),
    ('372664007', 'Prednisolone'),
    ('372695000', 'Furosemide'),
    ('387069000', 'Bisoprolol'),
    ('387529008', 'Ramipril'),
]

FORMATS   = ['SNOMED', 'HL7', 'FHIR', 'GHX']
GP_PRACTICES = [
    'Parkway Medical Centre','The Village Surgery','Riverside Practice',
    'Hillview Health Centre','Central Medical Group',"St Mary's Surgery",
    'Northgate Practice','Westfield Medical Centre','The Health Hub',
    'Dene Park Surgery','Castle Medical Group','Tyne Valley Practice',
]
TOWNS = [
    'Newcastle upon Tyne','Sunderland','Gateshead','Durham','Middlesbrough',
    'Hartlepool','Stockton-on-Tees','Darlington','South Shields','Tynemouth',
    'Whitley Bay','Hexham','Morpeth','Ashington','Scarborough','York',
]


# ── PQR hashing — self-salting scheme V1.3.0+ ────────────────────────────────

def pqr_hash(token: str) -> str:
    s     = str(token).strip()
    h1    = hashlib.sha256(s.encode()).hexdigest()
    mixed = (s + h1)[:16]
    return hashlib.sha256(mixed.encode()).hexdigest()[:16]

def pqr_hash_reversed(token: str) -> str:
    return pqr_hash(str(token).strip()[::-1])

def fpd_code(rec_id: str) -> str:
    return 'fpd_' + hashlib.sha256(rec_id.encode()).hexdigest()[:8]


# ── Record generation ─────────────────────────────────────────────────────────

def random_nhs(rng: random.Random) -> str:
    return ''.join(str(rng.randint(0, 9)) for _ in range(10))

def random_date(rng: random.Random, y1: int, y2: int) -> str:
    return f"{rng.randint(y1,y2)}-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}"

def random_email(rng: random.Random, forename: str, surname: str) -> str:
    domains = ['gmail.com','yahoo.co.uk','hotmail.com','outlook.com',
               'live.co.uk','sky.com','talktalk.net','btinternet.com']
    n = rng.randint(100, 9999)
    styles = [
        f"{forename.lower()}{n}@{rng.choice(domains)}",
        f"{forename[0].lower()}.{surname.lower()}@{rng.choice(domains)}",
        f"{forename.lower()}_{surname.lower()}@{rng.choice(domains)}",
    ]
    return rng.choice(styles)

def generate_record(idx: int, rng: random.Random) -> dict:
    forename = rng.choice(FORENAMES)
    surname  = rng.choice(SURNAMES)
    diag     = rng.choice(DIAGNOSES)
    med      = rng.choice(MEDICATIONS)
    return {
        'id':    f"REC-{idx:08d}",
        'name':  f"{forename} {surname}",
        'nhs':   random_nhs(rng),
        'email': random_email(rng, forename, surname),
        'dob':   random_date(rng, 1935, 2005),
        'visit': random_date(rng, 2018, 2024),
        'diag':  diag[0],
        'dlbl':  diag[1],
        'med':   med[0],
        'mlbl':  med[1],
        'gp':    rng.choice(GP_PRACTICES),
        'town':  rng.choice(TOWNS),
        'fmt':   rng.choice(FORMATS),
    }


# ── Token extraction ──────────────────────────────────────────────────────────

def extract_tokens(rec: dict) -> list[str]:
    """
    Extract all searchable tokens from a record.
    Mirrors how the original Lindisfarne ingest works:
    - Each field name is a token
    - Each field value is a token
    - Name fields are also split into individual words (forename + surname separately)
    - Multi-word string values are also split into words
    This means you can query:
      WHERE name='Mills'           (surname only)
      WHERE name='Oliver Mills'    (full name)
      WHERE dlbl='Diabetes'        (single word from label)
    """
    tokens = []
    seen   = set()

    def add(t: str):
        t = t.strip()
        if t and t not in seen:
            seen.add(t)
            tokens.append(t)

    for k, v in rec.items():
        add(k)                          # field name as token
        v = str(v).strip()
        add(v)                          # full field value as token
        # Also split multi-word values into individual word tokens
        words = v.split()
        if len(words) > 1:
            for word in words:
                add(word)

    return tokens


# ── Index builder ─────────────────────────────────────────────────────────────

def build_index(records: list[dict], source_file: str) -> dict:
    """
    Build a PQR+FPD search index.
    Each token is stored twice: forward hash + reversed-input hash.
    index: { hash_hex: [filereference, ...] }
    """
    index: dict[str, list[str]] = {}

    for i, rec in enumerate(records, 1):
        code    = fpd_code(rec['id'])
        fileref = f"{source_file}::line{i}::{rec['id']}::{code}::"

        for token in extract_tokens(rec):
            for h in (pqr_hash(token), pqr_hash_reversed(token)):
                if fileref not in index.get(h, []):
                    index.setdefault(h, []).append(fileref)

        if i % 100 == 0:
            print(f"  Indexed {i}/{len(records)} records…")

    return index


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"\nGhostQL Demo Dataset Builder")
    print(f"Generating {RECORD_COUNT} synthetic records (seed={SEED})…\n")

    rng     = random.Random(SEED)
    records = [generate_record(i, rng) for i in range(1, RECORD_COUNT + 1)]
    print(f"  Generated {len(records)} records")

    jsonl_path = OUTPUT_DIR / 'records.jsonl'
    with open(jsonl_path, 'w') as f:
        for rec in records:
            f.write(json.dumps(rec) + '\n')
    print(f"  Written: {jsonl_path}")

    print(f"\nBuilding PQR+FPD index…")
    index = build_index(records, 'records.jsonl')
    print(f"  Index entries: {len(index):,}")

    index_path = OUTPUT_DIR / 'demo_index.json'
    with open(index_path, 'w') as f:
        json.dump({
            'meta': {
                'version':       '1.0.0',
                'records':       len(records),
                'index_entries': len(index),
                'seed':          SEED,
                'source':        'records.jsonl',
                'scheme':        'PQR+FPD self-salting SHA-256 V1.3.0+',
            },
            'index': index,
        }, f, separators=(',', ':'))
    print(f"  Written: {index_path}")

    # Verification — test a few surnames
    print(f"\nVerification:")
    for rec in records[:5]:
        surname = rec['name'].split()[1]
        hits    = index.get(pqr_hash(surname), [])
        print(f"  WHERE name='{surname}' → {len(hits)} hit(s)")

    print(f"\nDemo dataset ready.")
    print(f"Set connector.type = local in ghostql.conf and start the server.\n")


if __name__ == '__main__':
    main()
