#!/usr/bin/env python3
"""
examples/query_ghostql.py
GhostQL Python Example Client v1.1.0

Demonstrates all GhostQL query types against a running GhostQL server.

Prerequisites:
  1. GhostQL server running: python -m ghostql.server
  2. ghostql.conf configured with valid DMM credentials

Usage:
  python examples/query_ghostql.py

Credentials via environment variables (recommended) or edit defaults below:
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
        "Test 1 — Plain SELECT, no hashing (expected: NO_MATCHES on PQR-ingested data)",
        "SELECT document FROM records WHERE name='Mills'"
    ),
    (
        "Test 2 — SELECT WITH PQR — hashed tokens, no FPD",
        "SELECT document FROM records WHERE name='Mills' WITH PQR"
    ),
    (
        "Test 3 — SELECT WITH PQR FPD — correct mode for PQR+FPD-ingested data",
        "SELECT document FROM records WHERE name='Mills' WITH PQR FPD"
    ),
    (
        "Test 4 — AND — multi-condition intersection, pinpoint a single record",
        "SELECT document FROM records WHERE name='Mills' AND nhs='4855805912' WITH PQR FPD"
    ),
    (
        "Test 5 — LIKE — similarity search, ranked by token overlap",
        "SELECT document FROM records WHERE dlbl LIKE 'Retinal detachment' WITH PQR FPD"
    ),
    (
        "Test 6 — JOIN — cross-dataset join via shared field token",
        "SELECT document FROM patients JOIN clinical ON nhs WHERE name='Mills' WITH PQR FPD"
    ),
    (
        "Test 7 — OR — union of two name searches",
        "SELECT document FROM records WHERE name='Mills' OR name='Chen' WITH PQR FPD"
    ),
    (
        "Test 8 — OR — union across different fields",
        "SELECT document FROM records WHERE dlbl='Diabetes' OR mlbl='Metformin' WITH PQR FPD"
    ),
    (
        "Test 9 — Mixed AND/OR — AND binds tighter, (Mills AND Retinal) OR Diabetes",
        "SELECT document FROM records WHERE name='Mills' AND dlbl='Retinal' OR dlbl='Diabetes' WITH PQR FPD"
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


def send_query(sock: socket.socket, label: str, query: str, timeout: float = 30.0) -> list:
    print(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"  {label}")
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"┌─ {query}")
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
                        for i, row in enumerate(data[:5], 1):
                            doc = row.get('document', json.dumps(row))
                            pct = f"  ({row['overlap_pct']}%)" if 'overlap_pct' in row else ''
                            print(f"   [{i}] {doc}{pct}")
                        if len(data) > 5:
                            print(f"   … and {len(data) - 5} more")
                    return data
                except json.JSONDecodeError:
                    pass

    print(f"└─ RAW: {raw[:300]}")
    return []


def main():
    print("\n╔══════════════════════════════════════════╗")
    print("║   GhostQL Python Example Client v1.1.0   ║")
    print("╚══════════════════════════════════════════╝")

    try:
        sock = socket.create_connection((HOST, PORT), timeout=5)
    except ConnectionRefusedError:
        print(f"\n✗ Could not connect to GhostQL at {HOST}:{PORT}")
        print("  Is the server running?  python -m ghostql.server")
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
        print("  Set credentials via environment variables:")
        print("    export GHOSTQL_USER=admin")
        print("    export GHOSTQL_PASS=your_password_from_ghostql_conf")
        sock.close()
        return

    # Ping
    print("\n── Ping ─────────────────────────────────────")
    send_line(sock, 'ping')
    print(recv_until(sock, b'>').strip())

    # Queries
    for label, query in QUERIES:
        send_query(sock, label, query, timeout=60.0)

    send_line(sock, 'quit')
    sock.close()
    print("\nDone.")


if __name__ == '__main__':
    main()
