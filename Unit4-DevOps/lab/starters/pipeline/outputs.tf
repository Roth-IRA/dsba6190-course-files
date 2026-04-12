# =============================================================
# DSBA 6190 — DevOps Lab: Outputs
# =============================================================
# TODO: Complete each output block with the correct value
#       expression referencing the appropriate resource attribute.
# =============================================================

output "repo_clone_url_http" {
  description = "HTTPS clone URL for the CodeCommit repository"
  # TODO: Set value (hint: aws_codecommit_repository.infra_repo.clone_url_http)
}

output "lambda_function_name" {
  description = "Name of the pipeline Lambda function"
  # TODO: Set value
}

output "sns_topic_arn" {
  description = "ARN of the pipeline notifications SNS topic"
  # TODO: Set value
}

output "artifact_bucket" {
  description = "Name of the S3 bucket for pipeline artifacts and logs"
  # TODO: Set value
}

output "stack_name" {
  description = "Name of the CloudFormation stack the pipeline deploys"
  # TODO: Set value to "dsba6190-<student_prefix>-app"
}
