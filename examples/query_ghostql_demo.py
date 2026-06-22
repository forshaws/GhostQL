#!/usr/bin/env python3
"""
examples/query_ghostql_demo.py
GhostQL Demo Client v1.0.0 — Local Dataset

Demonstrates all GhostQL query types against the bundled demo dataset.
No DMM credentials required — works out of the box with:

  [connector]
  type = local

Usage:
  python examples/query_ghostql_demo.py

Credentials via environment variables or defaults below:
  GHOSTQL_HOST, GHOSTQL_PORT, GHOSTQL_USER, GHOSTQL_PASS
"""
import socket
import json
import os
import time

HOST = os.environ.get('GHOSTQL_HOST', '127.0.0.1')
PORT = int(os.environ.get('GHOSTQL_PORT', 5051))
USER = os.environ.get('GHOSTQL_USER', 'admin')
PASS = os.environ.get('GHOSTQL_PASS', 'changeme')

QUERIES = [
    (
        "Plain SELECT — no hashing (expected: NO_MATCHES, dataset is PQR-ingested)",
        "SELECT document FROM records WHERE name='Mills'"
    ),
    (
        "SELECT WITH PQR — find all patients named Mills",
        "SELECT document FROM records WHERE name='Mills' WITH PQR FPD"
    ),
    (
        "SELECT WITH PQR FPD — find patients with diabetes",
        "SELECT document FROM records WHERE dlbl='Diabetes' WITH PQR FPD"
    ),
    (
        "Multi-condition AND — narrow to a specific town and diagnosis",
        "SELECT document FROM records WHERE town='Scarborough' AND dlbl='Hypertension' WITH PQR FPD"
    ),
    (
        "Multi-condition AND — GP practice and medication",
        "SELECT document FROM records WHERE gp='Parkway' AND mlbl='Metformin' WITH PQR FPD"
    ),
    (
        "LIKE — similarity search across diagnosis labels",
        "SELECT document FROM records WHERE dlbl LIKE 'Alzheimer Crohn's Psoriasis' WITH PQR FPD"
    ),
    (
        "LIKE — find patients on related medications",
        "SELECT document FROM records WHERE mlbl LIKE 'Metformin Warfarin Sertraline' WITH PQR FPD"
    ),
    (
        "JOIN — patients and records sharing a town",
        "SELECT document FROM records JOIN records ON dlbl WHERE town='Scarborough' WITH PQR FPD"
        
    ),
]


def recv_until(sock: socket.socket, marker: bytes, timeout: float = 10.0) -> str:
    sock.settimeout(0.2)
    buf = b''
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            chunk = sock.recv(4096)
            if not chunk:
                break
            buf += chunk
            if marker in buf:
                break
        except socket.timeout:
            pass
    return buf.decode('utf-8', errors='replace')


def send_line(sock: socket.socket, text: str):
    sock.sendall((text + '\n').encode('utf-8'))


def send_query(sock: socket.socket, query: str, timeout: float = 30.0) -> list:
    print(f"\n┌─ {query}")
    send_line(sock, query)
    raw = recv_until(sock, b'>', timeout)

    for start_char in ('[', '{'):
        idx = raw.find(start_char)
        if idx != -1:
            end_char = ']' if start_char == '[' else '}'
            end_idx  = raw.rfind(end_char)
            if end_idx != -1:
                try:
                    data = json.loads(raw[idx:end_idx + 1])
                    if isinstance(data, dict):
                        data = [data]

                    if data and data[0].get('status') in ('NO_MATCHES', 'NO_TOKENS'):
                        print(f"└─ ⚠  {data[0].get('message', 'No matches')}")
                        for token, count in data[0].get('search_summary', {}).items():
                            print(f"       '{token}' → {count} hit(s)")
                    else:
                        print(f"└─ ✓  {len(data)} result(s)")
                        for i, row in enumerate(data[:3], 1):
                            doc = row.get('document', json.dumps(row))
                            pct = f"  ({row['overlap_pct']}%)" if 'overlap_pct' in row else ''
                            print(f"   [{i}] {doc}{pct}")
                        if len(data) > 3:
                            print(f"   … and {len(data) - 3} more")
                    return data
                except json.JSONDecodeError:
                    pass

    print(f"└─ RAW: {raw[:300]}")
    return []


def main():
    print("\n╔══════════════════════════════════════════╗")
    print("║  GhostQL Demo Client v1.0.0              ║")
    print("║  Local dataset · 500 synthetic records   ║")
    print("╚══════════════════════════════════════════╝")

    try:
        sock = socket.create_connection((HOST, PORT), timeout=5)
    except ConnectionRefusedError:
        print(f"\n✗ Could not connect to GhostQL at {HOST}:{PORT}")
        print("  Is the server running?  python -m ghostql.server")
        print("  Is ghostql.conf set to connector.type = local?")
        return

    # Auth
    banner = recv_until(sock, b'Username:')
    print(banner)

    send_line(sock, USER)
    recv_until(sock, b'Password:')
    print("Password:")

    send_line(sock, PASS)
    auth = recv_until(sock, b'>')
    print(auth.strip())

    if 'ERROR' in auth:
        print("\n✗ Authentication failed.")
        print("  export GHOSTQL_PASS=your_password_from_ghostql_conf")
        sock.close()
        return

    # Ping
    print("\n── Ping ─────────────────────────────────────")
    send_line(sock, 'ping')
    print(recv_until(sock, b'>').strip())

    # Queries
    print("\n── Queries ──────────────────────────────────")
    for label, query in QUERIES:
        print(f"\n  [{label}]")
        send_query(sock, query)

    send_line(sock, 'quit')
    sock.close()
    print("\nDone.")


if __name__ == '__main__':
    main()
