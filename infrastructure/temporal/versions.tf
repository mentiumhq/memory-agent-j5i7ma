# Core Terraform version and provider requirements configuration
# Ensures consistent provider versions and compatibility across all environments
# Last updated: 2024

terraform {
  # Enforce Terraform 1.x version for enterprise stability and features
  # Allows minor version updates but maintains backward compatibility
  required_version = "~> 1.0"

  # Define required providers with strict version constraints
  required_providers {
    # Temporal provider for workflow orchestration infrastructure
    # Version 0.2.x provides necessary workflow features and fault tolerance
    temporal = {
      source  = "temporalio/temporal"
      version = "~> 0.2.0"
    }

    # AWS provider for cloud infrastructure management
    # Version 5.x ensures latest AWS service support and security updates
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}