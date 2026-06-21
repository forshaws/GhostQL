#!/usr/bin/env python3
"""
ghostql/server.py
GhostQL TCP Server v1.0.0

Listens for GhostQL query connections, authenticates clients,
dispatches queries, and returns JSON results.

Usage:
  python -m ghostql.server
  python -m ghostql.server --config /path/to/ghostql.conf

Protocol:
  TCP text protocol, newline-delimited.
  Client sends lines; server responds with JSON + prompt (>).

  Banner → Username: → Password: → OK/ERROR → queries → quit
"""
import socket
import threading
import json
import logging
import argparse
import sys
from pathlib import Path

from .core.config import GhostQLConfig
from .core.logging_setup import setup_logging
from .connectors import load_connector
from .query import dispatch
from .query.parser import ParseError

logger = logging.getLogger(__name__)

BANNER = r"""
  ______  _               _    ____  _
 / ___| || |__   ___  ___| |_ / __ \| |
| |  _| || '_ \ / _ \/ __| __/ / _` | |
| |_| | || | | | (_) \__ \ |_| | (_| | |___
 \____|_||_| |_|\___/|___/\__\ \__,_|_____|
  GhostQL v1.0.0 — Composable Sequential DB
  https://github.com/toridion/ghostql
"""

HELP_TEXT = """
GhostQL Query Language v1.0.0

Syntax:
  SELECT <cols> FROM <table> WHERE <field>='<value>' [AND ...] [WITH PQR [FPD]]
  SELECT <cols> FROM <table> WHERE <field> LIKE '<free text>' [WITH PQR [FPD]]
  SELECT <cols> FROM <table> JOIN <table2> ON <field> WHERE ... [WITH PQR [FPD]]

Flags:
  WITH PQR     — Self-salting SHA-256 hash per token (required for PQR-ingested data)
  WITH PQR FPD — PQR + False Positive Defence (forward ∩ reversed-input hash)

Examples:
  SELECT document FROM records WHERE name='Mills' WITH PQR FPD
  SELECT document FROM records WHERE name LIKE 'John Mills pharmacist' WITH PQR FPD
  SELECT document FROM patients JOIN prescriptions ON nhs_number WHERE name='Chen' WITH PQR FPD
  SELECT document, nhs FROM records WHERE nhs='4855805912' AND name='Chen' WITH PQR

Commands:
  help | ?    Show this text
  ping        Test connector health
  quit | exit Close connection
"""


def _send(conn: socket.socket, msg: str):
    try:
        conn.sendall((msg + "\n").encode('utf-8'))
    except Exception as e:
        logger.debug(f"[SEND ERROR] {e}")


def handle_client(conn: socket.socket, addr, config: GhostQLConfig, connector):
    logger.info(f"[CONNECT] {addr}")
    try:
        _send(conn, BANNER.strip())
        _send(conn, "Username:")

        user = conn.recv(1024).decode('utf-8', errors='replace').strip()
        _send(conn, "Password:")
        pw   = conn.recv(1024).decode('utf-8', errors='replace').strip()

        if user != config.server_username or pw != config.server_password:
            _send(conn, "ERROR: Access denied")
            logger.warning(f"[AUTH FAIL] {addr}  user={user!r}")
            return

        logger.info(f"[AUTH OK] {addr}  user={user!r}")
        _send(conn, "OK: Authenticated")
        _send(conn, f"INFO: Connector = {connector.name()}")
        _send(conn, "INFO: Type 'help' for query syntax")
        _send(conn, ">")

        while True:
            data = conn.recv(4096)
            if not data:
                break

            query = data.decode('utf-8', errors='replace').strip()
            if not query:
                _send(conn, ">")
                continue

            if query.lower() in ('quit', 'exit', 'bye'):
                _send(conn, "Goodbye!")
                break

            if query.lower() in ('help', '?'):
                _send(conn, HELP_TEXT)
                _send(conn, ">")
                continue

            if query.lower() == 'ping':
                ok = connector.ping()
                _send(conn, json.dumps({'ping': 'OK' if ok else 'FAILED'}))
                _send(conn, ">")
                continue

            try:
                logger.info(f"[QUERY] {addr}  {query}")
                results = dispatch(query, connector, config)
                _send(conn, json.dumps(results, indent=2))
                _send(conn, f"-- {len(results)} row(s) returned")
            except ParseError as e:
                _send(conn, json.dumps({'error': f'Parse error: {e}'}))
            except Exception as e:
                logger.exception(f"[QUERY ERROR] {e}")
                _send(conn, json.dumps({'error': str(e)}))

            _send(conn, ">")

    except Exception as e:
        logger.exception(f"[CLIENT ERROR] {addr}  {e}")
    finally:
        conn.close()
        logger.info(f"[DISCONNECT] {addr}")


def start(config: GhostQLConfig):
    connector = load_connector(config)
    logger.info(f"Connector ready: {connector.name()}")

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server.bind((config.server_host, config.server_port))
        server.listen(5)
        logger.info(
            f"GhostQL listening on {config.server_host}:{config.server_port}"
        )

        while True:
            conn, addr = server.accept()
            t = threading.Thread(target=handle_client, args=(conn, addr, config, connector))
            t.daemon = True
            t.start()

    except KeyboardInterrupt:
        logger.info("Shutdown requested")
    finally:
        server.close()


def main():
    ap = argparse.ArgumentParser(description='GhostQL Server v1.0.0')
    ap.add_argument('--config', '-c', help='Path to ghostql.conf', default=None)
    args = ap.parse_args()

    config = GhostQLConfig(args.config)
    setup_logging(config.log_level, config.log_file)

    logger.info("=" * 56)
    logger.info("  GhostQL v1.0.0 — Composable Sequential DB Engine")
    logger.info("=" * 56)

    start(config)


if __name__ == '__main__':
    main()
