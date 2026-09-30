"""Shared helpers for the DynamoDB repository tests (Phase 1).

Provides a context manager that stands up a fresh single table (with the
``GSI1`` index) inside moto's in-memory ``mock_aws``, so each test - or each
Hypothesis example - runs against an isolated table with no shared state and no
Docker. The table is created via the same
:func:`backend.repository.dynamo.create_table` helper the production/local
bootstrap uses.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from moto import mock_aws

from backend.repository import dynamo

TEST_REGION = "us-east-1"


@contextmanager
def fresh_table() -> Iterator[Any]:
    """Yield a freshly created, isolated DynamoDB ``Table`` under moto.

    A unique table name per use keeps examples independent even if moto state
    lingers within a single ``mock_aws`` scope.
    """
    with mock_aws():
        table_name = f"kiroops-test-{uuid.uuid4().hex}"
        table = dynamo.create_table(table_name, TEST_REGION)
        yield table
