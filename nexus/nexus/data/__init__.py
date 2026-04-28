"""Static seed data for NEXUS supply chain simulation."""

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent
_CACHE = {}

def load_json(filename: str) -> dict | list:
    """Load a JSON data file from the data directory with memory caching."""
    if filename not in _CACHE:
        with open(DATA_DIR / filename, "r", encoding="utf-8") as f:
            _CACHE[filename] = json.load(f)
    return _CACHE[filename]
