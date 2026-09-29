"""Smoke tests for configuration and SQLite bootstrap (Tasks 1.1, 1.2).

Requirements: 1.1, 4.6, 6.2.
"""

from __future__ import annotations

from backend import config
from backend.repository import db


def test_config_reads_defaults_when_env_absent() -> None:
    app = config.AppConfig.from_env(env={})
    assert app.db_path == config.DEFAULT_DB_PATH
    assert app.llm.model_id == config.DEFAULT_LLM_MODEL_ID
    assert app.llm.endpoint == config.DEFAULT_LLM_ENDPOINT


def test_config_reads_from_env_overrides() -> None:
    env = {
        config.ENV_DB_PATH: "/tmp/custom.db",
        config.ENV_LLM_MODEL_ID: "model-x",
        config.ENV_LLM_ENDPOINT: "https://example.test",
    }
    app = config.AppConfig.from_env(env=env)
    assert app.db_path == "/tmp/custom.db"
    assert app.llm.model_id == "model-x"
    assert app.llm.endpoint == "https://example.test"


def test_bootstrap_creates_the_four_tables() -> None:
    conn = db.in_memory()
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
        names = {row["name"] for row in rows}
        for table in db.TABLE_NAMES:
            assert table in names, f"missing table: {table}"
    finally:
        conn.close()


def test_foreign_keys_pragma_enabled() -> None:
    conn = db.connect(config.IN_MEMORY_DB_PATH)
    try:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        conn.close()


def test_apply_schema_is_idempotent() -> None:
    conn = db.in_memory()
    try:
        db.apply_schema(conn)  # second application must not raise
    finally:
        conn.close()
