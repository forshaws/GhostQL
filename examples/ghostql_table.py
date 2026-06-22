#!/usr/bin/env python3
"""
examples/ghostql_table.py
GhostQL — MySQL-style table result demo

Runs a single query and prints all matching document references
as a formatted table — just like a MySQL result set.

In a real application, each filereference would be used to fetch
the actual document content — a JSON record, a PDF, an image,
a medical record, whatever was ingested. GhostQL finds the
references; your app fetches the content.

Usage:
  python examples/ghostql_table.py
"""
import socket
import json
import os
import re
import time

HOST  = os.environ.get('GHOSTQL_HOST', '127.0.0.1')
PORT  = int(os.environ.get('GHOSTQL_PORT', 5051))
USER  = os.environ.get('GHOSTQL_USER', 'admin')
PASS  = os.environ.get('GHOSTQL_PASS', 'changeme')

QUERY = "SELECT document FROM records WHERE dlbl LIKE 'Depressive disorder' WITH PQR FPD"


def recv_until(sock, marker: bytes, timeout: float = 15.0) -> str:
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


def send_line(sock, text: str):
    sock.sendall((text + '\n').encode('utf-8'))


def parse_fileref(ref: str) -> dict:
    # e.g. records_0001.jsonl::line1044::REC-00011044::fpd_04bfabf8::
    parts = ref.rstrip(':').split('::')
    return {
        'source': parts[0] if len(parts) > 0 else '-',
        'line':   parts[1].replace('line', '') if len(parts) > 1 else '-',
        'rec_id': parts[2] if len(parts) > 2 else '-',
        'fpd':    parts[3] if len(parts) > 3 else '-',
    }


def print_table(rows: list, total: int):
    if not rows:
        return

    # Column widths
    w = {
        'row':    max(3,  len(str(total))),
        'source': max(6,  max(len(r['source']) for r in rows)),
        'line':   max(4,  max(len(r['line'])   for r in rows)),
        'rec_id': max(6,  max(len(r['rec_id']) for r in rows)),
        'fpd':    max(3,  max(len(r['fpd'])    for r in rows)),
    }

    def div():
        return (f"+{'-'*(w['row']+2)}+{'-'*(w['source']+2)}"
                f"+{'-'*(w['line']+2)}+{'-'*(w['rec_id']+2)}"
                f"+{'-'*(w['fpd']+2)}+")

    def row_line(num, source, line, rec_id, fpd):
        return (f"| {str(num).ljust(w['row'])} "
                f"| {source.ljust(w['source'])} "
                f"| {line.ljust(w['line'])} "
                f"| {rec_id.ljust(w['rec_id'])} "
                f"| {fpd.ljust(w['fpd'])} |")

    print(div())
    print(row_line('#', 'Source', 'Line', 'Rec ID', 'FPD'))
    print(div())
    for i, r in enumerate(rows, 1):
        print(row_line(i, r['source'], r['line'], r['rec_id'], r['fpd']))
    print(div())
    print(f"  {total} row(s) returned")


def main():
    print(f"\n  GhostQL — Query Result")
    print(f"  Query : {QUERY}")
    print(f"  Server: {HOST}:{PORT}\n")

    try:
        sock = socket.create_connection((HOST, PORT), timeout=5)
    except ConnectionRefusedError:
        print(f"✗ Cannot connect to GhostQL at {HOST}:{PORT}")
        print("  Is the server running?  python -m ghostql.server")
        return

    # Auth
    recv_until(sock, b'Username:')
    send_line(sock, USER)
    recv_until(sock, b'Password:')
    send_line(sock, PASS)
    auth = recv_until(sock, b'>')

    if 'ERROR' in auth:
        print("✗ Authentication failed. Check GHOSTQL_PASS.")
        sock.close()
        return

    # Query
    send_line(sock, QUERY)
    raw = recv_until(sock, b'>', timeout=60.0)

    # Parse JSON
    data = None
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
                    break
                except json.JSONDecodeError:
                    pass

    if not data or data[0].get('status') == 'NO_MATCHES':
        msg = data[0].get('message', 'No results') if data else 'No results'
        print(f"  ⚠  {msg}\n")
        sock.close()
        return

    # Parse and print table
    rows = [parse_fileref(r.get('document', '')) for r in data]
    print_table(rows, len(rows))

    print()
    print("  Each Rec ID is a pointer to the source document.")
    print("  Your application would use these to fetch the actual content —")
    print("  a JSON record, PDF, image, or any ingested file.")
    print()

    send_line(sock, 'quit')
    sock.close()


if __name__ == '__main__':
    main()
