# AWS Infrastructure Outputs for Memory Agent Service
# Version: ~> 5.0
# Purpose: Defines output values for core AWS infrastructure components
# Security: Sensitive values are marked accordingly to prevent exposure

# ECS Cluster Outputs
output "ecs_cluster_name" {
  description = "Name of the ECS cluster for Memory Agent service deployment"
  value       = aws_ecs_cluster.main.name
  sensitive   = false
}

output "ecs_service_name" {
  description = "Name of the ECS service running the Memory Agent containers"
  value       = aws_ecs_service.main.name
  sensitive   = false
}

output "ecs_cluster_arn" {
  description = "ARN of the ECS cluster for service deployment configuration"
  value       = aws_ecs_cluster.main.arn
  sensitive   = false
}

# S3 Storage Outputs
output "document_bucket_name" {
  description = "Name of the S3 bucket used for secure document storage with versioning enabled"
  value       = aws_s3_bucket.document_storage.id
  sensitive   = false
}

output "document_bucket_arn" {
  description = "ARN of the S3 bucket for use in IAM policies and resource permissions"
  value       = aws_s3_bucket.document_storage.arn
  sensitive   = false
}

output "document_bucket_domain_name" {
  description = "Domain name of the S3 bucket for constructing endpoint URLs"
  value       = aws_s3_bucket.document_storage.bucket_domain_name
  sensitive   = false
}

# KMS Encryption Outputs
output "kms_key_arn" {
  description = "ARN of the KMS key used for document encryption at rest"
  value       = aws_kms_key.document_kms_key.arn
  sensitive   = true # Marked sensitive as it's used for encryption
}

output "kms_key_id" {
  description = "ID of the KMS key for configuring encryption settings"
  value       = aws_kms_key.document_kms_key.key_id
  sensitive   = true # Marked sensitive as it's used for encryption
}

output "kms_key_alias" {
  description = "Alias of the KMS key for easier reference"
  value       = aws_kms_alias.document_kms_alias.name
  sensitive   = false
}

# Security Group Outputs
output "ecs_security_group_id" {
  description = "ID of the security group attached to ECS tasks"
  value       = aws_security_group.ecs.id
  sensitive   = false
}

# Monitoring and Logging Outputs
output "cloudwatch_log_group" {
  description = "Name of the CloudWatch log group for ECS service logs"
  value       = local.naming.log_group
  sensitive   = false
}

# Environment Configuration Outputs
output "environment_config" {
  description = "Current environment configuration settings"
  value = {
    environment     = var.environment
    min_tasks      = local.current_config.min_tasks
    max_tasks      = local.current_config.max_tasks
    cpu_threshold  = local.monitoring.cpu_threshold
    memory_threshold = local.monitoring.memory_threshold
  }
  sensitive   = false
}

# Service Discovery Outputs
output "service_discovery_namespace" {
  description = "Service discovery namespace for internal service communication"
  value       = "${var.app_name}.${var.environment}.local"
  sensitive   = false
}

# Tags Output
output "resource_tags" {
  description = "Common tags applied to all resources"
  value       = local.common_tags
  sensitive   = false
}

# Backup Configuration
output "backup_retention_days" {
  description = "Number of days to retain backups based on environment"
  value       = local.backup.retention_days
  sensitive   = false
}

# Security Configuration
output "security_config" {
  description = "Security configuration for the environment"
  value = {
    multi_az          = local.security.multi_az
    encryption_enabled = local.security.encryption_enabled
    ssl_policy        = local.security.ssl_policy
    audit_logging     = local.security.audit_logging
  }
  sensitive   = false
}