"""Smoke test for the Lambda entrypoint (Phase 2).

Guarded with ``importorskip("mangum")`` so the broader suite never depends on
the optional ``lambda`` extra: if mangum is absent this test is skipped, not
failed. When mangum is installed, importing ``backend.lambda_handler`` must
succeed with the default (SQLite) config and expose a callable ``handler``.
"""

from __future__ import annotations

import pytest

pytest.importorskip("mangum")


def test_lambda_handler_imports_and_exposes_callable_handler() -> None:
    """backend.lambda_handler imports cleanly and defines a callable handler."""
    from backend import lambda_handler

    assert callable(lambda_handler.handler)
