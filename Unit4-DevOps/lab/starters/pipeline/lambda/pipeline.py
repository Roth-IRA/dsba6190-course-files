"""
pipeline.py — Serverless DevOps Pipeline Lambda Handler
DSBA 6190 — Unit 4: DevOps on AWS

Triggered by EventBridge when CodeCommit fires a referenceUpdated event.
Reads template.yaml from the repo, validates it, then creates or updates
a CloudFormation stack.  Results are logged to S3 and published to SNS.

Environment variables
---------------------
STACK_NAME       : Name of the CloudFormation stack to manage
ARTIFACT_BUCKET  : S3 bucket used for result logs
SNS_TOPIC_ARN    : ARN of the SNS topic for notifications
"""

import base64
import json
import logging
import os
import time
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# AWS clients (created once at module level for Lambda container reuse)
# ---------------------------------------------------------------------------
codecommit = boto3.client("codecommit")
cloudformation = boto3.client("cloudformation")
s3 = boto3.client("s3")
sns = boto3.client("sns")
iam = boto3.client("iam")

# ---------------------------------------------------------------------------
# CloudFormation stack states that cannot be updated in-place
# ---------------------------------------------------------------------------
FAILED_STATES = {
    "ROLLBACK_COMPLETE",
    "ROLLBACK_FAILED",
    "CREATE_FAILED",
    "DELETE_FAILED",
    "UPDATE_ROLLBACK_FAILED",
}

# States that indicate an operation is already in progress
IN_PROGRESS_STATES = {
    "CREATE_IN_PROGRESS",
    "DELETE_IN_PROGRESS",
    "UPDATE_IN_PROGRESS",
    "UPDATE_ROLLBACK_IN_PROGRESS",
    "ROLLBACK_IN_PROGRESS",
    "REVIEW_IN_PROGRESS",
}


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def get_env(name: str) -> str:
    """Return a required environment variable or raise."""
    value = os.environ.get(name)
    if not value:
        raise EnvironmentError(f"Required environment variable '{name}' is not set.")
    return value


def extract_student_prefix(stack_name: str) -> str:
    """
    Extract the student prefix from a stack name.

    Convention: <course>-<prefix>-<suffix>  e.g. dsba6190-abc-app → 'abc'
    Falls back to the full stack name when the pattern doesn't match.
    """
    parts = stack_name.split("-")
    if len(parts) >= 3:
        return parts[1]
    return stack_name


def build_result(status: str, message: str, details: dict | None = None) -> dict:
    """Build a structured result dictionary."""
    return {
        "status": status,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "details": details or {},
    }


# ---------------------------------------------------------------------------
# CodeCommit helpers
# ---------------------------------------------------------------------------

def get_template_from_repo(repo_name: str, branch: str) -> str | None:
    """
    Fetch template.yaml content from a CodeCommit repository.

    Returns the file content as a string, or None if the file does not exist.
    """
    try:
        response = codecommit.get_file(
            repositoryName=repo_name,
            commitSpecifier=branch,
            filePath="template.yaml",
        )
        # Content is base64-encoded bytes
        raw = response["fileContent"]
        if isinstance(raw, (bytes, bytearray)):
            return raw.decode("utf-8")
        # SDK may already decode in some versions
        return base64.b64decode(raw).decode("utf-8")
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code in ("FileDoesNotExistException", "FileTooLargeException",
                    "CommitDoesNotExistException", "PathDoesNotExistException"):
            logger.warning(
                "template.yaml not found in %s@%s: %s", repo_name, branch, code
            )
            return None
        raise


# ---------------------------------------------------------------------------
# CloudFormation helpers
# ---------------------------------------------------------------------------

def get_lab_role_arn() -> str:
    """Look up the ARN of the LabRole IAM role."""
    response = iam.get_role(RoleName="LabRole")
    return response["Role"]["Arn"]


def get_stack_status(stack_name: str) -> str | None:
    """
    Return the current status string of a CloudFormation stack,
    or None if the stack does not exist.
    """
    try:
        response = cloudformation.describe_stacks(StackName=stack_name)
        stacks = response.get("Stacks", [])
        if stacks:
            return stacks[0]["StackStatus"]
        return None
    except ClientError as exc:
        if "does not exist" in str(exc):
            return None
        raise


