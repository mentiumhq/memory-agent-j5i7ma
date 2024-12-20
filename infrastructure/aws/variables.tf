# Core deployment environment variable
variable "environment" {
  type        = string
  description = "Deployment environment (development, staging, production)"
  validation {
    condition     = can(regex("^(development|staging|production)$", var.environment))
    error_message = "Environment must be one of: development, staging, production"
  }
}

# AWS region configuration
variable "aws_region" {
  type        = string
  description = "AWS region for resource deployment"
  default     = "us-west-2"
}

# Application naming
variable "app_name" {
  type        = string
  description = "Application name for resource naming"
  default     = "memory-agent"
}

# Container CPU allocation by environment
variable "container_cpu" {
  type        = map(number)
  description = "CPU units for containers by environment"
  default = {
    development = 2048 # 2 vCPU
    staging     = 4096 # 4 vCPU
    production  = 8192 # 8 vCPU
  }
}

# Container memory allocation by environment
variable "container_memory" {
  type        = map(number)
  description = "Memory allocation for containers by environment"
  default = {
    development = 4096  # 4GB
    staging     = 8192  # 8GB
    production  = 16384 # 16GB
  }
}

# Auto-scaling configuration
variable "min_capacity" {
  type        = map(number)
  description = "Minimum number of tasks by environment"
  default = {
    development = 1
    staging     = 2
    production  = 3
  }
}

variable "max_capacity" {
  type        = map(number)
  description = "Maximum number of tasks by environment"
  default = {
    development = 2
    staging     = 4
    production  = 10
  }
}

# Monitoring configuration
variable "enable_monitoring" {
  type        = bool
  description = "Enable detailed CloudWatch monitoring"
  default     = true
}

# Resource tagging
variable "tags" {
  type        = map(string)
  description = "Additional resource tags"
  default     = {}
}