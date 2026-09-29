# KiroOps Backend

Python (FastAPI-style) service for KiroOps incident-management. Persists to
local SQLite through a repository layer, exposes MCP evidence tools, and runs a
diagnosis agent behind an injected LLM provider.

## Package layout

```
backend/
  config.py        # LlmConfig + SQLite path, read from environment
  domain/          # enums, dataclasses, pure status state machine
  repository/      # SQLite connection factory + repositories
  service/         # deterministic business rules
  api/             # FastAPI routers + request/response models
  mcp/             # simulated evidence-gathering tools
  agent/           # diagnosis orchestration
  tests/           # pytest + Hypothesis
```

## Setup

```bash
py -m venv .venv
.venv\Scripts\activate        # Windows
pip install -e ".[dev]"        # or: pip install -r requirements.txt
```

## Test

```bash
pytest
```

## Configuration

All configuration is read from the environment with sensible defaults. No
secrets, endpoints, or model ids are hard-coded.

| Env var                 | Default                            | Purpose                     |
|-------------------------|------------------------------------|-----------------------------|
| `KIROOPS_DB_PATH`       | `kiroops.db`                       | SQLite database file path   |
| `KIROOPS_LLM_MODEL_ID`  | `anthropic.claude-3-5-sonnet`      | LLM model identifier        |
| `KIROOPS_LLM_ENDPOINT`  | `https://bedrock-runtime.us-east-1.amazonaws.com` | LLM endpoint |
