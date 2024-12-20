# AWS Route53 Configuration for Memory Agent Service
# Version: ~> 1.0
# Provider: AWS (~> 4.0)

# Primary hosted zone for Memory Agent service
resource "aws_route53_zone" "main" {
  name = "${local.naming.service_name}.internal"
  
  vpc {
    vpc_id = data.aws_vpc.main.id
    vpc_region = var.aws_region
  }
  
  comment = "Private hosted zone for ${var.environment} Memory Agent service"
  force_destroy = false
  
  tags = merge(
    local.common_tags,
    {
      Name = "${local.naming.service_name}-zone"
      Service = "dns"
    }
  )
}

# Primary health check for Memory Agent service
resource "aws_route53_health_check" "primary" {
  fqdn              = "${local.naming.service_name}.internal"
  port              = 443
  type              = "HTTPS"
  resource_path     = "/v1/health"
  failure_threshold = 3
  request_interval  = local.monitoring.interval
  
  measure_latency = true
  enable_sni      = true
  
  regions = [
    "us-west-1",
    "us-east-1",
    "eu-west-1"
  ]
  
  tags = merge(
    local.common_tags,
    {
      Name = "${local.naming.service_name}-health-primary"
      Type = "primary"
    }
  )
  
  search_string = "\"status\":\"healthy\""
  inverted      = false
}

# Secondary health check for failover
resource "aws_route53_health_check" "secondary" {
  fqdn              = "${local.naming.service_name}-secondary.internal"
  port              = 443
  type              = "HTTPS"
  resource_path     = "/v1/health"
  failure_threshold = 2
  request_interval  = local.monitoring.interval
  
  measure_latency = true
  enable_sni      = true
  
  regions = [
    "us-west-2",
    "us-east-2",
    "eu-central-1"
  ]
  
  tags = merge(
    local.common_tags,
    {
      Name = "${local.naming.service_name}-health-secondary"
      Type = "secondary"
    }
  )
  
  search_string = "\"status\":\"healthy\""
  inverted      = false
}

# Primary A record with failover routing
resource "aws_route53_record" "primary" {
  zone_id = aws_route53_zone.main.zone_id
  name    = local.naming.service_name
  type    = "A"
  
  set_identifier = "primary"
  
  failover_routing_policy {
    type = "PRIMARY"
  }
  
  alias {
    name                   = data.aws_lb.main.dns_name
    zone_id               = data.aws_lb.main.zone_id
    evaluate_target_health = true
  }
  
  health_check_id = aws_route53_health_check.primary.id
}

# Secondary A record for failover
resource "aws_route53_record" "secondary" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "${local.naming.service_name}-secondary"
  type    = "A"
  
  set_identifier = "secondary"
  
  failover_routing_policy {
    type = "SECONDARY"
  }
  
  alias {
    name                   = data.aws_lb.secondary.dns_name
    zone_id               = data.aws_lb.secondary.zone_id
    evaluate_target_health = true
  }
  
  health_check_id = aws_route53_health_check.secondary.id
}

# CNAME record for service discovery
resource "aws_route53_record" "service" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "service.${local.naming.service_name}"
  type    = "CNAME"
  ttl     = 300
  
  records = [aws_route53_record.primary.name]
}

# Outputs for DNS management
output "route53_zone_id" {
  description = "The hosted zone ID for DNS record management"
  value       = aws_route53_zone.main.zone_id
}

output "route53_name_servers" {
  description = "The name servers for the hosted zone"
  value       = aws_route53_zone.main.name_servers
}

output "route53_health_check_ids" {
  description = "The health check IDs for monitoring"
  value = {
    primary   = aws_route53_health_check.primary.id
    secondary = aws_route53_health_check.secondary.id
  }
}

# Data sources for existing resources
data "aws_vpc" "main" {
  id = var.vpc_id
}

data "aws_lb" "main" {
  name = "${local.naming.service_name}-alb"
}

data "aws_lb" "secondary" {
  name = "${local.naming.service_name}-secondary-alb"
}