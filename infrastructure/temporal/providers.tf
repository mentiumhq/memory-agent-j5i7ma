# Configure required providers with version constraints
terraform {
  required_providers {
    # Temporal provider v0.2.0 for managing Temporal resources
    temporal = {
      source  = "temporalio/temporal"
      version = "~> 0.2.0"
    }
    
    # AWS provider v5.0 for infrastructure management
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# AWS provider configuration with environment-specific settings and security tags
provider "aws" {
  region  = var.region
  profile = "memory-agent-${var.environment}"
  
  default_tags {
    tags = {
      Project            = "memory-agent"
      Environment        = var.environment
      Component         = "temporal"
      ManagedBy         = "terraform"
      SecurityLevel     = "high"
      DataClassification = "confidential"
    }
  }
}

# Temporal provider configuration with enhanced security settings
provider "temporal" {
  # Internal DNS resolution for Temporal server
  server_url = "temporal.${var.environment}.memory-agent.internal:7233"
  
  # Environment-specific namespace
  namespace = "memory-agent-${var.environment}"
  
  # TLS configuration with strict security settings
  tls {
    enabled             = true
    server_name         = "temporal.${var.environment}.memory-agent.internal"
    client_cert         = file("${path.module}/certs/client-cert.pem")
    client_key          = file("${path.module}/certs/client-key.pem")
    ca_cert             = file("${path.module}/certs/ca-cert.pem")
    min_version         = "TLS1.3"
    verify_server_name  = true
    verify_certificate  = true
  }
  
  # Retry configuration for resilient connections
  retry {
    initial_interval    = "1s"
    max_interval        = "10s"
    max_attempts        = 5
    backoff_coefficient = 2.0
  }
}