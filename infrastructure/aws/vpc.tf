# AWS VPC Configuration for Memory Agent Service
# Version: ~> 1.0
# Provider Requirements: AWS Provider ~> 4.0

terraform {
  required_version = "~> 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.0"
    }
  }
}

# Data source for available AZs in the region
data "aws_availability_zones" "available" {
  state = "available"
  filter {
    name   = "opt-in-status"
    values = ["opt-in-not-required"]
  }
}

# Main VPC
resource "aws_vpc" "main" {
  cidr_block                           = var.vpc_cidr
  enable_dns_hostnames                 = true
  enable_dns_support                   = true
  enable_network_address_usage_metrics = true
  instance_tenancy                     = "default"

  tags = merge(local.common_tags, {
    Name        = "${local.naming.cluster_name}-vpc"
    Environment = var.environment
  })
}

# Public Subnets
resource "aws_subnet" "public" {
  count                   = 3
  vpc_id                  = aws_vpc.main.id
  cidr_block             = "10.0.${count.index + 1}.0/24"
  availability_zone      = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true

  tags = merge(local.common_tags, {
    Name                     = "${local.naming.cluster_name}-public-subnet-${count.index + 1}"
    Environment             = var.environment
    "kubernetes.io/role/elb" = "1"
    Tier                    = "public"
  })
}

# Private Subnets
resource "aws_subnet" "private" {
  count             = 3
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.${count.index + 11}.0/24"
  availability_zone = data.aws_availability_zones.available.names[count.index]

  tags = merge(local.common_tags, {
    Name                              = "${local.naming.cluster_name}-private-subnet-${count.index + 1}"
    Environment                       = var.environment
    "kubernetes.io/role/internal-elb" = "1"
    Tier                             = "private"
  })
}

# Internet Gateway
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = merge(local.common_tags, {
    Name        = "${local.naming.cluster_name}-igw"
    Environment = var.environment
  })
}

# Elastic IPs for NAT Gateways
resource "aws_eip" "nat" {
  count  = local.security.multi_az ? 3 : 1
  domain = "vpc"

  tags = merge(local.common_tags, {
    Name        = "${local.naming.cluster_name}-nat-eip-${count.index + 1}"
    Environment = var.environment
  })
}

# NAT Gateways
resource "aws_nat_gateway" "main" {
  count             = local.security.multi_az ? 3 : 1
  allocation_id     = aws_eip.nat[count.index].id
  subnet_id         = aws_subnet.public[count.index].id
  connectivity_type = "public"

  tags = merge(local.common_tags, {
    Name        = "${local.naming.cluster_name}-nat-${count.index + 1}"
    Environment = var.environment
    AZ          = data.aws_availability_zones.available.names[count.index]
  })

  depends_on = [aws_internet_gateway.main]
}

# Public Route Table
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = merge(local.common_tags, {
    Name        = "${local.naming.cluster_name}-public-rt"
    Environment = var.environment
    Type        = "public"
  })
}

# Private Route Tables
resource "aws_route_table" "private" {
  count  = local.security.multi_az ? 3 : 1
  vpc_id = aws_vpc.main.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main[count.index].id
  }

  tags = merge(local.common_tags, {
    Name        = "${local.naming.cluster_name}-private-rt-${count.index + 1}"
    Environment = var.environment
    Type        = "private"
  })
}

# Route Table Associations - Public
resource "aws_route_table_association" "public" {
  count          = 3
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# Route Table Associations - Private
resource "aws_route_table_association" "private" {
  count          = 3
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[min(count.index, local.security.multi_az ? 2 : 0)].id
}

# Security Group for ALB
resource "aws_security_group" "alb" {
  name_prefix = "${local.naming.cluster_name}-alb-"
  description = "Security group for Application Load Balancer"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "HTTP inbound"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS inbound"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "All outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, {
    Name        = "${local.naming.cluster_name}-alb-sg"
    Environment = var.environment
    Component   = "alb"
  })

  lifecycle {
    create_before_destroy = true
  }
}

# Security Group for ECS Tasks
resource "aws_security_group" "ecs" {
  name_prefix = "${local.naming.cluster_name}-ecs-"
  description = "Security group for ECS tasks"
  vpc_id      = aws_vpc.main.id

  ingress {
    description              = "Application port"
    from_port               = 8000
    to_port                 = 8000
    protocol                = "tcp"
    security_groups         = [aws_security_group.alb.id]
  }

  egress {
    description = "All outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, {
    Name        = "${local.naming.cluster_name}-ecs-sg"
    Environment = var.environment
    Component   = "ecs"
  })

  lifecycle {
    create_before_destroy = true
  }
}

# Outputs
output "vpc_id" {
  description = "ID of the created VPC"
  value       = aws_vpc.main.id
}

output "public_subnet_ids" {
  description = "List of public subnet IDs"
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "List of private subnet IDs"
  value       = aws_subnet.private[*].id
}

output "ecs_security_group_id" {
  description = "Security group ID for ECS tasks"
  value       = aws_security_group.ecs.id
}

output "alb_security_group_id" {
  description = "Security group ID for Application Load Balancer"
  value       = aws_security_group.alb.id
}

output "nat_gateway_ips" {
  description = "List of NAT Gateway public IPs"
  value       = aws_eip.nat[*].public_ip
}