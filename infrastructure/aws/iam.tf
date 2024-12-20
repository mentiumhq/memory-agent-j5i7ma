# Memory Agent IAM Configuration
# Version: ~> 1.0
# Purpose: Defines IAM roles and policies for secure ECS task execution and runtime permissions

terraform {
  required_version = "~> 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# Get current AWS account ID for security policies
data "aws_caller_identity" "current" {}

# ECS Task Execution Role
# Allows ECS to pull container images and publish logs
resource "aws_iam_role" "ecs_execution" {
  name = "${var.app_name}-${var.environment}-ecs-execution"
  path = "/service-roles/"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
      Action = "sts:AssumeRole"
      Condition = {
        StringEquals = {
          "aws:SourceAccount" = data.aws_caller_identity.current.account_id
        }
      }
    }]
  })

  # Merge common tags with security-specific tags
  tags = merge(local.common_tags, {
    SecurityClass    = "High"
    ComplianceScope = "PCI"
    DataSensitivity = "Confidential"
    ServiceRole     = "ECSExecution"
  })
}

# Attach AWS managed policy for ECS task execution
resource "aws_iam_role_policy_attachment" "ecs_execution_policy" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# ECS Task Role
# Runtime permissions for the application
resource "aws_iam_role" "ecs_task" {
  name = "${var.app_name}-${var.environment}-ecs-task"
  path = "/service-roles/"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
      Action = "sts:AssumeRole"
      Condition = {
        StringEquals = {
          "aws:SourceAccount" = data.aws_caller_identity.current.account_id
        }
      }
    }]
  })

  tags = merge(local.common_tags, {
    SecurityClass    = "High"
    ComplianceScope = "PCI"
    DataSensitivity = "Confidential"
    ServiceRole     = "ECSTask"
  })
}

# S3 Access Policy
# Enforces encryption requirements for document storage
resource "aws_iam_policy" "s3_access" {
  name        = "${var.app_name}-${var.environment}-s3-access"
  description = "Allows encrypted access to document storage bucket with strict controls"
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket",
          "s3:DeleteObject"
        ]
        Resource = [
          aws_s3_bucket.document_storage.arn,
          "${aws_s3_bucket.document_storage.arn}/*"
        ]
        Condition = {
          StringEquals = {
            "s3:x-amz-server-side-encryption" = "aws:kms"
            "s3:x-amz-server-side-encryption-aws-kms-key-id" = aws_kms_key.document_kms_key.arn
          }
        }
      }
    ]
  })

  tags = merge(local.common_tags, {
    SecurityClass = "High"
    PolicyType   = "CustomManaged"
  })
}

# KMS Access Policy
# Restricts encryption operations to specific services and conditions
resource "aws_iam_policy" "kms_access" {
  name        = "${var.app_name}-${var.environment}-kms-access"
  description = "Allows KMS encryption/decryption operations with strict service restrictions"
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey",
          "kms:DescribeKey"
        ]
        Resource = aws_kms_key.document_kms_key.arn
        Condition = {
          StringEquals = {
            "kms:ViaService" = "s3.${var.aws_region}.amazonaws.com"
          }
        }
      }
    ]
  })

  tags = merge(local.common_tags, {
    SecurityClass = "High"
    PolicyType   = "CustomManaged"
  })
}

# CloudWatch Logs Policy
# Enables secure log management with encryption
resource "aws_iam_policy" "cloudwatch_logs" {
  name        = "${var.app_name}-${var.environment}-cloudwatch-logs"
  description = "Allows CloudWatch logs management with encryption"
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/ecs/${var.app_name}-${var.environment}*:*"
      }
    ]
  })

  tags = merge(local.common_tags, {
    SecurityClass = "High"
    PolicyType   = "CustomManaged"
  })
}

# Attach policies to ECS Task Role
resource "aws_iam_role_policy_attachment" "ecs_task_s3" {
  role       = aws_iam_role.ecs_task.name
  policy_arn = aws_iam_policy.s3_access.arn
}

resource "aws_iam_role_policy_attachment" "ecs_task_kms" {
  role       = aws_iam_role.ecs_task.name
  policy_arn = aws_iam_policy.kms_access.arn
}

resource "aws_iam_role_policy_attachment" "ecs_task_cloudwatch" {
  role       = aws_iam_role.ecs_task.name
  policy_arn = aws_iam_policy.cloudwatch_logs.arn
}

# Outputs for reference in other Terraform configurations
output "ecs_execution_role_arn" {
  description = "ARN of the ECS execution role for task execution"
  value       = aws_iam_role.ecs_execution.arn
}

output "ecs_task_role_arn" {
  description = "ARN of the ECS task role for runtime permissions"
  value       = aws_iam_role.ecs_task.arn
}

output "s3_access_policy_arn" {
  description = "ARN of the S3 access policy"
  value       = aws_iam_policy.s3_access.arn
}

output "kms_access_policy_arn" {
  description = "ARN of the KMS access policy"
  value       = aws_iam_policy.kms_access.arn
}