"""KiroOps frontend hosting stack (CDK v2, Python).

Provisions static hosting for the Vite + React single-page app, following AWS
Well-Architected and least-privilege principles:

- A private S3 bucket for the built site: all public access blocked,
  S3-managed encryption at rest, SSL enforced in-transit, and a RETAIN removal
  policy so a stack delete never discards the uploaded objects.
- A CloudFront distribution that serves the bucket privately via Origin Access
  Control (OAC) so the bucket is never public. HTTPS is enforced
  (REDIRECT_TO_HTTPS), ``index.html`` is the default root object, and 403/404
  responses are rewritten to ``/index.html`` with a 200 so client-side SPA
  routes resolve. Price class is PRICE_CLASS_100 (North America + Europe edge
  locations) to keep cost down.
- A BucketDeployment that uploads ``frontend/dist`` and invalidates the
  distribution. The deployment is only added when the build output exists at
  synth time, so ``cdk synth`` succeeds without a prior build; when it is
  missing the stack annotates a clear "build first" message instead of failing.

This stack is intentionally independent of the backend stack so each can deploy
on its own. The backend API URL is injected into the frontend at build time via
``VITE_API_BASE_URL`` (set from the backend stack's ``ApiEndpoint`` output), so
no cross-stack reference is required here.

No secrets, endpoints, or model ids are hard-coded. This file is
infrastructure-as-code only and performs no AWS calls at author time.
"""

from __future__ import annotations

import os

from aws_cdk import (
    Annotations,
    CfnOutput,
    RemovalPolicy,
    Stack,
)
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_deployment as s3deploy
from constructs import Construct

# This stack package lives at infra/kiroops_frontend/. The CDK app is run from
# infra/, so the built site is a sibling of infra/ at ../frontend/dist. We
# resolve an absolute path for the synth-time existence guard, but hand
# Source.asset a path relative to the CDK app working directory (infra/).
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_INFRA_DIR = os.path.dirname(_THIS_DIR)
_REPO_ROOT = os.path.dirname(_INFRA_DIR)

# Absolute path used only to check whether a build exists at synth time.
_DIST_ABS_PATH = os.path.join(_REPO_ROOT, "frontend", "dist")
# Path handed to Source.asset, relative to infra/ (the CDK app cwd).
_DIST_REL_PATH = os.path.join("..", "frontend", "dist")


class KiroopsFrontendStack(Stack):
    """Static site hosting: private S3 bucket + CloudFront (OAC) + deploy."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ---- S3 bucket (private origin) -------------------------------------
        # Block ALL public access, encrypt at rest with S3-managed keys, and
        # enforce TLS for in-transit requests. RETAIN keeps objects on stack
        # delete (see README) - the bucket is NOT auto-emptied, so a static
        # site re-deploy is cheap but accidental data loss is avoided.
        site_bucket = s3.Bucket(
            self,
            "KiroopsSiteBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.RETAIN,
        )

        # ---- CloudFront distribution (private origin via OAC) ---------------
        # aws-cdk-lib >= 2.156 provides S3BucketOrigin.with_origin_access_control,
        # which wires Origin Access Control and grants the distribution read
        # access to the bucket while keeping public access fully blocked. The
        # installed aws-cdk-lib (>= 2.243) includes this construct, so OAC is
        # used (no legacy Origin Access Identity).
        site_origin = origins.S3BucketOrigin.with_origin_access_control(site_bucket)

        distribution = cloudfront.Distribution(
            self,
            "KiroopsSiteDistribution",
            comment="KiroOps frontend static site (private S3 origin via OAC).",
            default_root_object="index.html",
            default_behavior=cloudfront.BehaviorOptions(
                origin=site_origin,
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                # Default managed cache policy is appropriate for a static SPA.
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
            ),
            # SPA deep-link support: S3 returns 403 (OAC, object missing) or 404
            # for unknown keys. Rewrite both to index.html with a 200 so the
            # React client-side router can resolve the route.
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_http_status=200,
                    response_page_path="/index.html",
                ),
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                ),
            ],
            # NA + EU edge locations only; cheapest tier that fits this app.
            price_class=cloudfront.PriceClass.PRICE_CLASS_100,
        )

        # ---- Deploy the built site (guarded on dist existence) --------------
        # frontend/dist may be absent at synth time if the app has not been
        # built. Guard the BucketDeployment so `cdk synth` still works without a
        # build; when missing, annotate a clear "build first" warning instead of
        # hard-failing. When present, upload the site and invalidate the whole
        # distribution so the new build is served immediately.
        if os.path.isdir(_DIST_ABS_PATH):
            s3deploy.BucketDeployment(
                self,
                "KiroopsSiteDeployment",
                sources=[s3deploy.Source.asset(_DIST_REL_PATH)],
                destination_bucket=site_bucket,
                distribution=distribution,
                distribution_paths=["/*"],
            )
        else:
            Annotations.of(self).add_warning(
                "frontend/dist not found - skipping site upload. Build the "
                "frontend first (cd ../frontend; set VITE_API_BASE_URL to the "
                "backend ApiEndpoint; npm install; npm run build), then "
                "redeploy this stack to upload the site."
            )

        # ---- Outputs --------------------------------------------------------
        CfnOutput(
            self,
            "SiteUrl",
            value=f"https://{distribution.distribution_domain_name}",
            description="CloudFront distribution URL for the KiroOps frontend.",
        )
        CfnOutput(
            self,
            "DistributionDomainName",
            value=distribution.distribution_domain_name,
            description="CloudFront distribution domain name (the site host).",
        )
        CfnOutput(
            self,
            "SiteBucketName",
            value=site_bucket.bucket_name,
            description="S3 bucket holding the built frontend assets.",
        )
