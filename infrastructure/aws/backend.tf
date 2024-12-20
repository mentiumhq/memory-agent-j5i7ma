# Backend configuration for Memory Agent Terraform state management
# Version: ~> 1.0
# Provider Requirements: AWS ~> 4.0

terraform {
  # S3 backend configuration for state management
  backend "s3" {
    # State storage bucket with environment-specific path
    bucket = "memory-agent-terraform-state"
    key    = "terraform.tfstate"
    region = var.aws_region

    # Enable server-side encryption with AWS KMS
    encrypt = true

    # DynamoDB table for state locking
    dynamodb_table = "memory-agent-terraform-locks"

    # Enhanced security and operational features
    kms_key_id                 = "alias/terraform-state-key"
    sse_algorithm             = "aws:kms"
    skip_region_validation    = false
    skip_credentials_validation = false
    skip_metadata_api_check   = false

    # Access logging and versioning configuration
    force_path_style           = false
    workspace_key_prefix      = "env"

    # Advanced features for production readiness
    max_retries              = 5
    shared_credentials_file  = "~/.aws/credentials"
    profile                 = "memory-agent-terraform"

    # Lifecycle configuration
    lifecycle {
      prevent_destroy = true
    }

    # Additional backend settings for enhanced security
    acl                     = "private"
    versioning             = true
    server_side_encryption = "AES256"

    # Cross-region replication settings
    replica_regions = {
      "us-east-1" = {
        kms_key_id = "alias/terraform-state-key-replica"
      }
    }
  }

  # Required provider configuration
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.0"
    }
  }

  # Terraform version constraint
  required_version = "~> 1.0"
}

# Backend configuration validation
locals {
  backend_validation = {
    ensure_encryption     = terraform.backend.s3.encrypt
    ensure_locking       = length(terraform.backend.s3.dynamodb_table) > 0
    ensure_versioning    = terraform.backend.s3.versioning
    ensure_replication   = length(terraform.backend.s3.replica_regions) > 0
  }
}

# Backend configuration outputs for monitoring
output "backend_configuration" {
  value = {
    bucket            = terraform.backend.s3.bucket
    region           = terraform.backend.s3.region
    dynamodb_table   = terraform.backend.s3.dynamodb_table
    encryption       = terraform.backend.s3.encrypt
    kms_key_id       = terraform.backend.s3.kms_key_id
  }
  description = "Backend configuration details for monitoring and validation"
  sensitive   = true
}