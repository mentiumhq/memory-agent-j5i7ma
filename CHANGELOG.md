# Changelog
All notable changes to the Memory Agent project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial implementation of document storage and retrieval service
  - Document storage with S3/Minio integration (#1)
  - Multi-strategy retrieval system with vector search, LLM, and hybrid approaches (#2)
  - Token-aware document chunking for LLM compatibility (#3)
  - Contributor: @core-team

### Changed
- Temporal workflow implementation for document operations
  - Migration to workflow-based architecture (#4)
  - Breaking Change: API restructuring for workflow compatibility
  - Migration Guide: [Workflow Migration Guide](docs/migration/workflow-migration.md)
  - Issue Reference: #5

### Deprecated
- Legacy direct storage methods
  - To be removed in version 2.0.0
  - Alternative: Use new workflow-based storage activities
  - Issue Reference: #6

### Removed
- Direct database access endpoints
  - Breaking Change: All database operations now through workflows
  - Migration Guide: [API Migration Guide](docs/migration/api-migration.md)
  - Issue Reference: #7

### Fixed
- Token counting accuracy in document chunking
  - Improved handling of special characters and Unicode
  - Issue Reference: #8
  - Contributor: @performance-team

### Security
- Implemented comprehensive security measures
  - Description: Added TLS 1.3 and mTLS for service communication
  - CVE Reference: CVE-2023-XXXXX
  - Severity Level: High
  - Patch Requirements: Update to latest version and rotate certificates

## [0.1.0] - 2023-12-01

### Added
- Core system architecture and base components
  - SQLite metadata storage (#10)
  - S3 document storage integration (#11)
  - Basic vector search capability (#12)
  - Temporal workflow foundation (#13)

### Changed
- Initial system configuration
  - Environment setup and configuration management (#14)
  - Service deployment architecture (#15)

### Security
- Basic security implementation
  - JWT authentication system (#16)
  - Data encryption at rest (#17)
  - Description: Initial security framework implementation
  - Severity Level: Medium
  - Patch Requirements: None (initial release)

[Unreleased]: https://github.com/owner/memory-agent/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/owner/memory-agent/releases/tag/v0.1.0