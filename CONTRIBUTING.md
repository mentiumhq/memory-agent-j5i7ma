# Contributing to Memory Agent

Welcome to the Memory Agent project! This document provides comprehensive guidelines for contributing to the project. Please read this guide carefully to ensure your contributions meet our quality and security standards.

## Table of Contents
- [Introduction](#introduction)
- [Development Setup](#development-setup)
- [Development Workflow](#development-workflow)
- [Code Quality Standards](#code-quality-standards)
- [Security Requirements](#security-requirements)
- [Testing Guidelines](#testing-guidelines)
- [Documentation Requirements](#documentation-requirements)
- [Release Process](#release-process)

## Introduction

### Project Overview
Memory Agent is a Temporal workflow-based document storage and retrieval service designed to serve as an intelligent memory layer for LLM-based agents. The system implements multiple retrieval strategies including vector-based search, pure LLM reasoning, hybrid approaches, and RAG with Knowledge Graphs.

### Code of Conduct
We are committed to providing a welcoming and inclusive environment. All contributors are expected to adhere to our code of conduct, which promotes respectful and professional interaction within our community.

### License
This project is licensed under [LICENSE]. All contributions must comply with this license and should not introduce dependencies with conflicting licenses.

### Communication Channels
- GitHub Issues: Bug reports and feature requests
- Pull Requests: Code review discussions
- Project Discussions: General questions and architectural discussions
- Security Issues: Send confidential security reports to [security@memoryagent.com]

## Development Setup

### Prerequisites
1. Python 3.11 or higher
2. Poetry 1.5+ for dependency management
3. Docker and Docker Compose
4. Git 2.0+

### Environment Setup
```bash
# Clone the repository
git clone https://github.com/yourusername/memory-agent.git
cd memory-agent

# Install Poetry
curl -sSL https://install.python-poetry.org | python3 -

# Install dependencies
poetry install

# Install pre-commit hooks
pre-commit install
```

### Development Tools Configuration
```toml
# pyproject.toml
[tool.poetry]
python = "^3.11"

[tool.black]
line-length = 88
target-version = ['py311']

[tool.mypy]
python_version = "3.11"
strict = true

[tool.pytest]
minversion = "7.4"
addopts = "-ra -q --cov=memory_agent --cov-report=xml --cov-report=term-missing"
```

## Development Workflow

### Branch Naming Convention
- `feature/` - New features or enhancements
- `bugfix/` - Bug fixes
- `hotfix/` - Critical production fixes
- `release/` - Release preparation

### Commit Message Format
```
type(scope): description

[optional body]

[optional footer]
```
Types: feat, fix, docs, style, refactor, test, chore

### Pull Request Process
1. Create a new branch following naming convention
2. Implement changes with tests and documentation
3. Ensure all checks pass locally
4. Submit PR using the provided template
5. Address review feedback
6. Maintain branch up-to-date with main
7. Squash commits before merge

## Code Quality Standards

### Code Formatting
- Black (version 23.+) for consistent formatting
- Maximum line length: 88 characters
- Enforced via pre-commit hooks

### Type Checking
- mypy (version 1.5+) with strict mode enabled
- Zero type errors allowed
- All functions must include type hints

### Testing Requirements
- Minimum 90% code coverage
- Unit tests for all new code
- Integration tests for workflows
- Performance benchmarks where applicable

### Documentation Standards
- Docstrings for all public APIs (Google style)
- README updates for new features
- Architecture documentation updates
- Changelog entries

## Security Requirements

### Security Scanning
- Snyk for dependency scanning
- Trivy for container scanning
- Zero high-severity issues allowed

### Secrets Management
- AWS KMS for key management
- No hardcoded secrets
- Environment variables for configuration

### Security Review Process
1. Automated security scans
2. Manual security review for sensitive changes
3. Compliance verification
4. Vulnerability assessment

## Testing Guidelines

### Test Structure
```python
# Example test structure
def test_feature_name():
    # Arrange
    test_data = setup_test_data()
    
    # Act
    result = feature_under_test(test_data)
    
    # Assert
    assert result == expected_result
```

### Test Coverage Requirements
- Unit tests: 90% minimum coverage
- Integration tests: Critical paths covered
- Performance tests: Response time thresholds
- Security tests: Authentication/authorization

## Documentation Requirements

### Code Documentation
```python
def function_name(param: type) -> return_type:
    """Short description.

    Detailed description of function behavior.

    Args:
        param: Parameter description

    Returns:
        Description of return value

    Raises:
        ExceptionType: Description of when this occurs
    """
```

### API Documentation
- OpenAPI/Swagger for REST endpoints
- Protocol buffers for gRPC interfaces
- Example requests and responses
- Error scenarios and handling

## Release Process

### Version Numbering
- MAJOR: Breaking changes
- MINOR: New features, backward-compatible
- PATCH: Bug fixes, backward-compatible

### Release Checklist
1. Version bump
2. Changelog update
3. Documentation review
4. Security scan
5. Performance testing
6. Deployment verification
7. Rollback procedure verification

### Deployment Process
1. Create release branch
2. Run full test suite
3. Generate release artifacts
4. Deploy to staging
5. Verification testing
6. Production deployment
7. Post-deployment monitoring

## Quality Gates

The following quality gates must pass before merge:

- [ ] Code coverage ≥90%
- [ ] All tests passing
- [ ] No mypy errors
- [ ] Black formatting verified
- [ ] Security scan passed
- [ ] Documentation updated
- [ ] PR template completed
- [ ] Changelog updated

For detailed CI/CD workflow information, see `.github/workflows/ci.yml`.