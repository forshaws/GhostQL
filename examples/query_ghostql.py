#!/usr/bin/env python3
"""
examples/query_ghostql.py
GhostQL Python Example Client v1.0.0

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


def recv_until(sock: socket.socket, marker: bytes, timeout: float = 10.0) -> str:
    """
    Read from socket until `marker` appears in the buffer, or timeout.
    Returns the full buffer as a string.
    Uses a short inner timeout so we keep accumulating across multiple recv() calls.
    """
    sock.settimeout(0.2)
    buf = b''
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            chunk = sock.recv(4096)
            if not chunk:
                break          # server closed connection
            buf += chunk
            if marker in buf:
                break
        except socket.timeout:
            pass               # keep looping until deadline
    return buf.decode('utf-8', errors='replace')


def send_line(sock: socket.socket, text: str):
    """Send a line (with newline) to the server."""
    sock.sendall((text + '\n').encode('utf-8'))


def send_query(sock: socket.socket, query: str, timeout: float = 30.0) -> list:
    print(f"\n┌─ {query}")
    send_line(sock, query)

    # Wait for the prompt that follows the result
    raw = recv_until(sock, b'>', timeout)

    # Extract JSON block
    for start_char in ('[', '{'):
        idx = raw.find(start_char)
        if idx != -1:
            end_char = ']' if start_char == '[' else '}'
            end_idx = raw.rfind(end_char)
            if end_idx != -1:
                try:
                    data = json.loads(raw[idx:end_idx + 1])
                    if isinstance(data, dict):
                        data = [data]

                    if data and data[0].get('status') in ('NO_MATCHES', 'NO_TOKENS'):
                        print(f"└─ ⚠  {data[0].get('message', 'No matches')}")
                        summary = data[0].get('search_summary', {})
                        for token, count in summary.items():
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
    print("║   GhostQL Python Example Client v1.0.0   ║")
    print("╚══════════════════════════════════════════╝")

    try:
        sock = socket.create_connection((HOST, PORT), timeout=5)
    except ConnectionRefusedError:
        print(f"\n✗ Could not connect to GhostQL at {HOST}:{PORT}")
        print("  Is the server running?  python -m ghostql.server")
        return

    # ── Auth handshake — wait for each prompt before sending ─────────────────
    # 1. Read banner + "Username:" prompt
    banner = recv_until(sock, b'Username:')
    print(banner)

    # 2. Send username, wait for "Password:" prompt
    send_line(sock, USER)
    recv_until(sock, b'Password:')
    print("Password:")

    # 3. Send password, wait for auth result prompt ">"
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

    # ── Ping ──────────────────────────────────────────────────────────────────
    print("\n── Ping ─────────────────────────────────────")
    send_line(sock, 'ping')
    print(recv_until(sock, b'>').strip())

    # ── Queries ───────────────────────────────────────────────────────────────
    print("\n── Queries ──────────────────────────────────")
    for label, query in QUERIES:
        print(f"\n  [{label}]")
        send_query(sock, query)

    send_line(sock, 'quit')
    sock.close()
    print("\nDone.")


if __name__ == '__main__':
    main()