def delete_stack_and_wait(stack_name: str) -> None:
    """Delete a CloudFormation stack and poll until deletion completes."""
    logger.info("Deleting stack %s before recreation.", stack_name)
    cloudformation.delete_stack(StackName=stack_name)

    waiter = cloudformation.get_waiter("stack_delete_complete")
    waiter.wait(
        StackName=stack_name,
        WaiterConfig={"Delay": 15, "MaxAttempts": 80},
    )
    logger.info("Stack %s deleted successfully.", stack_name)


def get_stack_events(stack_name: str) -> list[dict]:
    """Return the most recent CloudFormation stack events (up to 50)."""
    try:
        response = cloudformation.describe_stack_events(StackName=stack_name)
        events = response.get("StackEvents", [])
        # Return most recent events first, truncated for manageability
        return [
            {
                "timestamp": e["Timestamp"].isoformat(),
                "resource": e.get("LogicalResourceId", ""),
                "status": e.get("ResourceStatus", ""),
                "reason": e.get("ResourceStatusReason", ""),
            }
            for e in events[:50]
        ]
    except ClientError:
        return []


def validate_template(template_body: str) -> dict:
    """
    Call CloudFormation ValidateTemplate.

    Returns the validation response on success.
    Raises ClientError on validation failure.
    """
    return cloudformation.validate_template(TemplateBody=template_body)


def deploy_stack(
    stack_name: str,
    template_body: str,
    student_prefix: str,
    artifact_bucket: str,
    lab_role_arn: str,
) -> str:
    """
    Create or update a CloudFormation stack.

    Returns one of: CREATED, UPDATED, NO_CHANGES
    Raises ClientError for genuine failures.
    """
    # Build parameters list — only include parameters that exist in the template
    all_params = {
        "StudentPrefix": student_prefix,
        "ArtifactBucket": artifact_bucket,
    }
    # Discover which parameters the template declares
    validation = cloudformation.validate_template(TemplateBody=template_body)
    declared = {p["ParameterKey"] for p in validation.get("Parameters", [])}
    parameters = [
        {"ParameterKey": k, "ParameterValue": v}
        for k, v in all_params.items()
        if k in declared
    ]
    logger.info("Passing parameters: %s", [p["ParameterKey"] for p in parameters])
    capabilities = ["CAPABILITY_IAM", "CAPABILITY_NAMED_IAM", "CAPABILITY_AUTO_EXPAND"]

    current_status = get_stack_status(stack_name)
    logger.info("Current stack status for %s: %s", stack_name, current_status)

    # Delete stacks stuck in a terminal-failed state before attempting create
    if current_status in FAILED_STATES:
        delete_stack_and_wait(stack_name)
        current_status = None

    if current_status is None:
        # Create new stack
        logger.info("Creating stack %s.", stack_name)
        cloudformation.create_stack(
            StackName=stack_name,
            TemplateBody=template_body,
            Parameters=parameters,
            Capabilities=capabilities,
            RoleARN=lab_role_arn,
            OnFailure="ROLLBACK",
        )
        waiter = cloudformation.get_waiter("stack_create_complete")
        waiter.wait(
            StackName=stack_name,
            WaiterConfig={"Delay": 15, "MaxAttempts": 80},
        )
        return "CREATED"
    else:
        # Update existing stack
        logger.info("Updating stack %s.", stack_name)
        try:
            cloudformation.update_stack(
                StackName=stack_name,
                TemplateBody=template_body,
                Parameters=parameters,
                Capabilities=capabilities,
                RoleARN=lab_role_arn,
            )
            waiter = cloudformation.get_waiter("stack_update_complete")
            waiter.wait(
                StackName=stack_name,
                WaiterConfig={"Delay": 15, "MaxAttempts": 80},
            )
            return "UPDATED"
        except ClientError as exc:
            msg = exc.response["Error"]["Message"]
            if "No updates are to be performed" in msg:
                logger.info("No changes detected for stack %s.", stack_name)
                return "NO_CHANGES"
            raise


# ---------------------------------------------------------------------------
# S3 / SNS helpers
# ---------------------------------------------------------------------------

