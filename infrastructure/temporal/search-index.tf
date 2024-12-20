# Terraform configuration for Memory Agent search index attributes
# Version: ~> 1.0

# Configure Temporal provider
provider "temporal" {
  version = "~> 0.2.0"
}

# Data source to fetch existing search attributes
data "temporal_search_attributes" "existing_search_attributes" {
  namespace = temporal_namespace.name
}

# Local variables for validation and attribute merging
locals {
  # Combine existing and new search attributes
  combined_search_attributes = merge(
    data.existing_search_attributes.custom_attributes,
    var.search_attributes
  )

  # Validation rules for vector index parameters
  vector_index_validation = {
    dimension_valid = contains([768, 1024, 1536], var.vector_index_params.dim)
    m_valid = var.vector_index_params.m >= 16
    ef_construction_valid = var.vector_index_params.ef_construction >= var.vector_index_params.m * 2
  }
}

# Search attributes resource configuration
resource "temporal_search_attributes" "document_search_attributes" {
  namespace = temporal_namespace.name
  custom_attributes = var.search_attributes

  # Vector similarity search index configuration
  vector_index {
    name = "document_vectors"
    dimension = var.vector_index_params.dim
    m = var.vector_index_params.m
    ef_construction = var.vector_index_params.ef_construction
    metric = "cosine"  # Using cosine similarity for document vectors

    # Validation rules for vector index parameters
    validation_rules {
      dimension_range = [768, 1536]  # Support for different embedding models
      m_minimum = 16  # Minimum connections per layer
      ef_construction_ratio = 2.0  # Minimum ratio for ef_construction to m
    }
  }

  # Attribute validation configuration
  attribute_validation {
    required_types = [
      "Text",      # For full-text content
      "Keyword",   # For exact match fields
      "Int",       # For numeric values
      "Double",    # For floating-point values
      "Bool",      # For boolean flags
      "Datetime"   # For temporal values
    ]
    name_pattern = "^[a-zA-Z][a-zA-Z0-9_]{2,63}$"  # Valid attribute name pattern
    encryption_enabled = true  # Enable encryption for sensitive attributes
  }

  # Ensure vector index parameters are valid
  lifecycle {
    precondition {
      condition = local.vector_index_validation.dimension_valid
      error_message = "Vector dimension must be one of: 768, 1024, or 1536"
    }

    precondition {
      condition = local.vector_index_validation.m_valid
      error_message = "Parameter 'm' must be at least 16"
    }

    precondition {
      condition = local.vector_index_validation.ef_construction_valid
      error_message = "ef_construction must be at least 2 times the value of 'm'"
    }
  }

  # Depend on namespace creation
  depends_on = [
    temporal_namespace.name
  ]
}

# Output the search attributes configuration
output "search_attributes_config" {
  description = "Configured search attributes for the Memory Agent"
  value = {
    namespace = temporal_search_attributes.document_search_attributes.namespace
    custom_attributes = temporal_search_attributes.document_search_attributes.custom_attributes
    vector_index = temporal_search_attributes.document_search_attributes.vector_index
  }
  sensitive = true  # Protect sensitive configuration details
}