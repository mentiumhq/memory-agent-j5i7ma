# Pull Request Template

## Description

### Summary
<!-- Provide a concise description of the changes implemented -->

### Motivation
<!-- Explain the business or technical justification for these changes -->

### Technical Approach
<!-- Describe the technical approach and key architectural decisions -->

## Type of Change
<!-- Check all that apply -->
- [ ] New Feature
- [ ] Bug Fix
- [ ] Documentation Update
- [ ] Performance Improvement
- [ ] Security Enhancement
- [ ] Dependency Update
- [ ] Infrastructure Change
- [ ] Breaking Change

## Testing
<!-- All testing requirements must be satisfied -->

### Test Coverage Confirmation
- [ ] Test coverage exceeds 90% threshold

### Test Types
- [ ] Unit Tests Added
- [ ] Integration Tests Added
- [ ] Performance Tests Updated
- [ ] Security Tests Completed
- [ ] Load Tests (if applicable)
- [ ] Temporal Workflow Tests

## Security
<!-- All security requirements must be addressed -->

### Security Impact Analysis
<!-- Provide detailed analysis of security implications -->

### Security Checks
- [ ] Snyk Scan Passed
- [ ] Trivy Container Scan Passed
- [ ] Secret Detection Scan Clean
- [ ] Authentication Changes Reviewed
- [ ] Authorization Changes Reviewed
- [ ] Data Protection Impact Assessed
- [ ] Encryption Requirements Met

## Documentation
<!-- All documentation must be kept up to date -->

### Documentation Updates
- [ ] API Documentation Updated
- [ ] README Changes
- [ ] Architecture Diagrams Updated
- [ ] Technical Specification Updated
- [ ] Security Documentation Updated
- [ ] Workflow Documentation Updated
- [ ] Code Comments Added

## Dependencies

### Dependent Pull Requests/Issues
<!-- List any dependent PRs or issues -->

### Breaking Changes
- [ ] This change includes breaking changes

### Dependency Updates
- [ ] Python Dependencies Updated
- [ ] Container Base Images Updated
- [ ] Infrastructure Dependencies Updated
- [ ] API Dependencies Reviewed

## Review Requirements

### Required Reviewers
<!-- Auto-populated based on CODEOWNERS -->
- [ ] Security Team Review (required for security changes)
- [ ] Architecture Team Review (required for architectural changes)

### Review Checklist
- [ ] Code Quality Standards Met
- [ ] Security Requirements Satisfied
- [ ] Performance Impact Acceptable
- [ ] Architecture Guidelines Followed
- [ ] Error Handling Implemented
- [ ] Monitoring/Logging Added
- [ ] Resource Usage Optimized

## Validation Rules
<!-- All validation rules must pass before merge -->
- [ ] All CI workflow checks passing
- [ ] Test coverage threshold (>90%) met
- [ ] Security team approval (if required)
- [ ] Architecture team approval (if required)
- [ ] Documentation requirements satisfied

---
<!-- 
Note: This PR template enforces comprehensive documentation, testing, security compliance, 
and review requirements for the Memory Agent system. All sections marked as required 
must be completed before the PR can be merged.
-->