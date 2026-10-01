#!/usr/bin/env python3
"""CDK v2 app entrypoint for the KiroOps serverless app.

Instantiates two independent stacks:

- :class:`KiroopsBackendStack` - the serverless backend: an HTTP API Gateway in
  front of a single Lambda function (the FastAPI app wrapped by Mangum) backed
  by a DynamoDB single-table design, with Amazon Bedrock Nova powering live
  diagnosis.
- :class:`KiroopsFrontendStack` - static hosting for the Vite + React SPA: a
  private S3 bucket served through CloudFront (Origin Access Control), with the
  built ``frontend/dist`` uploaded on deploy.

The stacks are kept separate so each can deploy on its own
(``cdk deploy KiroopsBackendStack`` / ``cdk deploy KiroopsFrontendStack``), and
``cdk deploy --all`` deploys both. There is no hard cross-stack reference: the
backend API URL is injected into the frontend at build time via
``VITE_API_BASE_URL`` (set from the backend's ``ApiEndpoint`` output).

This is infrastructure-as-code only. Running this file (via ``cdk synth`` /
``cdk deploy``) requires the AWS CDK CLI and the dependencies in
``requirements.txt``. It performs no AWS calls at author time and does not
deploy automatically.

Account and region are resolved from the standard CDK environment variables
(``CDK_DEFAULT_ACCOUNT`` / ``CDK_DEFAULT_REGION``) populated by the CDK CLI from
the active AWS profile, so nothing environment-specific is hard-coded here.
"""

from __future__ import annotations

import os

import aws_cdk as cdk

from kiroops_backend.kiroops_backend_stack import KiroopsBackendStack
from kiroops_frontend.kiroops_frontend_stack import KiroopsFrontendStack

app = cdk.App()

# Resolve the deployment environment from the CDK CLI context. These are set by
# the CLI from the active AWS profile; keeping them unhard-coded lets the same
# app deploy to any account/region.
env = cdk.Environment(
    account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
    region=os.environ.get("CDK_DEFAULT_REGION"),
)

KiroopsBackendStack(
    app,
    "KiroopsBackendStack",
    env=env,
    description="KiroOps serverless backend: HTTP API, Lambda (FastAPI/Mangum), DynamoDB, Bedrock Nova diagnosis.",
)

KiroopsFrontendStack(
    app,
    "KiroopsFrontendStack",
    env=env,
    description="KiroOps frontend hosting: private S3 bucket served via CloudFront (OAC) for the Vite/React SPA.",
)

app.synth()
