# Backend configuration for Memory Agent Temporal infrastructure
# Version: 1.0
# Terraform Version: ~> 1.0
# Provider Version: AWS ~> 5.0

terraform {
  # Specify minimum Terraform version required
  required_version = "~> 1.0"

  # Configure the backend to store state in S3 with DynamoDB locking
  backend "s3" {
    # Environment-specific state bucket with proper naming convention
    bucket = "memory-agent-temporal-state-${var.environment}"
    
    # State file path within the bucket
    key = "temporal/terraform.tfstate"
    
    # AWS region for state storage
    region = "us-west-2"
    
    # Enable state file encryption using AWS KMS
    encrypt = true
    
    # Use environment-specific KMS key for state encryption
    kms_key_id = "arn:aws:kms:us-west-2:${data.aws_caller_identity.current.account_id}:key/temporal-state-${var.environment}"
    
    # Environment-specific DynamoDB table for state locking
    dynamodb_table = "memory-agent-temporal-locks-${var.environment}"
    
    # Enable versioning for state file history and backup
    versioning = true
    
    # Set private ACL for enhanced security
    acl = "private"
    
    # Enable server-side encryption for state files
    server_side_encryption_configuration {
      rule {
        apply_server_side_encryption_by_default {
          sse_algorithm = "aws:kms"
        }
      }
    }
    
    # Configure lifecycle rules for state management
    lifecycle_rule {
      enabled = true
      
      # Keep previous state versions for 30 days
      noncurrent_version_expiration {
        days = 30
      }
      
      # Transition old versions to cheaper storage
      noncurrent_version_transition {
        days          = 7
        storage_class = "STANDARD_IA"
      }
    }
    
    # Enable access logging for audit trails
    logging {
      target_bucket = "memory-agent-logs-${var.environment}"
      target_prefix = "terraform-state-access-logs/"
    }
    
    # Configure error handling and retry logic
    force_destroy = false
    max_retries   = 5
    
    # Enable strong consistency for state operations
    enable_strong_consistency = true
  }
}

# Data source to get current AWS account ID for KMS key ARN
data "aws_caller_identity" "current" {}