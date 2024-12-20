# Terraform outputs configuration for Memory Agent Temporal infrastructure
# Version: ~> 1.0

# Output the Temporal namespace name for service integration
output "namespace_name" {
  description = "Name of the Temporal namespace for Memory Agent service, used for workflow isolation and resource organization"
  value       = temporal_namespace.memory_agent.name
  sensitive   = false
}

# Output the workflow history retention period configuration
output "retention_period" {
  description = "Workflow history retention period configuration defining how long workflow histories are preserved"
  value       = temporal_namespace.memory_agent.retention_period
  sensitive   = false
}

# Output the configured search attributes for document management
output "search_attributes" {
  description = "Custom search attributes configuration for document indexing, including metadata fields and search parameters"
  value       = temporal_search_attributes.document_search_attributes.custom_attributes
  sensitive   = false
}

# Output the vector search index configuration
output "vector_index_config" {
  description = "Vector search index configuration including HNSW parameters, dimension size, and similarity metrics for document retrieval"
  value       = temporal_search_attributes.document_search_attributes.vector_index
  sensitive   = true # Protected due to internal configuration details
}

# Output the complete namespace configuration for cross-module reference
output "namespace_config" {
  description = "Complete namespace configuration including search attributes and archival settings"
  value = {
    id                        = temporal_namespace.memory_agent.name
    retention_period         = temporal_namespace.memory_agent.retention_period
    history_archival_state   = temporal_namespace.memory_agent.history_archival_state
    visibility_archival_state = temporal_namespace.memory_agent.visibility_archival_state
    is_global               = temporal_namespace.memory_agent.is_global_namespace
  }
  sensitive = false
}

# Output search attribute validation rules
output "search_attribute_validation" {
  description = "Validation rules configured for search attributes and vector indices"
  value = {
    required_types     = temporal_search_attributes.document_search_attributes.attribute_validation.required_types
    name_pattern      = temporal_search_attributes.document_search_attributes.attribute_validation.name_pattern
    encryption_enabled = temporal_search_attributes.document_search_attributes.attribute_validation.encryption_enabled
  }
  sensitive = true # Protected due to security configuration
}

# Output vector index validation parameters
output "vector_index_validation" {
  description = "Vector index validation parameters for similarity search configuration"
  value = {
    dimension_range        = temporal_search_attributes.document_search_attributes.vector_index.validation_rules.dimension_range
    m_minimum             = temporal_search_attributes.document_search_attributes.vector_index.validation_rules.m_minimum
    ef_construction_ratio = temporal_search_attributes.document_search_attributes.vector_index.validation_rules.ef_construction_ratio
  }
  sensitive = false
}