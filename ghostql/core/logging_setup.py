"""
ghostql/core/logging_setup.py
Centralised logging configuration for GhostQL.
"""
import logging
import sys
from pathlib import Path


def setup_logging(level: str = 'INFO', log_file: str = ''):
    """Configure root logger for GhostQL."""
    handlers = [logging.StreamHandler(sys.stdout)]

    if log_file:
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format='%(asctime)s  %(levelname)-8s  %(name)s  %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=handlers,
    )
