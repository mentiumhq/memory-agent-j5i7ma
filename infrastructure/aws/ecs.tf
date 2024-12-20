# AWS ECS Configuration for Memory Agent Service
# Version: ~> 5.0
# Provider: AWS

# ECS Cluster with enhanced monitoring and capacity providers
resource "aws_ecs_cluster" "main" {
  name = local.naming.cluster_name

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  capacity_providers = ["FARGATE", "FARGATE_SPOT"]

  default_capacity_provider_strategy {
    capacity_provider = "FARGATE"
    weight           = 1
    base            = 1
  }

  default_capacity_provider_strategy {
    capacity_provider = "FARGATE_SPOT"
    weight           = 1
    base            = 0
  }

  tags = merge(local.common_tags, {
    Name = local.naming.cluster_name
  })
}

# ECS Task Definition with optimized resource allocation
resource "aws_ecs_task_definition" "main" {
  family                   = local.naming.task_family
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = local.compute_resources.cpu
  memory                   = local.compute_resources.memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn           = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name         = var.app_name
      image        = "${var.ecr_repository_url}:${var.image_tag}"
      essential    = true
      portMappings = [
        {
          containerPort = 8000
          protocol      = "tcp"
        }
      ]
      healthCheck = {
        command     = ["CMD-SHELL", "curl -f http://localhost:8000/v1/health || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = local.naming.log_group
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "ecs"
        }
      }
      environment = [
        {
          name  = "ENVIRONMENT"
          value = var.environment
        }
      ]
      mountPoints = []
      volumesFrom = []
    }
  ])

  tags = merge(local.common_tags, {
    Name = local.naming.task_family
  })
}

# ECS Service with high availability configuration
resource "aws_ecs_service" "main" {
  name                              = local.naming.service_name
  cluster                          = aws_ecs_cluster.main.id
  task_definition                  = aws_ecs_task_definition.main.arn
  desired_count                    = local.current_config.min_tasks
  launch_type                      = "FARGATE"
  platform_version                 = "LATEST"
  health_check_grace_period_seconds = 60
  propagate_tags                   = "SERVICE"

  deployment_maximum_percent         = 200
  deployment_minimum_healthy_percent = 100

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  network_configuration {
    subnets          = data.aws_subnet_ids.private.ids
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.main.arn
    container_name   = var.app_name
    container_port   = 8000
  }

  service_registries {
    registry_arn = aws_service_discovery_service.main.arn
  }

  tags = merge(local.common_tags, {
    Name = local.naming.service_name
  })

  lifecycle {
    ignore_changes = [desired_count]
  }
}

# Auto-scaling target configuration
resource "aws_appautoscaling_target" "main" {
  max_capacity       = local.current_config.max_tasks
  min_capacity       = local.current_config.min_tasks
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.main.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

# CPU-based auto-scaling policy
resource "aws_appautoscaling_policy" "cpu" {
  name               = "${local.naming.service_name}-cpu-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.main.resource_id
  scalable_dimension = aws_appautoscaling_target.main.scalable_dimension
  service_namespace  = aws_appautoscaling_target.main.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value       = local.monitoring.cpu_threshold
    scale_in_cooldown  = local.current_config.scaling_cooldown
    scale_out_cooldown = 60
  }
}

# Memory-based auto-scaling policy
resource "aws_appautoscaling_policy" "memory" {
  name               = "${local.naming.service_name}-memory-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.main.resource_id
  scalable_dimension = aws_appautoscaling_target.main.scalable_dimension
  service_namespace  = aws_appautoscaling_target.main.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageMemoryUtilization"
    }
    target_value       = local.monitoring.memory_threshold
    scale_in_cooldown  = local.current_config.scaling_cooldown
    scale_out_cooldown = 60
  }
}

# Request count-based auto-scaling policy
resource "aws_appautoscaling_policy" "requests" {
  name               = "${local.naming.service_name}-request-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.main.resource_id
  scalable_dimension = aws_appautoscaling_target.main.scalable_dimension
  service_namespace  = aws_appautoscaling_target.main.service_namespace

  target_tracking_scaling_policy_configuration {
    customized_metric_specification {
      metric_name = "RequestCountPerTarget"
      namespace   = "AWS/ApplicationELB"
      dimensions {
        name  = "TargetGroup"
        value = aws_lb_target_group.main.arn_suffix
      }
      statistic = "Sum"
    }
    target_value       = 50.0 # Support 50 requests/second per target
    scale_in_cooldown  = local.current_config.scaling_cooldown
    scale_out_cooldown = 60
  }
}

# Outputs for reference by other modules
output "cluster_name" {
  description = "Name of the ECS cluster"
  value       = aws_ecs_cluster.main.name
}

output "service_name" {
  description = "Name of the ECS service"
  value       = aws_ecs_service.main.name
}

output "task_definition_arn" {
  description = "ARN of the task definition"
  value       = aws_ecs_task_definition.main.arn
}

output "service_discovery_arn" {
  description = "ARN of the service discovery service"
  value       = aws_service_discovery_service.main.arn
}