#!/usr/bin/env python3
"""
demo/build_demo_index.py
GhostQL Demo Dataset Builder

Generates 500 synthetic NHS-style patient records, splits them into two
logical datasets (patients + clinical), and builds a unified PQR+FPD
search index that supports cross-dataset JOIN queries.

Usage:
  python demo/build_demo_index.py

Output:
  demo/patients.jsonl     — patient demographics (name, nhs, dob, gp, town)
  demo/clinical.jsonl     — clinical records (nhs, diagnosis, medication, visit)
  demo/demo_index.json    — unified PQR+FPD search index

JOIN example:
  SELECT document FROM patients JOIN clinical ON nhs
    WHERE name='Mills' WITH PQR FPD

  → finds patients named Mills, then finds their clinical records
    by intersecting on the shared NHS number token.
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


# ── PQR hashing ───────────────────────────────────────────────────────────────

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


# ── Dataset split ─────────────────────────────────────────────────────────────

def to_patient(rec: dict) -> dict:
    """Demographic view — who the patient is."""
    return {
        'id':    rec['id'],
        'name':  rec['name'],
        'nhs':   rec['nhs'],
        'email': rec['email'],
        'dob':   rec['dob'],
        'gp':    rec['gp'],
        'town':  rec['town'],
    }

def to_clinical(rec: dict) -> dict:
    """Clinical view — what happened at the visit."""
    return {
        'id':    rec['id'],
        'nhs':   rec['nhs'],
        'visit': rec['visit'],
        'diag':  rec['diag'],
        'dlbl':  rec['dlbl'],
        'med':   rec['med'],
        'mlbl':  rec['mlbl'],
        'fmt':   rec['fmt'],
    }


# ── Token extraction ──────────────────────────────────────────────────────────

def extract_tokens(rec: dict) -> list:
    import re
    tokens = []
    seen   = set()

    def add(t: str):
        t = t.strip()
        if t and t not in seen:
            seen.add(t)
            tokens.append(t)

    for k, v in rec.items():
        add(k)
        v = str(v).strip()
        add(v)
        for word in re.findall(r'[a-zA-Z0-9]+', v):
            add(word)

    return tokens


# ── Index builder ─────────────────────────────────────────────────────────────

def index_dataset(records: list, source_file: str, index: dict):
    """Add a dataset's records to the shared index."""
    for i, rec in enumerate(records, 1):
        code    = fpd_code(rec['id'])
        fileref = f"{source_file}::line{i}::{rec['id']}::{code}::"

        for token in extract_tokens(rec):
            for h in (pqr_hash(token), pqr_hash_reversed(token)):
                if fileref not in index.get(h, []):
                    index.setdefault(h, []).append(fileref)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"\nGhostQL Demo Dataset Builder")
    print(f"Generating {RECORD_COUNT} synthetic records (seed={SEED})…\n")

    rng     = random.Random(SEED)
    records = [generate_record(i, rng) for i in range(1, RECORD_COUNT + 1)]
    print(f"  Generated {len(records)} records")

    # Split into two logical datasets
    patients = [to_patient(r) for r in records]
    clinical = [to_clinical(r) for r in records]

    # Write JSONL files
    for path, dataset in [('patients.jsonl', patients), ('clinical.jsonl', clinical)]:
        out = OUTPUT_DIR / path
        with open(out, 'w') as f:
            for rec in dataset:
                f.write(json.dumps(rec) + '\n')
        print(f"  Written: {out}")

    # Build unified index across both datasets
    print(f"\nBuilding unified PQR+FPD index…")
    index: dict = {}
    index_dataset(patients, 'patients.jsonl', index)
    print(f"  Indexed patients.jsonl  ({len(patients)} records)")
    index_dataset(clinical, 'clinical.jsonl', index)
    print(f"  Indexed clinical.jsonl  ({len(clinical)} records)")
    print(f"  Total index entries: {len(index):,}")

    # Write index
    index_path = OUTPUT_DIR / 'demo_index.json'
    with open(index_path, 'w') as f:
        json.dump({
            'meta': {
                'version':       '1.0.0',
                'records':       len(records),
                'datasets':      ['patients.jsonl', 'clinical.jsonl'],
                'index_entries': len(index),
                'seed':          SEED,
                'scheme':        'PQR+FPD self-salting SHA-256 V1.3.0+',
            },
            'index': index,
        }, f, separators=(',', ':'))
    print(f"  Written: {index_path}")

    # Verification
    print(f"\nVerification:")
    test_cases = [
        ('name', 'Mills'),
        ('nhs',  records[0]['nhs']),
        ('dlbl', 'Diabetes'),
        ('mlbl', 'Metformin'),
    ]
    for field, value in test_cases:
        h    = pqr_hash(value)
        hits = index.get(h, [])
        pat  = [r for r in hits if r.startswith('patients')]
        clin = [r for r in hits if r.startswith('clinical')]
        print(f"  {field}='{value}': {len(hits)} total  "
              f"(patients={len(pat)}  clinical={len(clin)})")

    print(f"\nDemo dataset ready.")
    print(f"  JOIN example:")
    print(f"  SELECT document FROM patients JOIN clinical ON nhs")
    print(f"    WHERE name='Mills' WITH PQR FPD\n")


if __name__ == '__main__':
    main()
