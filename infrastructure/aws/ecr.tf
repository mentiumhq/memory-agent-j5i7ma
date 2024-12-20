# AWS ECR configuration for Memory Agent service
# Terraform version: ~> 1.0
# AWS Provider version: ~> 4.0

# Create ECR repository for Memory Agent container images
resource "aws_ecr_repository" "main" {
  name                 = "${var.app_name}-${var.environment}"
  image_tag_mutability = "IMMUTABLE"  # Ensures image tags cannot be overwritten

  # Enable image scanning on push for security
  image_scanning_configuration {
    scan_on_push = true
  }

  # Enable KMS encryption for container images
  encryption_configuration {
    encryption_type = "KMS"
  }

  # Apply common tags
  tags = var.tags
}

# Configure lifecycle policy for ECR repository
resource "aws_ecr_lifecycle_policy" "main" {
  repository = aws_ecr_repository.main.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 30 production images"
        selection = {
          tagStatus     = "tagged"
          tagPrefixList = ["prod"]
          countType     = "imageCountMoreThan"
          countNumber   = 30
        }
        action = {
          type = "expire"
        }
      },
      {
        rulePriority = 2
        description  = "Keep last 10 staging images"
        selection = {
          tagStatus     = "tagged"
          tagPrefixList = ["staging"]
          countType     = "imageCountMoreThan"
          countNumber   = 10
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

# Output the repository URL and ARN for use in other resources
output "repository_url" {
  description = "URL of the created ECR repository"
  value       = aws_ecr_repository.main.repository_url
}

output "repository_arn" {
  description = "ARN of the created ECR repository"
  value       = aws_ecr_repository.main.arn
}