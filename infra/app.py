#!/usr/bin/env python3
"""CDK v2 app entrypoint for the KiroOps serverless backend.

Instantiates :class:`KiroopsBackendStack`, which provisions the serverless
backend: an HTTP API Gateway in front of a single Lambda function (the FastAPI
app wrapped by Mangum) backed by a DynamoDB single-table design, with Amazon
Bedrock Nova powering live diagnosis.

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

app.synth()
