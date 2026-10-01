# KiroOps Infrastructure (AWS CDK v2, Python)

This directory contains an AWS CDK v2 app (Python) with two independent stacks:

- `KiroopsBackendStack` - the serverless backend (below).
- `KiroopsFrontendStack` - static hosting for the React SPA on S3 + CloudFront
  (see "Frontend hosting (S3 + CloudFront)" near the end).

Deploy them individually or together:

```
cdk deploy KiroopsBackendStack      # backend only
cdk deploy KiroopsFrontendStack     # frontend only
cdk deploy --all                    # both
```

## Backend stack

The `KiroopsBackendStack` provisions the KiroOps serverless backend:

- **DynamoDB** single-table (PK/SK) with a `GSI1` secondary index, on-demand
  billing, and point-in-time recovery.
- **Lambda** function running the FastAPI app (wrapped by Mangum) on the
  Python 3.12 ARM64 (Graviton) runtime.
- **HTTP API Gateway** that proxies every route to the Lambda.
- **Least-privilege IAM**: scoped DynamoDB access and a narrow
  `bedrock:InvokeModel` statement for Amazon Bedrock Nova.

> This app is infrastructure-as-code only. Nothing here deploys automatically.
> You run `cdk synth` / `cdk deploy` yourself after reviewing the stack.

## Prerequisites

- **Node.js + AWS CDK CLI** — `npm install -g aws-cdk` (CDK v2). Check with
  `cdk --version`.
- **Python 3.11+** — used both to run the CDK app and as the Lambda runtime
  target (3.12).
- **Docker** — the Lambda asset is bundled in a container so the packaged
  dependencies match the Lambda Linux/ARM64 runtime. Docker must be running
  for `cdk synth`/`cdk deploy` (not for `py_compile`).
- **A bootstrapped AWS account/region** — run `cdk bootstrap` once per
  account/region before the first deploy.
- **AWS credentials** — via an AWS profile or environment variables. The CDK
  CLI resolves the target account/region from the active profile
  (`CDK_DEFAULT_ACCOUNT` / `CDK_DEFAULT_REGION`).

## Install

```
cd infra
python -m venv .venv
# Windows:  .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
```

## Synthesize (no deploy)

```
cdk synth
```

This renders the CloudFormation template and performs the Lambda bundling. It
does not change any AWS resources.

## Deploy

```
cdk deploy
```

Optional context overrides (recommended for production):

```
# Tighten CORS to your frontend origin and/or pick a different Nova size:
cdk deploy -c corsOrigins=https://your-frontend.example.com -c modelId=us.amazon.nova-pro-v1:0
```

After deploy, read the stack **Outputs**:

- `ApiEndpoint` — set the frontend `VITE_API_BASE_URL` to this URL.
- `TableName` — the generated DynamoDB table name (`KIROOPS_DDB_TABLE`).
- `FunctionName` — the backend Lambda function name.

## Lambda packaging approach

The function is built with the **stable** `aws_lambda.Code.from_asset(...)` plus
Docker-based bundling in the Lambda ARM64 Python 3.12 build image. The bundling
command `pip install`s the FastAPI/Mangum runtime deps into the asset and copies
the `backend/` package in. Bundling inside the Lambda build image ensures
compiled wheels (pydantic-core, etc.) match the ARM64 Linux runtime.

- The asset `entry` is the **repo root** and the handler is
  `backend.lambda_handler.handler`, so the `backend` package is importable at
  the Lambda root.
- `fastapi`, `mangum`, and `pydantic` (which pulls `starlette`,
  `pydantic-core`) are installed into the package.
- `boto3`/`botocore` are **not** installed and are pruned from the bundle,
  because the Lambda runtime already provides them.

This uses only `aws-cdk-lib` (no alpha module). If you prefer the higher-level
`PythonFunction` construct instead, add `aws-cdk.aws-lambda-python-alpha` to
`requirements.txt` and swap the function definition — but the stable
`from_asset` + bundling approach here keeps the dependency surface minimal.

> **Docker is required** for `cdk synth`/`cdk deploy` because the asset is
> bundled in a container. Make sure Docker is running.

## DynamoDB removal policy (data safety)

The table uses `removal_policy=RETAIN`. **Deleting the stack does not delete the
table or its data** — the table is left in place and must be removed manually if
truly no longer needed. This prevents accidental loss of incident data. Point-
in-time recovery is also enabled for additional durability.

## Bedrock model access

