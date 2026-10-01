"""KiroOps serverless backend stack (CDK v2, Python).

Provisions, following AWS Well-Architected and least-privilege IAM:

- A DynamoDB single-table design (PK/SK) with a GSI1 secondary index,
  on-demand billing, point-in-time recovery, and a retain removal policy.
- A Lambda function running the FastAPI app (wrapped by Mangum) on the
  Python 3.12 ARM64 (Graviton) runtime, bundled from ``backend/`` with its
  runtime dependencies.
- An HTTP API Gateway that proxies every route to the Lambda, with CORS.
- Least-privilege IAM: scoped DynamoDB read/write on the table (and its
  indexes) plus a narrowly scoped ``bedrock:InvokeModel`` statement for the
  Nova inference profile and foundation model.
- Stack outputs for the API endpoint, table name, and function name.

No secrets, model ids, or endpoints are hard-coded beyond non-secret defaults;
operational values are surfaced as context/parameters so a deployment can
override them. This file is infrastructure-as-code only.
"""

from __future__ import annotations

import os

import aws_cdk as cdk
from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
)
from aws_cdk import aws_apigatewayv2 as apigwv2
from aws_cdk import aws_apigatewayv2_integrations as integrations
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from constructs import Construct

# Repo root is the parent of this stack package's parent (infra/).
# infra/kiroops_backend/kiroops_backend_stack.py -> infra/ -> repo root.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_INFRA_DIR = os.path.dirname(_THIS_DIR)
_REPO_ROOT = os.path.dirname(_INFRA_DIR)

# Non-secret default Nova model id. Overridable via context ("modelId") so a
# deployment can select nova-micro / nova-lite / nova-pro without code changes.
DEFAULT_MODEL_ID = "us.amazon.nova-lite-v1:0"
# Default region Bedrock is called in when the stack region is unavailable at
# synth time (e.g. an env-agnostic synth). us-east-1 supports the Nova profiles.
DEFAULT_BEDROCK_REGION = "us-east-1"
# Permissive development default; a production deployment should set the
# frontend origin via the "corsOrigins" context value.
DEFAULT_CORS_ORIGINS = "*"


