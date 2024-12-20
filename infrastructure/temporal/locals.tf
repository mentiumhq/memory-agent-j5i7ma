# Terraform locals configuration for Memory Agent Temporal infrastructure
# Version: 1.0
# Purpose: Defines computed values and environment-specific configurations for Temporal resources

locals {
  # Common tags applied to all Temporal resources for consistent resource management
  common_tags = {
    Environment  = var.environment
    Service      = "memory-agent"
    ManagedBy    = "terraform"
    Version      = "1.0"
    CostCenter   = "memory-services"
    SecurityTier = lookup(local.security_tiers, var.environment)
    BackupPolicy = lookup(local.backup_policies, var.environment)
  }

  # Environment-specific namespace configuration with computed values
  namespace_config = {
    full_name                 = "memory-agent-${var.environment}"
    description              = "Memory Agent service namespace for ${var.environment} environment"
    retention_days           = lookup(local.retention_periods, var.environment)
    workflow_execution_ttl    = lookup(local.workflow_ttls, var.environment)
    data_encryption_level    = lookup(local.encryption_levels, var.environment)
    max_concurrent_workflows = lookup(local.workflow_limits, var.environment)
  }

  # Vector index configuration with environment-specific optimizations
  vector_config = {
    # Environment-specific index parameters
    index_params = {
      dev = {
        dim               = 1536  # OpenAI embedding dimension
        m                 = 16    # HNSW connections per layer
        ef_construction   = 100   # Construction-time accuracy parameter
        max_elements      = 100000
        index_refresh_interval = "5m"
        cache_size_mb    = 512
      }
      staging = {
        dim               = 1536
        m                 = 16
        ef_construction   = 150
        max_elements      = 500000
        index_refresh_interval = "3m"
        cache_size_mb    = 1024
      }
      prod = {
        dim               = 1536
        m                 = 16
        ef_construction   = 200
        max_elements      = 1000000
        index_refresh_interval = "1m"
        cache_size_mb    = 2048
      }
    }
    # Computed environment-specific configuration
    environment_specific = lookup(local.vector_config.index_params, var.environment)
    # Performance monitoring settings
    performance_monitoring = {
      enable_metrics    = true
      metric_interval   = lookup(local.metric_intervals, var.environment)
      alert_thresholds  = lookup(local.alert_thresholds, var.environment)
    }
  }

  # Security tier mapping per environment
  security_tiers = {
    dev     = "standard"
    staging = "enhanced"
    prod    = "maximum"
  }

  # Backup policy configuration per environment
  backup_policies = {
    dev     = "daily"
    staging = "daily-with-retention"
    prod    = "hourly-with-geo-replication"
  }

  # Data retention periods in days per environment
  retention_periods = {
    dev     = 7
    staging = 30
    prod    = 90
  }

  # Workflow execution TTL in hours per environment
  workflow_ttls = {
    dev     = 24
    staging = 72
    prod    = 168  # 7 days
  }

  # Data encryption levels per environment
  encryption_levels = {
    dev     = "standard"
    staging = "enhanced"
    prod    = "maximum"
  }

  # Maximum concurrent workflows per environment
  workflow_limits = {
    dev     = 50
    staging = 200
    prod    = 500
  }

  # Metric collection intervals per environment
  metric_intervals = {
    dev     = "5m"
    staging = "2m"
    prod    = "1m"
  }

  # Alert thresholds for monitoring per environment
  alert_thresholds = {
    dev = {
      cpu_threshold    = 80
      memory_threshold = 85
      error_rate      = 5
    }
    staging = {
      cpu_threshold    = 75
      memory_threshold = 80
      error_rate      = 3
    }
    prod = {
      cpu_threshold    = 70
      memory_threshold = 75
      error_rate      = 1
    }
  }
}