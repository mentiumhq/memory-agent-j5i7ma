# Temporal provider version 0.2.0
terraform {
  required_providers {
    temporal = {
      source  = "temporalio/temporal"
      version = "~> 0.2.0"
    }
  }
}

# Data source for retrieving existing Temporal namespace information
data "temporal_namespace" "memory_agent" {
  name = var.namespace_name

  timeouts {
    read = "5m"
  }

  lifecycle {
    prevent_destroy = true
  }
}

# Data source for retrieving existing search attributes configuration
data "temporal_search_attributes" "document_search" {
  namespace = var.namespace_name

  custom_attributes = {
    DocumentID       = "Keyword"
    ContentType     = "Keyword"
    TokenCount      = "Int"
    VectorEmbedding = "Binary"
    MetadataFields  = "KeywordList"
    LastAccessed    = "Datetime"
    ProcessingStatus = "Keyword"
  }
}

# Data source for retrieving Temporal cluster information
data "temporal_cluster_info" "cluster" {
  query = {
    include_capacity        = true
    include_scaling        = true
    include_workflow_config = true
    include_version_info    = true
  }

  timeouts {
    read = "5m"
  }
}

# Output exported namespace information
output "namespace_info" {
  description = "Comprehensive Temporal namespace information"
  value = {
    id               = data.temporal_namespace.memory_agent.id
    name             = data.temporal_namespace.memory_agent.name
    state            = data.temporal_namespace.memory_agent.state
    retention_period = data.temporal_namespace.memory_agent.retention_period
    isolation_group  = data.temporal_namespace.memory_agent.isolation_group
    permissions      = data.temporal_namespace.memory_agent.permissions
  }
  sensitive = false
}

# Output exported search attributes configuration
output "search_attributes_config" {
  description = "Enhanced search attributes configuration for document indexing"
  value = {
    custom_attributes  = data.temporal_search_attributes.document_search.custom_attributes
    system_attributes = data.temporal_search_attributes.document_search.system_attributes
    index_settings    = data.temporal_search_attributes.document_search.index_settings
    vector_config     = data.temporal_search_attributes.document_search.vector_config
  }
  sensitive = false
}

# Output exported cluster information
output "cluster_info" {
  description = "Comprehensive cluster information including capacity and configuration"
  value = {
    version          = data.temporal_cluster_info.cluster.version
    cluster_id       = data.temporal_cluster_info.cluster.cluster_id
    capacity_info    = data.temporal_cluster_info.cluster.capacity_info
    scaling_config   = data.temporal_cluster_info.cluster.scaling_config
    workflow_config  = data.temporal_cluster_info.cluster.workflow_config
  }
  sensitive = false
}