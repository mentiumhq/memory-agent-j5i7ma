# Terraform version and provider requirements for Memory Agent AWS infrastructure
# Ensures consistent deployment across development, staging, and production environments
terraform {
  # Core Terraform version constraint
  # Using ~> 1.0 to allow patches while maintaining compatibility with 1.x features
  required_version = "~> 1.0"

  # Required provider configurations
  required_providers {
    # AWS provider configuration
    # Version ~> 4.0 allows minor version updates while maintaining stability
    # Supports all required services: ECS, S3, CloudWatch, Route 53, KMS, ECR
    aws = {
      source  = "hashicorp/aws"    # Official HashiCorp registry source
      version = "~> 4.0"           # AWS provider version constraint
    }
  }
}