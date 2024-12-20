# Memory Agent Infrastructure Documentation

Comprehensive infrastructure documentation for the Memory Agent system, detailing AWS services, Temporal configurations, security protocols, and operational procedures.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Infrastructure Components](#infrastructure-components)
  - [AWS Resources](#aws-resources)
  - [Temporal Resources](#temporal-resources)
- [Setup Instructions](#setup-instructions)
- [Maintenance Guidelines](#maintenance-guidelines)
- [Troubleshooting](#troubleshooting)

## Prerequisites

Before proceeding with infrastructure deployment, ensure the following tools are installed and properly configured:

| Tool | Required Version | Purpose |
|------|-----------------|----------|
| AWS CLI | v2.x | AWS resource management |
| Terraform | >= 1.5.0 | Infrastructure as Code |
| Docker | >= 24.0.0 | Container runtime |
| Docker Compose | >= 2.20.0 | Local development orchestration |
| Python | 3.11+ | Runtime environment |
| OpenSSL | >= 3.0.0 | Security and encryption |
| jq | >= 1.6 | JSON processing |
| make | >= 4.3 | Build automation |

## Infrastructure Components

### AWS Resources

#### ECS Fargate Configuration
- Instance Type: t3.medium (minimum)
- Auto-scaling configuration
- Spot instance support for cost optimization
- Custom task definitions with resource limits

#### S3 Storage
- Versioning enabled
- SSE-KMS encryption
- Cross-region replication
- Lifecycle policies for cost management

#### Monitoring and Security
- CloudWatch with custom metrics
- Route 53 health checks and failover
- KMS with automatic key rotation
- ECR vulnerability scanning

### Temporal Resources

#### Namespace Configuration
- Production namespace: `memory-agent-prod`
- History retention: 30 days
- Custom search attributes for document metadata
- Archival configuration enabled

#### Worker Configuration
- Resource limits:
  - CPU: 2 vCPU
  - Memory: 4GB
  - Concurrency: 20 workflows
- Error handling with retry policies
- Activity timeouts configured

## Setup Instructions

### 1. Initialize Infrastructure
```bash
make init-infrastructure
```
This command:
- Initializes Terraform backend
- Validates AWS credentials
- Checks prerequisite tools

### 2. Configure Environment
```bash
make configure-env ENV=<dev|staging|prod>
```
Environment-specific configurations:
- Development: Local resources with Minio
- Staging: Reduced AWS resource allocation
- Production: Full HA configuration

### 3. Deploy Infrastructure
```bash
make deploy-infrastructure ENV=<dev|staging|prod>
```
Deploys:
- ECS clusters and services
- S3 buckets with proper configurations
- Temporal namespaces and workers
- Monitoring and security components

### 4. Verify Deployment
```bash
make verify-deployment ENV=<dev|staging|prod>
```
Runs validation tests for:
- Service health checks
- Security configurations
- Resource provisioning
- Connectivity tests

## Maintenance Guidelines

### Backup Strategy
1. Automated Backups
   - Hourly SQLite WAL shipping to S3
   - Cross-region S3 replication
   - Daily Terraform state backups
   - Weekly system snapshots

2. Monitoring Setup
   - CloudWatch metrics (1-minute resolution)
   - Custom ECS container insights
   - S3 access logging (90-day retention)
   - Temporal workflow metrics

3. Security Maintenance
   - 90-day KMS key rotation
   - Least-privilege IAM management
   - Weekly security group audit
   - Monthly penetration testing

## Troubleshooting

### Common Issues and Resolutions

#### ECS Deployment Failures
**Resolution:**
- Check CloudWatch logs at `/aws/ecs/memory-agent`
- Verify task definition and resource allocation
- Review service auto-scaling policies

#### S3 Access Issues
**Resolution:**
- Verify IAM roles and bucket policies
- Check VPC endpoints configuration
- Review encryption settings

#### Temporal Connection Problems
**Resolution:**
- Validate worker configurations
- Check namespace settings
- Review network security groups

#### Performance Degradation
**Resolution:**
- Monitor ECS metrics
- Check scaling policies
- Analyze CloudWatch insights
- Review resource utilization

## Security Protocols

### Authentication and Authorization
- JWT-based authentication
- mTLS for service-to-service communication
- IAM role-based access control
- Temporal namespace isolation

### Encryption Standards
- TLS 1.3 for in-transit encryption
- KMS-managed keys for at-rest encryption
- Secure secret management
- Regular security audits

## Resource Scaling

### Auto-scaling Configuration
- ECS service scaling based on CPU/Memory
- Temporal worker pool scaling
- S3 performance optimization
- CloudWatch alarms for scaling triggers

## Monitoring and Alerting

### Metrics Collection
- Custom CloudWatch dashboards
- Temporal workflow metrics
- Infrastructure health monitoring
- Security event logging

### Alert Configuration
- Critical service disruptions
- Resource utilization thresholds
- Security incidents
- Backup failure notifications

## Disaster Recovery

### Backup Procedures
- Automated system backups
- Cross-region replication
- State file backups
- Configuration backups

### Recovery Procedures
- Service restoration process
- Data recovery steps
- Configuration restoration
- Validation procedures