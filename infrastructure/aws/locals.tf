# Terraform locals configuration for Memory Agent AWS infrastructure
# Version: ~> 1.0

locals {
  # Enhanced common tags for comprehensive resource management
  common_tags = {
    Project             = "memory-agent"
    Environment         = var.environment
    ManagedBy          = "terraform"
    Service            = "document-storage"
    Owner              = "platform-team"
    CostCenter         = "platform-engineering"
    SecurityLevel      = "high"
    DataClassification = "internal"
    Backup             = "required"
    Compliance         = "sox-hipaa"
    ApplicationRole    = "document-processing"
  }

  # Comprehensive environment-specific configurations
  environment_config = {
    development = {
      instance_type           = "t3.medium"
      cpu                     = 2048
      memory                 = 4096
      min_tasks              = 1
      max_tasks              = 2
      monitoring_interval    = 60
      storage_size           = 20
      backup_retention_days  = 7
      alert_threshold_cpu    = 80
      alert_threshold_memory = 80
      scaling_cooldown       = 300
      maintenance_window     = "sun:04:00-sun:06:00"
      log_retention_days     = 30
      performance_insights   = false
      multi_az              = false
    }
    staging = {
      instance_type           = "t3.large"
      cpu                     = 4096
      memory                 = 8192
      min_tasks              = 2
      max_tasks              = 4
      monitoring_interval    = 30
      storage_size           = 100
      backup_retention_days  = 14
      alert_threshold_cpu    = 75
      alert_threshold_memory = 75
      scaling_cooldown       = 180
      maintenance_window     = "sat:04:00-sat:06:00"
      log_retention_days     = 60
      performance_insights   = true
      multi_az              = false
    }
    production = {
      instance_type           = "t3.xlarge"
      cpu                     = 8192
      memory                 = 16384
      min_tasks              = 3
      max_tasks              = 10
      monitoring_interval    = 15
      storage_size           = 500
      backup_retention_days  = 30
      alert_threshold_cpu    = 70
      alert_threshold_memory = 70
      scaling_cooldown       = 120
      maintenance_window     = "sun:02:00-sun:04:00"
      log_retention_days     = 90
      performance_insights   = true
      multi_az              = true
    }
  }

  # Comprehensive resource naming conventions
  naming = {
    cluster_name       = "${var.app_name}-${var.environment}-cluster"
    service_name       = "${var.app_name}-${var.environment}-service"
    task_family       = "${var.app_name}-${var.environment}-task"
    log_group         = "/aws/ecs/${var.app_name}-${var.environment}"
    security_group    = "${var.app_name}-${var.environment}-sg"
    iam_role         = "${var.app_name}-${var.environment}-role"
    kms_key          = "${var.app_name}-${var.environment}-key"
    s3_bucket        = "${var.app_name}-${var.environment}-storage"
    cloudwatch_alarm = "${var.app_name}-${var.environment}-alarm"
    sns_topic        = "${var.app_name}-${var.environment}-notifications"
    backup_vault     = "${var.app_name}-${var.environment}-backup"
    parameter_store  = "/${var.app_name}/${var.environment}"
  }

  # Current environment configuration lookup
  current_config = local.environment_config[var.environment]

  # Computed resource configurations
  compute_resources = {
    cpu    = local.current_config.cpu
    memory = local.current_config.memory
  }

  # Monitoring and alerting configurations
  monitoring = {
    interval           = local.current_config.monitoring_interval
    retention_days     = local.current_config.log_retention_days
    cpu_threshold      = local.current_config.alert_threshold_cpu
    memory_threshold   = local.current_config.alert_threshold_memory
    evaluation_periods = 3
    datapoints_required = 2
  }

  # Backup and recovery configurations
  backup = {
    retention_days     = local.current_config.backup_retention_days
    maintenance_window = local.current_config.maintenance_window
    backup_window      = "03:00-04:00"
    snapshot_interval  = "24h"
  }

  # Security and compliance configurations
  security = {
    encryption_enabled = true
    ssl_policy        = "ELBSecurityPolicy-TLS-1-2-2017-01"
    backup_encryption = true
    audit_logging     = true
    multi_az          = local.current_config.multi_az
  }
}