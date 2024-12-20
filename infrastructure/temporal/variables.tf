# Core Terraform configuration
terraform {
  required_version = "~> 1.0"
}

# Environment variable with validation
variable "environment" {
  type        = string
  description = "Deployment environment (dev/staging/prod)"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod"
  }
}

# Temporal namespace configuration
variable "namespace_name" {
  type        = string
  description = "Name of the Temporal namespace for Memory Agent service"
  default     = "memory-agent-${var.environment}"
}

# Workflow history retention configuration
variable "retention_period" {
  type        = string
  description = "Workflow history retention period for maintaining execution records"
  default     = "30 days"
}

# Document search attributes configuration
variable "search_attributes" {
  type        = map(string)
  description = "Custom search attributes for document indexing and retrieval"
  default = {
    DocumentID         = "Keyword"
    DocumentFormat     = "Keyword"
    TokenCount        = "Int"
    LastAccessed      = "DateTime"
    VectorEmbedding   = "Binary"
    MetadataKeys      = "KeywordList"
    RetrievalStrategy = "Keyword"
    ContentHash       = "Keyword"
    ChunkCount        = "Int"
    UpdatedAt         = "DateTime"
    IndexStatus       = "Keyword"
  }
}

# Vector similarity search configuration
variable "vector_index_params" {
  type        = map(number)
  description = "HNSW vector index parameters for similarity search optimization"
  default = {
    dim             = 1536  # Dimension for OpenAI embeddings
    m               = 16    # Number of connections per layer
    ef_construction = 200   # Size of dynamic candidate list for construction
    ef_search       = 100   # Size of dynamic candidate list for search
    max_elements    = 100000 # Maximum number of vectors in the index
  }
}