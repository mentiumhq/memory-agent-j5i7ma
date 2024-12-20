# AWS KMS configuration for Memory Agent document encryption
# Provider version: ~> 4.0
# Purpose: Manages encryption keys for secure document storage with automated rotation

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.0"
    }
  }
}

# Get current AWS account identity for KMS policy
data "aws_caller_identity" "current" {}

# KMS key for document encryption
resource "aws_kms_key" "document_kms_key" {
  description              = "KMS key for Memory Agent document encryption with automated rotation"
  deletion_window_in_days  = 30
  enable_key_rotation     = true
  is_enabled              = true
  customer_master_key_spec = "SYMMETRIC_DEFAULT"
  key_usage               = "ENCRYPT_DECRYPT"

  # Enhanced KMS key policy with strict access controls
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "Enable IAM User Permissions"
        Effect    = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action    = "kms:*"
        Resource  = "*"
        Condition = {
          StringEquals = {
            "aws:PrincipalType": "AWS"
          }
        }
      },
      {
        Sid       = "Allow S3 Service"
        Effect    = "Allow"
        Principal = {
          Service = "s3.amazonaws.com"
        }
        Action    = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ]
        Resource  = "*"
      },
      {
        Sid       = "Allow ECS Service"
        Effect    = "Allow"
        Principal = {
          Service = "ecs.amazonaws.com"
        }
        Action    = [
          "kms:Decrypt",
          "kms:GenerateDataKey*"
        ]
        Resource  = "*"
      },
      {
        Sid       = "DenyKeyDeletionInProduction"
        Effect    = "Deny"
        Principal = {
          AWS = "*"
        }
        Action    = [
          "kms:ScheduleKeyDeletion",
          "kms:DeleteImportedKeyMaterial"
        ]
        Resource  = "*"
        Condition = {
          StringEquals = {
            "aws:RequestedRegion": var.aws_region,
            "aws:ResourceTag/Environment": "production"
          }
        }
      }
    ]
  })

  # Apply common tags with additional KMS-specific tags
  tags = merge(
    local.common_tags,
    {
      Name = "${var.app_name}-${var.environment}-document-kms-key"
      Service = "encryption"
      SecurityControl = "data-protection"
      EncryptionType = "AES-256"
      AutoRotation = "enabled"
    }
  )
}

# KMS alias for easier key reference
resource "aws_kms_alias" "document_kms_alias" {
  name          = "alias/${var.app_name}-${var.environment}-document-key"
  target_key_id = aws_kms_key.document_kms_key.key_id
}

# KMS key policy for automated rotation monitoring
resource "aws_cloudwatch_metric_alarm" "kms_rotation_alarm" {
  alarm_name          = "${var.app_name}-${var.environment}-kms-rotation-check"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name        = "DaysUntilKeyRotation"
  namespace          = "AWS/KMS"
  period             = 86400  # 24 hours
  statistic          = "Maximum"
  threshold          = 365    # Alert if rotation hasn't occurred in a year
  alarm_description  = "Monitor KMS key rotation status for document encryption"
  alarm_actions      = []     # Add SNS topic ARN if needed

  dimensions = {
    KeyId = aws_kms_key.document_kms_key.key_id
  }

  tags = merge(
    local.common_tags,
    {
      Name = "${var.app_name}-${var.environment}-kms-rotation-alarm"
      MonitoringType = "security"
    }
  )
}

# Output the KMS key ARN and ID for use by other resources
output "document_kms_key_arn" {
  description = "ARN of the KMS key used for document encryption"
  value       = aws_kms_key.document_kms_key.arn
}

output "document_kms_key_id" {
  description = "ID of the KMS key used for document encryption"
  value       = aws_kms_key.document_kms_key.key_id
}