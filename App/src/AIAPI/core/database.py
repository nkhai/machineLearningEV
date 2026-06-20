"""
AIAPI database module — mirrors admin_server.py connection logic.
Loads .env first, then imports the shared ev_client_app connection layer.
Both AIAPI and ev_client_app connect to the same PostgreSQL instance.
"""
import os
import sys

# ── Load .env BEFORE importing DB connection (same pattern as admin_server.py) ──
_current_dir = os.path.dirname(os.path.abspath(__file__))
_env_candidates = [
    os.path.join(_current_dir, "..", "..", "infra", ".env"),  # src/infra/.env (local)
    os.path.join(_current_dir, "..", ".env"),                  # src/AIAPI/.env (local or Docker)
    os.path.join(_current_dir, ".env"),                       # fallback
]
from dotenv import load_dotenv
for _env_path in _env_candidates:
    if os.path.isfile(_env_path):
        load_dotenv(_env_path, override=True)
        break

# ── Add ev_client_app to import path ──
_ev_client_candidates = [
    os.path.join(_current_dir, "..", "..", "ev_client_app"),  # local: src/ev_client_app
    "/app/ev_client_app",                                      # Docker mount
]
for _ev_path in _ev_client_candidates:
    if os.path.isdir(_ev_path):
        _src_root = os.path.dirname(_ev_path)
        if _src_root not in sys.path:
            sys.path.insert(0, _src_root)
        break

from ev_client_app.database.connection import (  # noqa: E402
    engine,
    SessionLocal,
    Base,
    get_db,
)

__all__ = ["engine", "SessionLocal", "Base", "get_db"]