class KiroopsBackendStack(Stack):
    """Serverless backend: HTTP API + Lambda (FastAPI/Mangum) + DynamoDB."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ---- Context-driven, non-secret configuration -----------------------
        # CORS origins and model id come from CDK context so operators can
        # override them at deploy time (e.g. -c corsOrigins=https://app.example).
        cors_origins_raw = str(
            self.node.try_get_context("corsOrigins") or DEFAULT_CORS_ORIGINS
        )
        cors_origins = [o.strip() for o in cors_origins_raw.split(",") if o.strip()]

        model_id = str(self.node.try_get_context("modelId") or DEFAULT_MODEL_ID)

        # The region Bedrock is called in. Prefer the stack region (a concrete
        # value when the app is run with an environment); fall back to a known
        # Bedrock region for env-agnostic synth.
        bedrock_region = (
            self.region
            if self.region and not cdk.Token.is_unresolved(self.region)
            else DEFAULT_BEDROCK_REGION
        )

        # ---- DynamoDB single-table design -----------------------------------
        # PK/SK primary key + GSI1 (GSI1PK/GSI1SK). On-demand billing (no
        # capacity planning), point-in-time recovery for durability, and RETAIN
        # so a stack delete never discards incident data (see README).
        table = dynamodb.TableV2(
            self,
            "KiroopsTable",
            partition_key=dynamodb.Attribute(
                name="PK", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="SK", type=dynamodb.AttributeType.STRING
            ),
            billing=dynamodb.Billing.on_demand(),
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True
            ),
            removal_policy=RemovalPolicy.RETAIN,
            global_secondary_indexes=[
                dynamodb.GlobalSecondaryIndexPropsV2(
                    index_name="GSI1",
                    partition_key=dynamodb.Attribute(
                        name="GSI1PK", type=dynamodb.AttributeType.STRING
                    ),
                    sort_key=dynamodb.Attribute(
                        name="GSI1SK", type=dynamodb.AttributeType.STRING
                    ),
                    projection_type=dynamodb.ProjectionType.ALL,
                )
            ],
        )

        # ---- Lambda function (FastAPI app via Mangum) -----------------------
        # Bundled from the repo root with Code.from_asset + Docker bundling in
        # the Lambda ARM64 Python 3.12 build image: pip-installs the runtime
        # deps (fastapi, mangum, pydantic, starlette) into the asset and copies
        # the backend package so the handler "backend.lambda_handler.handler"
        # resolves at the Lambda root. boto3/botocore are intentionally NOT
        # installed (the Lambda runtime already provides them).
        runtime = lambda_.Runtime.PYTHON_3_12
        architecture = lambda_.Architecture.ARM_64

        # Build commands run inside the bundling container. /asset-input is the
        # bundled source (repo root), /asset-output becomes the deployed package.
        bundling_command = [
            "bash",
            "-c",
            " && ".join(
                [
                    # Install the FastAPI/Mangum runtime deps (no boto3) to the
                    # output. Force the manylinux aarch64 wheels so native
                    # extensions (pydantic-core) match the Graviton ARM64 runtime
                    # regardless of the build host's architecture.
                    "pip install --no-cache-dir "
                    "--platform manylinux2014_aarch64 "
                    "--implementation cp --python-version 3.12 "
                    "--only-binary=:all: --upgrade "
                    "'fastapi>=0.110' 'mangum>=0.17' 'pydantic>=2.6' "
                    "-t /asset-output",
                    # Copy only the backend package into the output.
                    "cp -r /asset-input/backend /asset-output/backend",
                    # Drop test/dev artifacts and caches from the package.
                    "rm -rf /asset-output/backend/tests "
                    "/asset-output/backend/.hypothesis "
                    "/asset-output/backend/.pytest_cache "
                    "/asset-output/backend/kiroops.db",
                    "find /asset-output -type d -name __pycache__ -prune -exec rm -rf {} +",
                    "find /asset-output -type d -name 'botocore*' -prune -exec rm -rf {} +",
                    "find /asset-output -type d -name 'boto3*' -prune -exec rm -rf {} +",
                ]
            ),
        ]

        # Explicit log group with a one-week retention (replaces the deprecated
        # Function.log_retention). Logs are not precious state, so destroy on
        # stack delete to avoid orphaned log groups.
        log_group = logs.LogGroup(
            self,
            "KiroopsBackendFunctionLogs",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
        )

        backend_fn = lambda_.Function(
            self,
            "KiroopsBackendFunction",
            runtime=runtime,
            architecture=architecture,
            handler="backend.lambda_handler.handler",
            memory_size=512,
            timeout=Duration.seconds(30),
            log_group=log_group,
            code=lambda_.Code.from_asset(
                _REPO_ROOT,
                bundling=cdk.BundlingOptions(
                    image=runtime.bundling_image,
                    command=bundling_command,
                ),
            ),
            environment={
                # Switch persistence to DynamoDB and point at the generated table.
                "KIROOPS_PERSISTENCE": "dynamodb",
                "KIROOPS_DDB_TABLE": table.table_name,
                # Bedrock Nova diagnosis configuration.
                "KIROOPS_LLM_MODEL_ID": model_id,
                "KIROOPS_LLM_REGION": bedrock_region,
                # CORS handled by the app layer too; keep both in sync.
                "KIROOPS_CORS_ORIGINS": cors_origins_raw,
            },
        )

        # ---- IAM: least privilege -------------------------------------------
        # DynamoDB: read/write ONLY on this table and its indexes (covers GSI1).
        table.grant_read_write_data(backend_fn)

        # Bedrock: scope InvokeModel to the Nova inference profile (account- and
        # region-scoped) and the underlying foundation model. No bedrock:* and no
        # Resource "*". Operators may need to adjust these ARNs if they select a
        # different Nova size via the "modelId" context (see README).
        #
        # The inference-profile id (e.g. "us.amazon.nova-lite-v1:0") maps to a
        # foundation-model id by dropping the cross-region "us." prefix.
        foundation_model_id = model_id.split(".", 1)[1] if model_id.startswith("us.") else model_id
        backend_fn.add_to_role_policy(
            iam.PolicyStatement(
                sid="KiroopsBedrockInvokeNova",
                effect=iam.Effect.ALLOW,
                actions=["bedrock:InvokeModel"],
                resources=[
                    # Cross-region inference profile in this account/region.
                    f"arn:aws:bedrock:{bedrock_region}:{self.account}:inference-profile/{model_id}",
                    # Underlying foundation model (region-agnostic partition ARN).
                    f"arn:aws:bedrock:*::foundation-model/{foundation_model_id}",
                ],
            )
        )

        # ---- HTTP API Gateway (proxy all routes to the Lambda) --------------
        proxy_integration = integrations.HttpLambdaIntegration(
            "KiroopsLambdaIntegration", handler=backend_fn
        )

        http_api = apigwv2.HttpApi(
            self,
            "KiroopsHttpApi",
            description="KiroOps backend HTTP API (proxies all FastAPI routes to Lambda).",
            cors_preflight=apigwv2.CorsPreflightOptions(
                allow_methods=[
                    apigwv2.CorsHttpMethod.GET,
                    apigwv2.CorsHttpMethod.POST,
                    apigwv2.CorsHttpMethod.PATCH,
                    apigwv2.CorsHttpMethod.OPTIONS,
                ],
                allow_origins=cors_origins,
                allow_headers=["*"],
            ),
        )

        # Route the root and every sub-path (ANY /{proxy+}) to the function so
        # all FastAPI routes (/health, /incidents, ...) are served.
        http_api.add_routes(
            path="/",
            methods=[apigwv2.HttpMethod.ANY],
            integration=proxy_integration,
        )
        http_api.add_routes(
            path="/{proxy+}",
            methods=[apigwv2.HttpMethod.ANY],
            integration=proxy_integration,
        )

        # ---- Outputs --------------------------------------------------------
        CfnOutput(
            self,
            "ApiEndpoint",
            value=http_api.api_endpoint,
            description="HTTP API base URL (set the frontend VITE_API_BASE_URL to this).",
        )
        CfnOutput(
            self,
            "TableName",
            value=table.table_name,
            description="DynamoDB single-table name (KIROOPS_DDB_TABLE).",
        )
        CfnOutput(
            self,
            "FunctionName",
            value=backend_fn.function_name,
            description="Backend Lambda function name.",
        )
