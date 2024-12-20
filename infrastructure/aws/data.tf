# AWS Provider version ~> 4.0 required
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.0"
    }
  }
}

# Get available AWS Availability Zones
data "aws_availability_zones" "available" {
  state = "available"
}

# Get current AWS account ID
data "aws_caller_identity" "current" {}

# Lookup KMS key for S3 encryption
data "aws_kms_alias" "s3" {
  name = "alias/aws/s3"
}

# Get ECR repository for container images
data "aws_ecr_repository" "memory_agent" {
  name = "memory-agent-${var.environment}"
}

# Get default VPC if not explicitly specified
data "aws_vpc" "default" {
  default = true
  state   = "available"
}

# Get available subnets for ECS task placement
data "aws_subnets" "available" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }

  filter {
    name   = "state"
    values = ["available"]
  }

  filter {
    name   = "map-public-ip-on-launch"
    values = ["true"]
  }
}

# Lookup ECS task execution role
data "aws_iam_role" "ecs_execution" {
  name = "ecsTaskExecutionRole-${var.environment}"
}

# Get CloudWatch log group for container logs
data "aws_cloudwatch_log_group" "memory_agent" {
  name = "/ecs/memory-agent-${var.environment}"
}

# Output available Availability Zones
output "availability_zones" {
  description = "List of available AWS Availability Zones"
  value       = data.aws_availability_zones.available.names
}

# Output AWS account ID
output "account_id" {
  description = "Current AWS account ID"
  value       = data.aws_caller_identity.current.account_id
}

# Output VPC ID
output "vpc_id" {
  description = "Default VPC ID"
  value       = data.aws_vpc.default.id
}

# Output subnet IDs
output "subnet_ids" {
  description = "Available subnet IDs for task placement"
  value       = data.aws_subnets.available.ids
}

# Output ECS execution role ARN
output "ecs_role_arn" {
  description = "ECS task execution role ARN"
  value       = data.aws_iam_role.ecs_execution.arn
}

# Output CloudWatch log group name
output "log_group_name" {
  description = "CloudWatch log group name for container logs"
  value       = data.aws_cloudwatch_log_group.memory_agent.name
}