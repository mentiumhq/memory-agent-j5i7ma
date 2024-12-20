# Memory Agent

[![CI Status](https://github.com/username/memory-agent/workflows/ci/badge.svg)]
[![Code Coverage](https://codecov.io/gh/username/memory-agent/branch/main/graph/badge.svg)]
[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)]
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)]

Memory Agent is a Temporal workflow-based document storage and retrieval service designed to serve as an intelligent memory layer for LLM-based agents. The system provides context-aware document retrieval through multiple strategies including vector-based search, pure LLM reasoning, hybrid approaches, and RAG with Knowledge Graphs.

## Features

- **Intelligent Document Storage**
  - Token-aware document chunking
  - Secure encryption at rest and in transit
  - Efficient metadata indexing
  - Versioned document storage

- **Multi-Strategy Retrieval**
  - Vector-based similarity search
  - Pure LLM reasoning and selection
  - Hybrid retrieval approaches
  - RAG with Knowledge Graphs

- **Enterprise-Ready Architecture**
  - Fault-tolerant Temporal workflows
  - Automatic retry mechanisms
  - Comprehensive monitoring
  - High concurrency support
  - Scalable cloud-native design

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose (latest)
- Poetry 1.5+
- Terraform 1.0+ (for production deployment)
- AWS CLI 2.0+ (for production deployment)
- Temporal CLI 1.0+

### Local Development Setup

1. Clone the repository:
```bash
git clone https://github.com/username/memory-agent.git
cd memory-agent
```

2. Install dependencies:
```bash
poetry install
```

3. Configure local environment:
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. Start local services:
```bash
docker-compose up -d
```

5. Initialize development environment:
```bash
poetry run python scripts/init_dev.py
```

### Basic Usage

```python
from memory_agent import MemoryAgent

# Initialize agent
agent = MemoryAgent()

# Store document
doc_id = await agent.store_document(
    content="Document content",
    metadata={"format": "markdown"}
)

# Retrieve document using vector search
result = await agent.retrieve_document(
    query="Search query",
    strategy="vector"
)
```

## Development

### Testing

```bash
# Run unit tests
poetry run pytest

# Run integration tests
poetry run pytest tests/integration

# Run with coverage
poetry run pytest --cov=memory_agent
```

### Code Quality

```bash
# Format code
poetry run black .

# Type checking
poetry run mypy .

# Linting
poetry run pylint memory_agent
```

## Deployment

### Production Setup

1. Configure AWS credentials:
```bash
aws configure
```

2. Deploy infrastructure:
```bash
cd infrastructure
terraform init
terraform apply
```

3. Configure environment:
```bash
# Set production environment variables
export MEMORY_AGENT_ENV=production
export AWS_REGION=us-west-2
# Additional environment variables...
```

4. Deploy application:
```bash
./scripts/deploy.sh production
```

### Monitoring

- CloudWatch Metrics Dashboard: `https://console.aws.amazon.com/cloudwatch/`
- OpenTelemetry Traces: `https://your-jaeger-instance/`
- Temporal UI: `https://temporal.your-domain.com/`

## Documentation

- [API Documentation](./docs/api.md)
- [Architecture Overview](./docs/architecture.md)
- [Configuration Guide](./docs/configuration.md)
- [Deployment Guide](./docs/deployment.md)
- [Troubleshooting](./docs/troubleshooting.md)

## Contributing

Please read our [Contributing Guidelines](CONTRIBUTING.md) for details on our code of conduct, development workflow, and pull request process.

## Performance Targets

- Retrieval Accuracy: >90% relevant document selection
- System Availability: 99.9% uptime
- Response Time: 
  - Vector search: <500ms
  - LLM-based: <3000ms
- Concurrent Requests: 50 requests/second

## Security

- JWT + mTLS authentication
- AES-256 encryption at rest
- TLS 1.3 for data in transit
- Role-based access control
- Regular security audits

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Links

- [Backend Setup](src/backend/README.md)
- [Infrastructure Guide](infrastructure/README.md)
- [Full Documentation](./docs)

## Maintenance

- Documentation updates: Monthly minimum
- Version updates: Following semantic versioning
- Security patches: As needed, high priority
- Performance monitoring: Continuous with weekly reviews

---
Built with ❤️ by the Memory Agent Team