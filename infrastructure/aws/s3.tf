# AWS S3 Configuration for Memory Agent Document Storage
# Version: ~> 4.0
# Purpose: Defines S3 bucket resources with versioning, encryption, and lifecycle policies
# Security Level: High with KMS encryption and strict access controls

# Main document storage bucket
resource "aws_s3_bucket" "document_storage" {
  bucket        = local.naming.s3_bucket
  force_destroy = !local.security.multi_az # Only allow force destroy in non-production

  # Apply comprehensive tagging strategy
  tags = merge(local.common_tags, {
    Name        = "Document Storage Bucket"
    Description = "Primary storage for Memory Agent documents"
    BackupType  = "Versioned"
    Encryption  = "KMS"
  })
}

# Enable versioning for document history and recovery
resource "aws_s3_bucket_versioning" "document_versioning" {
  bucket = aws_s3_bucket.document_storage.id
  versioning_configuration {
    status = local.security.multi_az ? "Enabled" : "Suspended"
  }
}

# Configure server-side encryption using KMS
resource "aws_s3_bucket_server_side_encryption_configuration" "document_encryption" {
  bucket = aws_s3_bucket.document_storage.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.document_kms_key.arn
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

# Configure lifecycle rules for cost optimization
resource "aws_s3_bucket_lifecycle_configuration" "document_lifecycle" {
  bucket = aws_s3_bucket.document_storage.id

  rule {
    id     = "document_retention"
    status = "Enabled"

    # Transition to Intelligent-Tiering after 30 days
    transition {
      days          = 30
      storage_class = "INTELLIGENT_TIERING"
    }

    # Archive old versions after 90 days
    noncurrent_version_transition {
      noncurrent_days = 90
      storage_class   = "GLACIER"
    }

    # Expire old versions based on environment retention policy
    expiration {
      days = local.backup.retention_days
    }

    # Clean up incomplete multipart uploads
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

# Block all public access
resource "aws_s3_bucket_public_access_block" "document_access" {
  bucket = aws_s3_bucket.document_storage.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Enable access logging
resource "aws_s3_bucket_logging" "document_logging" {
  bucket = aws_s3_bucket.document_storage.id

  target_bucket = aws_s3_bucket.document_storage.id
  target_prefix = "access-logs/"
}

# Configure CORS for API access
resource "aws_s3_bucket_cors_configuration" "document_cors" {
  bucket = aws_s3_bucket.document_storage.id

  cors_rule {
    allowed_headers = ["Authorization", "Content-Length"]
    allowed_methods = ["GET", "PUT", "POST"]
    allowed_origins = ["https://*.memory-agent.internal"]
    expose_headers  = ["ETag"]
    max_age_seconds = 3600
  }
}

# Enable bucket replication for production environment
resource "aws_s3_bucket_replication_configuration" "document_replication" {
  count = local.security.multi_az ? 1 : 0

  bucket = aws_s3_bucket.document_storage.id
  role   = aws_iam_role.replication_role.arn

  rule {
    id     = "document-replication"
    status = "Enabled"

    destination {
      bucket        = aws_s3_bucket.document_storage_replica[0].arn
      storage_class = "STANDARD_IA"

      encryption_configuration {
        replica_kms_key_id = aws_kms_key.document_kms_key_replica[0].arn
      }
    }

    source_selection_criteria {
      sse_kms_encrypted_objects {
        status = "Enabled"
      }
    }
  }
}

# Configure bucket policy
resource "aws_s3_bucket_policy" "document_policy" {
  bucket = aws_s3_bucket.document_storage.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "EnforceSSLOnly"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.document_storage.arn,
          "${aws_s3_bucket.document_storage.arn}/*"
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      },
      {
        Sid       = "EnforceKMSEncryption"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:PutObject"
        Resource  = "${aws_s3_bucket.document_storage.arn}/*"
        Condition = {
          StringNotEquals = {
            "s3:x-amz-server-side-encryption" = "aws:kms"
          }
        }
      }
    ]
  })
}

# Configure bucket notification for document processing
resource "aws_s3_bucket_notification" "document_notification" {
  bucket = aws_s3_bucket.document_storage.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.document_processor.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "uploads/"
    filter_suffix       = ".json"
  }

  depends_on = [aws_lambda_permission.allow_bucket]
}