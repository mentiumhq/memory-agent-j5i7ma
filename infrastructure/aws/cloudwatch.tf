# AWS CloudWatch configuration for Memory Agent service monitoring
# Provider version: ~> 4.0

# Main application log group
resource "aws_cloudwatch_log_group" "main" {
  name              = "/aws/ecs/${var.app_name}-${var.environment}"
  retention_in_days = var.log_retention_days

  tags = {
    Name        = "${var.app_name}-${var.environment}-logs"
    Environment = var.environment
    Application = var.app_name
    ManagedBy   = "Terraform"
  }
}

# Performance and health alarms
resource "aws_cloudwatch_metric_alarm" "cpu_utilization" {
  alarm_name          = "${var.app_name}-${var.environment}-cpu-utilization"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name        = "CPUUtilization"
  namespace          = "AWS/ECS"
  period             = 300
  statistic          = "Average"
  threshold          = 70
  alarm_description  = "CPU utilization has exceeded 70% threshold"
  alarm_actions      = [] # Add SNS topic ARN for notifications

  dimensions = {
    ClusterName = "${var.app_name}-${var.environment}"
    ServiceName = "${var.app_name}-${var.environment}-service"
  }

  tags = {
    Environment = var.environment
    Application = var.app_name
    ManagedBy   = "Terraform"
  }
}

resource "aws_cloudwatch_metric_alarm" "memory_utilization" {
  alarm_name          = "${var.app_name}-${var.environment}-memory-utilization"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name        = "MemoryUtilization"
  namespace          = "AWS/ECS"
  period             = 300
  statistic          = "Average"
  threshold          = 85
  alarm_description  = "Memory utilization has exceeded 85% threshold"
  alarm_actions      = [] # Add SNS topic ARN for notifications

  dimensions = {
    ClusterName = "${var.app_name}-${var.environment}"
    ServiceName = "${var.app_name}-${var.environment}-service"
  }

  tags = {
    Environment = var.environment
    Application = var.app_name
    ManagedBy   = "Terraform"
  }
}

resource "aws_cloudwatch_metric_alarm" "api_latency" {
  alarm_name          = "${var.app_name}-${var.environment}-api-latency"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name        = "TargetResponseTime"
  namespace          = "AWS/ApplicationELB"
  period             = 60
  statistic          = "Average"
  threshold          = 3
  alarm_description  = "API latency has exceeded 3 seconds"
  alarm_actions      = [] # Add SNS topic ARN for notifications

  dimensions = {
    LoadBalancer = "${var.app_name}-${var.environment}-alb"
  }

  tags = {
    Environment = var.environment
    Application = var.app_name
    ManagedBy   = "Terraform"
  }
}

resource "aws_cloudwatch_metric_alarm" "error_rate" {
  alarm_name          = "${var.app_name}-${var.environment}-error-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name        = "HTTPCode_Target_5XX_Count"
  namespace          = "AWS/ApplicationELB"
  period             = 300
  statistic          = "Sum"
  threshold          = 10
  alarm_description  = "Error rate has exceeded 10 5XX errors in 5 minutes"
  alarm_actions      = [] # Add SNS topic ARN for notifications

  dimensions = {
    LoadBalancer = "${var.app_name}-${var.environment}-alb"
  }

  tags = {
    Environment = var.environment
    Application = var.app_name
    ManagedBy   = "Terraform"
  }
}

# Custom metrics for Memory Agent specific monitoring
resource "aws_cloudwatch_metric_alarm" "vector_search_latency" {
  alarm_name          = "${var.app_name}-${var.environment}-vector-search-latency"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name        = "VectorSearchLatency"
  namespace          = "MemoryAgent"
  period             = 60
  statistic          = "Average"
  threshold          = 0.5 # 500ms threshold as per requirements
  alarm_description  = "Vector search latency has exceeded 500ms threshold"
  alarm_actions      = [] # Add SNS topic ARN for notifications

  dimensions = {
    Service = "${var.app_name}-${var.environment}"
  }

  tags = {
    Environment = var.environment
    Application = var.app_name
    ManagedBy   = "Terraform"
  }
}

resource "aws_cloudwatch_metric_alarm" "llm_latency" {
  alarm_name          = "${var.app_name}-${var.environment}-llm-latency"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name        = "LLMLatency"
  namespace          = "MemoryAgent"
  period             = 60
  statistic          = "Average"
  threshold          = 3.0 # 3000ms threshold as per requirements
  alarm_description  = "LLM processing latency has exceeded 3000ms threshold"
  alarm_actions      = [] # Add SNS topic ARN for notifications

  dimensions = {
    Service = "${var.app_name}-${var.environment}"
  }

  tags = {
    Environment = var.environment
    Application = var.app_name
    ManagedBy   = "Terraform"
  }
}

# Comprehensive monitoring dashboard
resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${var.app_name}-${var.environment}-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        x    = 0
        y    = 0
        width = 12
        height = 6
        properties = {
          metrics = [
            ["AWS/ECS", "CPUUtilization", "ServiceName", "${var.app_name}-${var.environment}-service"],
            ["AWS/ECS", "MemoryUtilization", "ServiceName", "${var.app_name}-${var.environment}-service"]
          ]
          period = 300
          stat   = "Average"
          region = var.aws_region
          title  = "ECS Resource Utilization"
        }
      },
      {
        type = "metric"
        x    = 12
        y    = 0
        width = 12
        height = 6
        properties = {
          metrics = [
            ["MemoryAgent", "VectorSearchLatency"],
            ["MemoryAgent", "LLMLatency"]
          ]
          period = 60
          stat   = "Average"
          region = var.aws_region
          title  = "Latency Metrics"
        }
      },
      {
        type = "metric"
        x    = 0
        y    = 6
        width = 12
        height = 6
        properties = {
          metrics = [
            ["AWS/ApplicationELB", "RequestCount"],
            ["AWS/ApplicationELB", "TargetResponseTime"]
          ]
          period = 60
          stat   = "Average"
          region = var.aws_region
          title  = "API Performance"
        }
      },
      {
        type = "metric"
        x    = 12
        y    = 6
        width = 12
        height = 6
        properties = {
          metrics = [
            ["AWS/ApplicationELB", "HTTPCode_Target_2XX_Count"],
            ["AWS/ApplicationELB", "HTTPCode_Target_4XX_Count"],
            ["AWS/ApplicationELB", "HTTPCode_Target_5XX_Count"]
          ]
          period = 300
          stat   = "Sum"
          region = var.aws_region
          title  = "API Error Rates"
        }
      }
    ]
  })
}

# Outputs for reference in other modules
output "log_group_name" {
  description = "Name of the CloudWatch log group for Memory Agent"
  value       = aws_cloudwatch_log_group.main.name
}

output "dashboard_name" {
  description = "Name of the CloudWatch dashboard for Memory Agent monitoring"
  value       = aws_cloudwatch_dashboard.main.dashboard_name
}