def write_result_to_s3(bucket: str, stack_name: str, result: dict) -> str:
    """
    Write a JSON result object to S3.

    Key pattern: pipeline-results/<stack-name>/<ISO-timestamp>.json
    Returns the S3 key.
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    key = f"pipeline-results/{stack_name}/{ts}.json"
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(result, indent=2, default=str).encode("utf-8"),
        ContentType="application/json",
    )
    logger.info("Result written to s3://%s/%s", bucket, key)
    return key


def publish_to_sns(topic_arn: str, subject: str, result: dict) -> None:
    """Publish a summary message to an SNS topic."""
    message = (
        f"Status : {result['status']}\n"
        f"Message: {result['message']}\n"
        f"Time   : {result['timestamp']}\n"
    )
    if result.get("details"):
        message += "\nDetails:\n" + json.dumps(result["details"], indent=2, default=str)

    sns.publish(
        TopicArn=topic_arn,
        Subject=subject[:100],  # SNS subject limit is 100 characters
        Message=message,
    )
    logger.info("Published to SNS topic %s with subject: %s", topic_arn, subject)


# ---------------------------------------------------------------------------
# Main Lambda handler
# ---------------------------------------------------------------------------

def handler(event: dict, context) -> dict:  # noqa: ANN001
    """
    Lambda entry point.

    Expected event structure (EventBridge CodeCommit referenceUpdated):
    {
        "source": "aws.codecommit",
        "detail-type": "CodeCommit Repository State Change",
        "detail": {
            "event": "referenceUpdated",
            "repositoryName": "<name>",
            "referenceName": "<branch>",
            "referenceType": "branch",
            ...
        }
    }
    """
    logger.info("Pipeline handler invoked. Event: %s", json.dumps(event, default=str))

    # -- Read environment variables ------------------------------------------
    try:
        stack_name = get_env("STACK_NAME")
        artifact_bucket = get_env("ARTIFACT_BUCKET")
        sns_topic_arn = get_env("SNS_TOPIC_ARN")
    except EnvironmentError as exc:
        logger.error("Configuration error: %s", exc)
        raise

    # -- Parse the EventBridge event -----------------------------------------
    detail = event.get("detail", {})
    repo_name = detail.get("repositoryName", "")
    branch = detail.get("referenceName", "")

    logger.info(
        "Event details — repo: %s, branch: %s",
        repo_name, branch,
    )

    # Only act on pushes to the main branch
    if branch != "main":
        logger.info("Ignoring push to non-main branch: %s", branch)
        return {"statusCode": 200, "body": f"Ignored: branch '{branch}' is not main"}

    if not repo_name:
        logger.error("repositoryName missing from event detail.")
        return {"statusCode": 400, "body": "Missing repositoryName"}

    # -- Derive student prefix -----------------------------------------------
    student_prefix = extract_student_prefix(stack_name)
    logger.info("Student prefix: %s", student_prefix)

    # -- Fetch template.yaml from CodeCommit ---------------------------------
    logger.info("Fetching template.yaml from %s@%s", repo_name, branch)
    try:
        template_body = get_template_from_repo(repo_name, branch)
    except ClientError as exc:
        logger.error("Unexpected error reading from CodeCommit: %s", exc)
        result = build_result(
            "CODECOMMIT_ERROR",
            f"Could not read from CodeCommit repository '{repo_name}'.",
            {"error": str(exc)},
        )
        _finalize(result, stack_name, artifact_bucket, sns_topic_arn,
                  subject="Pipeline Error: CodeCommit read failure")
        return {"statusCode": 500, "body": result["status"]}

    if template_body is None:
        logger.warning("No template.yaml found in %s@%s. Exiting cleanly.", repo_name, branch)
        result = build_result(
            "NO_TEMPLATE_FOUND",
            f"template.yaml was not found in repository '{repo_name}' on branch '{branch}'. "
            "Push a template.yaml to trigger a deployment.",
        )
        _finalize(result, stack_name, artifact_bucket, sns_topic_arn,
                  subject=f"Pipeline Notice: No template.yaml in {repo_name}")
        return {"statusCode": 200, "body": result["status"]}

    logger.info("Fetched template.yaml (%d bytes).", len(template_body))

    # -- Validate template ----------------------------------------------------
    logger.info("Validating CloudFormation template.")
    try:
        validate_template(template_body)
        logger.info("Template validation passed.")
    except ClientError as exc:
        error_msg = exc.response["Error"]["Message"]
        logger.error("Template validation failed: %s", error_msg)
        result = build_result(
            "VALIDATION_FAILED",
            f"CloudFormation template validation failed: {error_msg}",
            {"validationError": error_msg},
        )
        _finalize(result, stack_name, artifact_bucket, sns_topic_arn,
                  subject=f"Pipeline FAILED: Validation error in {repo_name}")
        return {"statusCode": 400, "body": result["status"]}

    # -- Look up LabRole ARN -------------------------------------------------
    try:
        lab_role_arn = get_lab_role_arn()
        logger.info("LabRole ARN: %s", lab_role_arn)
    except ClientError as exc:
        logger.error("Could not retrieve LabRole: %s", exc)
        result = build_result(
            "IAM_ERROR",
            "Could not look up the LabRole IAM role. "
            "Ensure the role exists and the Lambda has iam:GetRole permission.",
            {"error": str(exc)},
        )
        _finalize(result, stack_name, artifact_bucket, sns_topic_arn,
                  subject="Pipeline Error: IAM role lookup failure")
        return {"statusCode": 500, "body": result["status"]}

    # -- Deploy the CloudFormation stack -------------------------------------
    logger.info("Deploying stack %s.", stack_name)
    try:
        operation = deploy_stack(
            stack_name=stack_name,
            template_body=template_body,
            student_prefix=student_prefix,
            artifact_bucket=artifact_bucket,
            lab_role_arn=lab_role_arn,
        )
        logger.info("Stack operation completed: %s", operation)

        status_map = {
            "CREATED": ("DEPLOY_SUCCESS", f"Stack '{stack_name}' created successfully."),
            "UPDATED": ("DEPLOY_SUCCESS", f"Stack '{stack_name}' updated successfully."),
            "NO_CHANGES": ("NO_CHANGES", f"Stack '{stack_name}' is already up to date — no changes were deployed."),
        }
        status, message = status_map.get(
            operation,
            ("DEPLOY_SUCCESS", f"Stack operation '{operation}' completed for '{stack_name}'.")
        )

        result = build_result(
            status,
            message,
            {"stackName": stack_name, "operation": operation, "studentPrefix": student_prefix},
        )
        subject = (
            f"Pipeline SUCCESS: {stack_name} {operation.lower()}"
            if status == "DEPLOY_SUCCESS"
            else f"Pipeline: {stack_name} no changes"
        )
        _finalize(result, stack_name, artifact_bucket, sns_topic_arn, subject=subject)
        return {"statusCode": 200, "body": result["status"]}

    except ClientError as exc:
        error_msg = exc.response["Error"]["Message"]
        logger.error("Stack operation failed: %s", error_msg)

        # Capture stack events for diagnosis
        events = get_stack_events(stack_name)

        result = build_result(
            "DEPLOY_FAILED",
            f"CloudFormation stack operation failed for '{stack_name}': {error_msg}",
            {
                "stackName": stack_name,
                "error": error_msg,
                "studentPrefix": student_prefix,
                "recentEvents": events,
            },
        )
        _finalize(result, stack_name, artifact_bucket, sns_topic_arn,
                  subject=f"Pipeline FAILED: {stack_name} deployment error")
        return {"statusCode": 500, "body": result["status"]}

    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Unexpected error during stack deployment.")
        result = build_result(
            "DEPLOY_FAILED",
            f"Unexpected error during deployment of '{stack_name}': {exc}",
            {"stackName": stack_name, "error": str(exc)},
        )
        _finalize(result, stack_name, artifact_bucket, sns_topic_arn,
                  subject=f"Pipeline FAILED: {stack_name} unexpected error")
        return {"statusCode": 500, "body": result["status"]}


# ---------------------------------------------------------------------------
# Internal helper — always write to S3 and publish to SNS
# ---------------------------------------------------------------------------

def _finalize(
    result: dict,
    stack_name: str,
    artifact_bucket: str,
    sns_topic_arn: str,
    subject: str,
) -> None:
    """
    Best-effort: write result JSON to S3 and publish summary to SNS.
    Errors here are logged but do not propagate (so the Lambda can still
    return a meaningful HTTP status to EventBridge).
    """
    try:
        s3_key = write_result_to_s3(artifact_bucket, stack_name, result)
        result["details"]["s3Key"] = s3_key
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Failed to write result to S3: %s", exc)

    try:
        publish_to_sns(sns_topic_arn, subject, result)
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Failed to publish result to SNS: %s", exc)
