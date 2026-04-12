# =============================================================
# DSBA 6190 — DevOps Lab: Variables
# =============================================================
# TODO: Complete each variable block with the correct type
#       and a sensible default where indicated.
# =============================================================

variable "student_prefix" {
  description = "Unique student identifier (e.g., initials). Used in resource names."
  # TODO: Add the type (hint: it's a simple type)
}

variable "aws_region" {
  description = "AWS region for all resources"
  # TODO: Add the type and a default value of "us-east-1"
}
