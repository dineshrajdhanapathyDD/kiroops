"""Shared import shim for the standalone incident-mcp server.

Makes the backend package importable from this standalone folder so the server
reuses the single source of truth for seeded simulated data in
``backend/mcp/tools.py`` instead of duplicating the seeding logic.

The workspace root (two levels up from this file: ``mcp/incident-mcp/``) is the
directory that contains the ``backend`` package, so it is placed on ``sys.path``.
"""

from __future__ import annotations

import sys
from pathlib import Path

_WORKSPACE_ROOT = Path(__file__).resolve().parents[2]

if str(_WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE_ROOT))
