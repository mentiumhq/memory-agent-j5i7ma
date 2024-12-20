# AWS Provider Configuration for Memory Agent Infrastructure
# Version: ~> 4.0
# Purpose: Defines AWS provider settings, authentication, and regional configuration
# Security Level: High with encryption and secure defaults

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.0"
    }
  }
}

# Main AWS Provider Configuration
provider "aws" {
  region = var.aws_region

  # Default tags applied to all resources
  default_tags {
    tags = {
      Project            = "memory-agent"
      Environment        = var.environment
      ManagedBy         = "terraform"
      Service           = "memory-agent"
      SecurityLevel     = "high"
      DataClassification = "confidential"
      LastUpdated       = timestamp()
    }
  }

  # Enhanced security configuration for IAM role assumption
  assume_role {
    role_arn     = var.assume_role_arn
    session_name = "MemoryAgentTerraform-${var.environment}"
    external_id  = var.external_id
  }

  # Default encryption configuration using AES-256
  default_encryption_configuration {
    kms_key_id           = var.kms_key_id
    encryption_algorithm = "AES256"
  }

  # Retry configuration for API calls
  retry_mode  = "standard"
  max_retries = 5

  # Environment-specific endpoints configuration
  endpoints {
    s3   = var.s3_endpoint
    kms  = var.kms_endpoint
    ecs  = var.ecs_endpoint
    logs = var.cloudwatch_endpoint
  }

  # Tag management configuration
  ignore_tags {
    keys = ["temporary", "testing"]
  }

  # Enhanced security settings
  default_security_configuration {
    enable_tls_1_2_only = true
    enable_iam_database_authentication = true
    enable_s3_bucket_encryption = true
    block_public_access = true
  }

  # Environment-specific provider configuration
  dynamic "assume_role_with_web_identity" {
    for_each = var.environment == "production" ? [1] : []
    content {
      role_arn                = var.prod_role_arn
      web_identity_token_file = var.token_file_path
      session_name           = "MemoryAgentProdSession"
    }
  }
}

# Provider alias for cross-region operations (e.g., DR)
provider "aws" {
  alias  = "dr_region"
  region = var.dr_region

  default_tags {
    tags = {
      Project            = "memory-agent"
      Environment        = "${var.environment}-dr"
      ManagedBy         = "terraform"
      Service           = "memory-agent"
      SecurityLevel     = "high"
      DataClassification = "confidential"
      LastUpdated       = timestamp()
    }
  }

  assume_role {
    role_arn     = var.dr_assume_role_arn
    session_name = "MemoryAgentTerraform-${var.environment}-dr"
    external_id  = var.dr_external_id
  }
}

# Provider configuration for CloudWatch monitoring
provider "aws" {
  alias  = "monitoring"
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "memory-agent"
      Environment = var.environment
      ManagedBy   = "terraform"
      Service     = "monitoring"
      Component   = "cloudwatch"
    }
  }

  assume_role {
    role_arn     = var.monitoring_role_arn
    session_name = "MemoryAgentMonitoring-${var.environment}"
    external_id  = var.monitoring_external_id
  }
}