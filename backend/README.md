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
| `KIROOPS_LLM_MODEL_ID`  | `us.amazon.nova-lite-v1:0`         | Bedrock model / inference profile id |
| `KIROOPS_LLM_ENDPOINT`  | `https://bedrock-runtime.us-east-1.amazonaws.com` | LLM endpoint |
| `KIROOPS_LLM_REGION`    | `AWS_REGION` / `AWS_DEFAULT_REGION` / `us-east-1` | AWS region for Bedrock |

## Enabling live diagnosis (Bedrock Nova)

Out of the box the diagnosis endpoint returns `503` (diagnosis unavailable,
incident status unchanged) because `boto3` is not a core dependency. To return
a real, model-generated diagnosis instead:

1. Install the optional extra (pulls in `boto3`):

   ```bash
   py -m pip install -e ".[bedrock]"
   ```

2. Configure the model and region (all optional; defaults shown above):

   ```bash
   # Windows PowerShell
   $env:KIROOPS_LLM_MODEL_ID = "us.amazon.nova-lite-v1:0"   # or nova-micro / nova-pro
   $env:KIROOPS_LLM_REGION   = "us-east-1"
   ```

   Nova models require a cross-region inference profile for on-demand use; the
   `us.` prefix selects the US profile. Pick `us.amazon.nova-micro-v1:0`,
   `us.amazon.nova-lite-v1:0`, or `us.amazon.nova-pro-v1:0`.

3. Provide AWS credentials via the standard credential chain (environment
   variables, a shared profile, or an attached role) and make sure your account
   has Bedrock model access enabled for the chosen Nova model in that region.
   No credentials are ever read from or written to the source.

With the extra installed and credentials present, `build_default_provider()`
selects the Bedrock Nova provider automatically and the demo returns a real
diagnosis. If `boto3` is missing, credentials are absent, or the call fails, the
provider degrades to `LlmUnavailableError` and the endpoint keeps returning
`503` with the incident status unchanged.