- You must **enable model access** for the chosen Nova model in the Amazon
  Bedrock console (Model access) in the target region before diagnosis works.
  Enabling IAM `bedrock:InvokeModel` is necessary but not sufficient; account-
  level model access is a separate opt-in.
- The IAM policy scopes `bedrock:InvokeModel` to the Nova **inference profile**
  (`arn:aws:bedrock:<region>:<account>:inference-profile/us.amazon.nova-lite-v1:0`)
  and the underlying **foundation model**
  (`arn:aws:bedrock:*::foundation-model/amazon.nova-lite-v1:0`).
- If you pick a different Nova size via `-c modelId=...`, the policy ARNs are
  derived automatically, but double-check them against the Bedrock console if
  invocation is denied — inference-profile naming can vary by model and region.

## Relationship to local development

Local development stays on **SQLite** (`KIROOPS_PERSISTENCE` unset defaults to
`sqlite`); this stack sets `KIROOPS_PERSISTENCE=dynamodb` only in the deployed
Lambda environment. The backend code and tests are unchanged by this app.

## Frontend hosting (S3 + CloudFront)

The `KiroopsFrontendStack` serves the Vite + React SPA from a **private** S3
bucket behind a CloudFront distribution. The two stacks are independent: there
is no cross-stack reference. The frontend learns the backend URL at **build
time** through `VITE_API_BASE_URL`, which you set from the backend stack's
`ApiEndpoint` output.

### Deploy order

1. **Deploy the backend and note its API URL.**

   ```
   cd infra
   cdk deploy KiroopsBackendStack
   ```

   Copy the `ApiEndpoint` value from the stack Outputs.

2. **Build the frontend against that API URL.** The build must exist before the
   frontend stack deploys (the bucket upload reads `frontend/dist`).

   ```
   cd ../frontend
   # Windows (PowerShell):  $env:VITE_API_BASE_URL="https://abc123.execute-api.us-east-1.amazonaws.com"
   # macOS/Linux:           export VITE_API_BASE_URL="https://abc123.execute-api.us-east-1.amazonaws.com"
   npm install
   npm run build        # outputs frontend/dist/
   ```

3. **Deploy the frontend stack.**

   ```
   cd ../infra
   cdk deploy KiroopsFrontendStack
   ```

   Read the Outputs:

   - `SiteUrl` - the `https://` CloudFront URL for the app.
   - `DistributionDomainName` - the CloudFront domain (host only).
   - `SiteBucketName` - the S3 bucket holding the built assets.

### The `frontend/dist` must-exist requirement

The `BucketDeployment` that uploads the site is **guarded on the existence of
`frontend/dist`**:

- If `frontend/dist` exists at synth time, the stack adds the deployment and
  invalidates the CloudFront distribution (`distribution_paths=["/*"]`) so the
  new build is served immediately.
- If `frontend/dist` is **missing** (you have not run `npm run build`), the
  stack **skips** the deployment and emits a build-first warning. This keeps
  `cdk synth` working without a build, but a `cdk deploy` in that state creates
  the bucket and distribution with **no uploaded content**. Build first, then
  deploy, to populate the site.

### Design notes

- **Private bucket + Origin Access Control (OAC).** The bucket blocks all
  public access (`BLOCK_ALL`), uses S3-managed encryption, and enforces SSL.
  CloudFront reaches it through OAC via
  `S3BucketOrigin.with_origin_access_control(bucket)` (available in
  aws-cdk-lib >= 2.156; the installed version satisfies this, so OAC is used
  rather than a legacy Origin Access Identity). The bucket is never public.
- **SPA error-response mapping.** CloudFront maps both `403` and `404` to
  `/index.html` with a `200` response code, so client-side React Router deep
  links resolve instead of returning an error for a key that is not a real S3
  object.
- **RETAIN removal policy.** The bucket uses `RemovalPolicy.RETAIN`: deleting
  the stack leaves the bucket and its objects in place (it is not auto-emptied).
  A static-site bucket is low-risk, but RETAIN avoids surprise data loss; delete
  it manually if you truly no longer need it.
- **Price class.** The distribution uses `PriceClass.PRICE_CLASS_100` (North
  America + Europe edge locations), the cheapest tier. Raise it if you need
  edge presence in other regions.

### CORS in production

Set the backend's `KIROOPS_CORS_ORIGINS` to the CloudFront domain so the browser
app is allowed to call the API. On the backend stack:

```
cdk deploy KiroopsBackendStack -c corsOrigins=https://<DistributionDomainName>
```

Using `*` is fine for local development, but production should scope CORS to the
exact CloudFront origin.
