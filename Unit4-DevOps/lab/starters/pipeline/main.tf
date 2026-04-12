# =============================================================
# DSBA 6190 — DevOps Lab: Main Configuration
# =============================================================
# Instructions
# ------------
# The terraform {}, provider "aws" {}, and all data {} blocks
# below are COMPLETE — do not modify them.
#
# For every resource block, replace each TODO comment with the
# correct Terraform argument.  Terraform docs links are provided
# next to each resource to help you look up argument names and
# expected values.
# =============================================================

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# ---------------------------------------------------------------------------
# Data sources  (COMPLETE — do not modify)
# ---------------------------------------------------------------------------

data "aws_caller_identity" "current" {}

data "aws_iam_role" "lab_role" {
  name = "LabRole"
}

data "archive_file" "lambda_zip" {
  type        = "zip"
  source_file = "${path.module}/lambda/pipeline.py"
  output_path = "${path.module}/lambda/pipeline.zip"
}

# ---------------------------------------------------------------------------
# CodeCommit repository
# Docs: https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/codecommit_repository
# ---------------------------------------------------------------------------

resource "aws_codecommit_repository" "infra_repo" {
  # TODO: repository_name — use the pattern "dsba6190-<student_prefix>-infra"
  # TODO: description     — brief description that mentions the student prefix
}

# ---------------------------------------------------------------------------
# S3 artifact bucket
# Docs: https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket
# ---------------------------------------------------------------------------

resource "aws_s3_bucket" "artifacts" {
  # TODO: bucket — use the pattern "dsba6190-<student_prefix>-pipeline-artifacts"
  force_destroy = true  # Allows terraform destroy to work even when bucket has objects
}

# Docs: https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_versioning
resource "aws_s3_bucket_versioning" "artifacts" {
  # TODO: bucket — reference the S3 bucket created above
  #               (hint: aws_s3_bucket.artifacts.id)

  # TODO: Add a versioning_configuration block with status = "Enabled"
}

# Docs: https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_server_side_encryption_configuration
resource "aws_s3_bucket_server_side_encryption_configuration" "artifacts" {
  # TODO: bucket — reference the S3 bucket created above
  #               (hint: aws_s3_bucket.artifacts.id)

  # TODO: Add a rule block containing an apply_server_side_encryption_by_default
  #       block with sse_algorithm = "AES256"
}

# Docs: https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_policy
resource "aws_s3_bucket_policy" "artifacts_policy" {
  # TODO: bucket — reference the S3 bucket created above
  #               (hint: aws_s3_bucket.artifacts.id)

  # TODO: policy — use jsonencode() to build a policy document with four statements:
  #
  #   Statement 1 — Sid: "CloudTrailGetBucketAcl"
  #     Effect: "Allow"
  #     Principal: { Service: "cloudtrail.amazonaws.com" }
  #     Action:   "s3:GetBucketAcl"
  #     Resource: <bucket ARN>  (hint: aws_s3_bucket.artifacts.arn)
  #
  #   Statement 2 — Sid: "CloudTrailPutObject"
  #     Effect: "Allow"
  #     Principal: { Service: "cloudtrail.amazonaws.com" }
  #     Action:   "s3:PutObject"
  #     Resource: "<bucket ARN>/cloudtrail/*"
  #     Condition: { StringEquals: { "s3:x-amz-acl": "bucket-owner-full-control" } }
  #
  #   Statement 3 — Sid: "ConfigGetBucketAcl"
  #     Effect: "Allow"
  #     Principal: { Service: "config.amazonaws.com" }
  #     Action:   "s3:GetBucketAcl"
  #     Resource: <bucket ARN>
  #
  #   Statement 4 — Sid: "ConfigPutObject"
  #     Effect: "Allow"
  #     Principal: { Service: "config.amazonaws.com" }
  #     Action:   "s3:PutObject"
  #     Resource: "<bucket ARN>/config/*"
  #     Condition: { StringEquals: { "s3:x-amz-acl": "bucket-owner-full-control" } }
}

# ---------------------------------------------------------------------------
# SNS topic
# Docs: https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/sns_topic
# ---------------------------------------------------------------------------

resource "aws_sns_topic" "pipeline_notifications" {
  # TODO: name — use the pattern "dsba6190-<student_prefix>-pipeline-notifications"
}

# ---------------------------------------------------------------------------
# Lambda function
# Docs: https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lambda_function
# ---------------------------------------------------------------------------

resource "aws_lambda_function" "pipeline" {
  # TODO: function_name — use the pattern "dsba6190-<student_prefix>-pipeline"
  # TODO: description   — brief description that mentions the student prefix

  # TODO: filename         — path to the zip produced by data.archive_file.lambda_zip
  #                          (hint: data.archive_file.lambda_zip.output_path)
  # TODO: source_code_hash — base64-encoded SHA256 of the zip for change detection
  #                          (hint: data.archive_file.lambda_zip.output_base64sha256)

  # TODO: runtime — "python3.12"
  # TODO: handler — "pipeline.handler"
  # TODO: role    — ARN of the LabRole from the data source
  #                 (hint: data.aws_iam_role.lab_role.arn)

  # TODO: timeout     — 120 (seconds)
  # TODO: memory_size — 256 (MB)

  # TODO: Add an environment block with a variables map containing:
  #   STACK_NAME      = "dsba6190-<student_prefix>-app"
  #   ARTIFACT_BUCKET = <S3 bucket id>   (hint: aws_s3_bucket.artifacts.id)
  #   SNS_TOPIC_ARN   = <SNS topic ARN>  (hint: aws_sns_topic.pipeline_notifications.arn)
}

# ---------------------------------------------------------------------------
# EventBridge rule — CodeCommit push to main
# Docs: https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_event_rule
# ---------------------------------------------------------------------------

resource "aws_cloudwatch_event_rule" "codecommit_push" {
  # TODO: name        — use the pattern "dsba6190-<student_prefix>-codecommit-push"
  # TODO: description — short description of what this rule does

  # TODO: event_pattern — use jsonencode() to match CodeCommit push events:
  #   source      = ["aws.codecommit"]
  #   detail-type = ["CodeCommit Repository State Change"]
  #   detail = {
  #     event          = ["referenceCreated", "referenceUpdated"]
  #     referenceName  = ["main"]
  #     repositoryName = [<repo name>]  (hint: aws_codecommit_repository.infra_repo.repository_name)
  #   }
}

# Docs: https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_event_target
resource "aws_cloudwatch_event_target" "lambda_target" {
  # TODO: rule      — name of the EventBridge rule created above
  #                   (hint: aws_cloudwatch_event_rule.codecommit_push.name)
  # TODO: target_id — a unique string ID for this target (e.g., "PipelineLambda")
  # TODO: arn       — ARN of the Lambda function to invoke
  #                   (hint: aws_lambda_function.pipeline.arn)
}

# ---------------------------------------------------------------------------
# Lambda permission — allow EventBridge to invoke the function
# Docs: https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lambda_permission
# ---------------------------------------------------------------------------

resource "aws_lambda_permission" "eventbridge_invoke" {
  # TODO: statement_id  — unique identifier for this permission statement
  #                       (e.g., "AllowExecutionFromEventBridge")
  # TODO: action        — "lambda:InvokeFunction"
  # TODO: function_name — name of the Lambda function
  #                       (hint: aws_lambda_function.pipeline.function_name)
  # TODO: principal     — "events.amazonaws.com"
  # TODO: source_arn    — ARN of the EventBridge rule that is allowed to invoke
  #                       (hint: aws_cloudwatch_event_rule.codecommit_push.arn)
}
