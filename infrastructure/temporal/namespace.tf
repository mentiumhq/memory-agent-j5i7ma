# Configure Terraform and required providers
terraform {
  required_providers {
    temporal = {
      source  = "temporalio/temporal"
      version = "~> 0.2.0"
    }
  }
}

# Define the Temporal namespace resource for Memory Agent service
resource "temporal_namespace" "memory_agent" {
  name        = var.namespace_name
  description = "Memory Agent service namespace for ${var.environment} environment with enhanced document management capabilities"
  
  # Configure retention and archival settings
  retention_period           = var.retention_period
  is_global_namespace       = true
  history_archival_state    = "ENABLED"
  visibility_archival_state = "ENABLED"
  
  # Configure base search attributes from variables
  search_attributes = var.search_attributes
  
  # Configure extended custom search attributes for comprehensive document management
  custom_search_attributes = {
    # Document-specific attributes
    DocumentID         = "Keyword"     # Unique identifier for documents
    DocumentFormat     = "Keyword"     # Format of stored documents (markdown, json, etc.)
    TokenCount        = "Int"         # Number of tokens in the document
    LastAccessed      = "DateTime"    # Last access timestamp
    VectorEmbedding   = "Binary"      # Document vector embeddings for similarity search
    MetadataKeys      = "KeywordList" # List of metadata keys for filtering
    
    # Workflow execution attributes
    RetrievalStrategy = "Keyword"     # Strategy used for document retrieval
    SecurityLevel     = "Keyword"     # Document security classification
    ProcessingStatus  = "Keyword"     # Current status of document processing
    
    # Operational metrics
    ErrorCount       = "Int"         # Number of processing errors
    RetryCount       = "Int"         # Number of retry attempts
    ExecutionTime    = "Int"         # Workflow execution duration
    WorkflowType     = "Keyword"     # Type of workflow executed
  }
}

# Data source to fetch namespace information
data "temporal_namespace" "namespace_info" {
  name = var.namespace_name
  
  depends_on = [
    temporal_namespace.memory_agent
  ]
}

# Export namespace attributes for other configurations
output "namespace_id" {
  description = "ID of the created Temporal namespace"
  value       = temporal_namespace.memory_agent.name
}

output "namespace_retention" {
  description = "Configured retention period for the namespace"
  value       = temporal_namespace.memory_agent.retention_period
}

output "namespace_search_attributes" {
  description = "Configured search attributes for document management"
  value       = temporal_namespace.memory_agent.custom_search_attributes
}