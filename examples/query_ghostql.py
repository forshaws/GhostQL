#!/usr/bin/env python3
"""
examples/query_ghostql.py
GhostQL Python Example Client v1.0.0

Demonstrates all query types via raw TCP.
For production use, the GhostQL Python client library is on the roadmap.
For now, this shows the raw protocol — it's intentionally simple.

Usage:
  python examples/query_ghostql.py
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
    ("Plain SELECT (no hashing)",
     "SELECT document FROM records WHERE name='Mills'"),

    ("SELECT WITH PQR",
     "SELECT document FROM records WHERE name='Mills' WITH PQR"),

    ("SELECT WITH PQR FPD (correct mode for PQR-ingested data)",
     "SELECT document FROM records WHERE name='Mills' WITH PQR FPD"),

    ("Multi-condition AND WITH PQR FPD",
     "SELECT document FROM records WHERE name='Mills' AND nhs='4855805912' WITH PQR FPD"),

    ("LIKE similarity search WITH PQR FPD",
     "SELECT document FROM records WHERE notes LIKE 'Mills pharmacy medication review' WITH PQR FPD"),

    ("JOIN WITH PQR FPD",
     "SELECT document FROM patients JOIN prescriptions ON nhs_number WHERE name='Mills' WITH PQR FPD"),
]


def read_until_prompt(sock: socket.socket, timeout: float = 10.0) -> str:
    sock.settimeout(0.1)
    buf = ''
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            chunk = sock.recv(4096).decode('utf-8', errors='replace')
            if chunk:
                buf += chunk
                if buf.rstrip().endswith('>'):
                    break
        except socket.timeout:
            pass
    return buf


def send_query(sock: socket.socket, query: str, timeout: float = 30.0) -> list:
    print(f"\n┌─ {query}")
    sock.sendall((query + '\n').encode())
    raw = read_until_prompt(sock, timeout)

    # Find and parse JSON
    for start_char in ('[', '{'):
        idx = raw.find(start_char)
        if idx != -1:
            try:
                data = json.loads(raw[idx:raw.rfind(']' if start_char == '[' else '}') + 1])
                if isinstance(data, dict):
                    data = [data]

                if data and data[0].get('status') == 'NO_MATCHES':
                    print(f"└─ ⚠  {data[0].get('message', 'No matches')}")
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

    print(f"└─ RAW: {raw[:200]}")
    return []


def main():
    print("\n╔══════════════════════════════════════════╗")
    print("║  GhostQL Python Example Client v1.0.0  ║")
    print("╚══════════════════════════════════════════╝")

    try:
        sock = socket.create_connection((HOST, PORT), timeout=5)
    except ConnectionRefusedError:
        print(f"\n✗ Could not connect to GhostQL at {HOST}:{PORT}")
        print("  Is the server running?  python -m ghostql.server")
        return

    # Auth
    banner = read_until_prompt(sock, 5)
    print(banner.strip())

    sock.sendall((USER + '\n').encode()); time.sleep(0.2)
    sock.sendall((PASS + '\n').encode())
    auth = read_until_prompt(sock, 5)
    print(auth.strip())

    # Ping
    print("\n── Ping ─────────────────────────────────────")
    sock.sendall(b'ping\n')
    print(read_until_prompt(sock, 5).strip())

    # Queries
    print("\n── Queries ──────────────────────────────────")
    for label, query in QUERIES:
        print(f"\n  [{label}]")
        send_query(sock, query)

    sock.sendall(b'quit\n')
    sock.close()
    print("\nDone.")


if __name__ == '__main__':
    main()
