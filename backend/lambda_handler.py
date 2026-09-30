"""AWS Lambda entrypoint for the KiroOps backend (Phase 2).

Wraps the FastAPI app in a Mangum adapter so it can run behind API Gateway.
The Lambda function is configured with handler ``backend.lambda_handler.handler``.

Configuration is read from the environment at import time via ``create_app()``:
in Lambda the environment sets ``KIROOPS_PERSISTENCE=dynamodb`` (plus the table
name and region), so the app is wired to the DynamoDB backend. When
``KIROOPS_PERSISTENCE`` is unset it defaults to SQLite and requires no AWS
access, so this module stays importable outside Lambda for local checks.

``mangum`` is an optional dependency (the ``lambda`` extra); only the Lambda
package needs it. No test in the suite imports this module, so the broader test
run does not require ``mangum`` to be installed.
"""

from __future__ import annotations

from mangum import Mangum

from backend.api.app import create_app

# Built once at cold start; reused across warm invocations. create_app() reads
# config (persistence, region, table, CORS) from the environment and performs no
# network calls at construction time (the DynamoDB table resource is created
# lazily and the LLM provider only contacts AWS on the first diagnosis call).
app = create_app()

# The Lambda handler object. Referenced as "backend.lambda_handler.handler".
handler = Mangum(app)
