# Cloud Management Platform - System Architecture

## Overview

This document describes the architecture of a cloud management platform built on top of Proxmox VE, designed for large-scale deployments (500+ users, 1000+ VMs) with multi-datacenter support.

## Architecture Principles

- **Microservices Architecture**: Loosely coupled services for scalability and maintainability
- **Multi-tenancy**: Complete isolation between organizations
- **API-First Design**: All functionality exposed via REST APIs
- **Horizontal Scalability**: Scale services independently based on load
- **High Availability**: No single points of failure
- **Event-Driven**: Asynchronous processing for long-running operations

## System Components

### 1. Frontend Layer

#### Web Portal (React/Vue)
- **User Portal**: Self-service VM/container management
- **Admin Dashboard**: Platform administration and monitoring
- **Organization Dashboard**: Tenant management and billing

Technology: React with TypeScript, Tailwind CSS, TanStack Query

### 2. API Gateway Layer

#### API Gateway (Kong/NGINX)
- Request routing and load balancing
- Rate limiting and throttling
- SSL termination
- Request/response transformation
- Authentication enforcement

### 3. Backend Services (Microservices)

#### Core API Service (FastAPI)
- User authentication and authorization
- Organization/tenant management
- Resource quota management
- User and role management
- Central business logic

#### VM Orchestration Service (FastAPI)
- VM lifecycle management (create, start, stop, delete)
- Template management
- Snapshot and backup operations
- VM migration coordination
- Proxmox cluster selection and load balancing

#### Network Service (FastAPI)
- VLAN management and allocation
- IP address management (IPAM)
- Firewall rule management
- Load balancer configuration
- VPN and networking

#### Storage Service (FastAPI)
- Storage pool management
- Disk allocation and management
- Storage quotas
- Backup storage coordination

#### Metering Service (FastAPI)
- Resource usage tracking (CPU hours, RAM, storage)
- Usage metrics collection
- Usage reporting and analytics
- Quota enforcement

#### Monitoring Service (FastAPI)
- VM performance metrics collection
- Health checks and alerting
- Log aggregation coordination
- System status dashboard

### 4. Message Queue Layer

#### RabbitMQ/Redis Streams
- Asynchronous task processing
- Event distribution across services
- Job queue for long-running operations
- Inter-service communication

### 5. Worker Services

#### Task Workers (Celery)
- VM provisioning tasks
- Backup operations
- Resource cleanup
- Scheduled maintenance tasks
- Report generation

### 6. Data Layer

#### PostgreSQL (Primary Database)
- User and organization data
- VM metadata and configuration
- Resource allocations and quotas
- Audit logs
- Billing/usage data

Deployment: PostgreSQL cluster with replication (Primary + Read Replicas)

#### Redis (Cache + Sessions)
- Session storage
- API response caching
- Real-time data caching
- Rate limiting state
- Lock management

#### TimescaleDB/InfluxDB (Time-Series)
- VM performance metrics
- Resource usage metrics
- System monitoring data
- Historical trends

### 7. Hypervisor Layer

#### Proxmox VE Clusters
- Multiple Proxmox clusters across datacenters
- Each cluster managed via Proxmox API
- Integration via `proxmoxer` Python library
- Connection pooling and retry logic

### 8. Supporting Services

#### Authentication Service
- JWT token generation and validation
- Password hashing and verification
- Session management
- API key management

#### Notification Service
- Email notifications
- Webhook integrations
- Alert delivery
- System notifications

#### Audit Service
- Comprehensive audit logging
- Compliance reporting
- Change tracking
- Security event logging

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         USERS / CLIENTS                          │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         │ HTTPS
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    LOAD BALANCER (HAProxy)                       │
└────────────┬────────────────────────────────┬───────────────────┘
             │                                │
             ▼                                ▼
┌────────────────────────┐      ┌────────────────────────────────┐
│   Frontend Servers     │      │    API Gateway (Kong/NGINX)    │
│   - Web Portal         │      │    - Rate Limiting             │
│   - Static Assets      │      │    - SSL Termination           │
│   - CDN Integration    │      │    - Request Routing           │
└────────────────────────┘      └─────────────┬──────────────────┘
                                              │
                    ┌─────────────────────────┼─────────────────────────┐
                    │                         │                         │
                    ▼                         ▼                         ▼
         ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
         │   Core API       │    │  VM Orchestration│    │  Network Service │
         │   Service        │    │     Service      │    │                  │
         │                  │    │                  │    │                  │
         └─────────┬────────┘    └─────────┬────────┘    └─────────┬────────┘
                   │                       │                       │
                   └───────────────┬───────┴───────────────────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
                    ▼              ▼              ▼
         ┌──────────────────┐  ┌─────────────┐  ┌──────────────────┐
         │ Storage Service  │  │  Metering   │  │    Monitoring    │
         │                  │  │   Service   │  │     Service      │
         └─────────┬────────┘  └──────┬──────┘  └─────────┬────────┘
                   │                  │                    │
                   └──────────────────┼────────────────────┘
                                      │
                                      ▼
                    ┌──────────────────────────────────────┐
                    │      Message Queue (RabbitMQ)        │
                    │      - Task Queue                    │
                    │      - Event Bus                     │
                    └──────────────┬───────────────────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
                    ▼              ▼              ▼
         ┌──────────────────┐  ┌─────────────┐  ┌──────────────────┐
         │  Task Workers    │  │   Worker    │  │    Worker        │
         │  (Celery)        │  │   Node 2    │  │    Node 3        │
         │  - VM Creation   │  │             │  │                  │
         │  - Backups       │  │             │  │                  │
         └──────────────────┘  └─────────────┘  └──────────────────┘
                   │                  │                    │
                   └──────────────────┼────────────────────┘
                                      │
                    ┌─────────────────┴─────────────────────────────┐
                    │                                               │
                    ▼                                               ▼
         ┌────────────────────────┐                    ┌──────────────────────┐
         │  PostgreSQL Cluster    │                    │   Redis Cluster      │
         │  - Primary (Write)     │                    │   - Cache            │
         │  - Read Replicas       │                    │   - Sessions         │
         │  - Auto Failover       │                    │   - Pub/Sub          │
         └────────────────────────┘                    └──────────────────────┘
                    │
                    ▼
         ┌────────────────────────┐                    ┌──────────────────────┐
         │ TimescaleDB/InfluxDB   │                    │   Object Storage     │
         │  - Metrics Storage     │                    │   (MinIO/S3)         │
         │  - Time-Series Data    │                    │   - Backups          │
         └────────────────────────┘                    │   - ISO Images       │
                                                        └──────────────────────┘
                    │
                    ▼
         ┌─────────────────────────────────────────────────────────┐
         │              Proxmox VE Layer                           │
         ├─────────────────────────────────────────────────────────┤
         │  Datacenter 1          │  Datacenter 2  │  Datacenter 3│
         │  - Cluster 1           │  - Cluster 3   │  - Cluster 5 │
         │  - Cluster 2           │  - Cluster 4   │  - Cluster 6 │
         └─────────────────────────────────────────────────────────┘
```

## Multi-Datacenter Architecture

### Regional Deployment Model

For large-scale deployments, the platform supports multiple deployment regions:

```
┌────────────────────────────────────────────────────────────────┐
│                      Global Load Balancer                       │
│                    (GeoDNS / CloudFlare)                        │
└─────────┬──────────────────────┬──────────────────┬───────────┘
          │                      │                  │
          ▼                      ▼                  ▼
┌─────────────────┐    ┌─────────────────┐   ┌─────────────────┐
│   Region 1      │    │   Region 2      │   │   Region 3      │
│   (US East)     │    │   (EU West)     │   │   (APAC)        │
├─────────────────┤    ├─────────────────┤   ├─────────────────┤
│ - API Services  │    │ - API Services  │   │ - API Services  │
│ - Workers       │    │ - Workers       │   │ - Workers       │
│ - Local DB      │    │ - Local DB      │   │ - Local DB      │
│ - Proxmox       │    │ - Proxmox       │   │ - Proxmox       │
│   Clusters      │    │   Clusters      │   │   Clusters      │
└─────────────────┘    └─────────────────┘   └─────────────────┘
         │                      │                       │
         └──────────────────────┴───────────────────────┘
                                │
                    ┌───────────▼──────────┐
                    │  Central Services    │
                    │  - Auth Service      │
                    │  - Global Catalog    │
                    │  - Central Billing   │
                    └──────────────────────┘
```

### Data Replication Strategy

- **User/Organization Data**: Replicated globally with eventual consistency
- **VM Metadata**: Region-specific with optional cross-region replication
- **Metrics Data**: Stored locally, aggregated centrally for reporting
- **Audit Logs**: Replicated to central logging service

## Request Flow Examples

### VM Provisioning Flow

1. User submits VM creation request via Web Portal
2. API Gateway authenticates and routes to Core API Service
3. Core API validates quotas and permissions
4. Core API publishes "vm.create" event to message queue
5. VM Orchestration Service picks up event
6. Service selects optimal Proxmox cluster based on resources
7. Service calls Proxmox API to create VM
8. Worker monitors VM creation progress
9. On completion, VM metadata saved to PostgreSQL
10. Notification sent to user
11. Metering service starts tracking resource usage

### Resource Monitoring Flow

1. Monitoring Service polls Proxmox clusters (every 30-60s)
2. Metrics collected: CPU, RAM, disk I/O, network traffic
3. Data stored in TimescaleDB
4. Redis cache updated with latest VM status
5. Web Portal queries cache for real-time dashboard
6. Metering Service aggregates metrics for billing
7. Alerts triggered if thresholds exceeded

## Scalability Considerations

### Horizontal Scaling

- **API Services**: Stateless, scale to N instances behind load balancer
- **Workers**: Scale worker pool based on queue depth
- **Database**: Read replicas for query scaling
- **Cache**: Redis cluster with sharding
- **Proxmox**: Add clusters to distribute load

### Performance Optimizations

- **Caching Strategy**:
  - API responses cached in Redis (short TTL)
  - VM status cached (30s TTL)
  - User sessions in Redis
  - Static assets via CDN

- **Database Optimization**:
  - Connection pooling (PgBouncer)
  - Read/Write splitting
  - Partitioning for audit logs and metrics
  - Materialized views for complex queries

- **Async Processing**:
  - Long-running operations in background workers
  - WebSocket/SSE for real-time updates
  - Batch operations for bulk actions

### High Availability

- **Database**: PostgreSQL with streaming replication, automatic failover (Patroni)
- **Message Queue**: RabbitMQ cluster with mirrored queues
- **Redis**: Redis Sentinel or Redis Cluster for HA
- **API Services**: Multiple instances behind load balancer
- **Load Balancer**: Active-passive HAProxy pair

## Security Architecture

### Network Security

- All services in private network (VPC)
- Only API Gateway and Load Balancer exposed publicly
- TLS 1.3 for all external communication
- mTLS for internal service communication (optional)
- Network segmentation between layers

### Authentication & Authorization

- JWT tokens with short expiry (15 min access, 7 day refresh)
- API keys for service accounts and automation
- Role-Based Access Control (RBAC) with fine-grained permissions
- Multi-factor authentication (TOTP) optional
- Password policies enforced

### Data Security

- Passwords hashed with Argon2
- Sensitive data encrypted at rest (database encryption)
- Audit logging for all sensitive operations
- PII data handling compliance (GDPR considerations)
- Proxmox credentials stored in HashiCorp Vault (or encrypted in DB)

### API Security

- Rate limiting per user/organization
- Request validation and sanitization
- CORS policies
- API versioning
- Input validation on all endpoints

## Monitoring & Observability

### Metrics Collection

- **Application Metrics**: Prometheus + Grafana
- **VM Metrics**: Custom collector → TimescaleDB
- **Log Aggregation**: ELK Stack or Loki
- **Distributed Tracing**: Jaeger or Tempo
- **Uptime Monitoring**: Custom health checks

### Key Metrics to Track

- API request latency (p50, p95, p99)
- VM provisioning time
- Error rates per service
- Queue depth and processing time
- Database query performance
- Cache hit rates
- Resource utilization per tenant

### Alerting

- Service health checks
- API error rate thresholds
- Resource quota warnings
- VM failures
- Database replication lag
- Queue backlog alerts

## Disaster Recovery

### Backup Strategy

- **Database**: Daily full backup + continuous WAL archiving
- **VM Metadata**: Backed up with database
- **Configuration**: Version controlled in Git
- **Proxmox Backups**: Managed by platform backup service
- **Recovery Time Objective (RTO)**: < 4 hours
- **Recovery Point Objective (RPO)**: < 1 hour

### Failure Scenarios

1. **Database Failure**: Auto-failover to replica
2. **Service Crash**: Auto-restart via orchestrator
3. **Datacenter Failure**: Failover to different region
4. **Proxmox Node Failure**: VMs migrated automatically
5. **Message Queue Failure**: Messages persisted, reprocess on recovery

## Development & Deployment

### Development Environment

- Docker Compose for local development
- All services containerized
- Mock Proxmox API for testing
- Seed data for development

### CI/CD Pipeline

- Automated testing (unit, integration, e2e)
- Code quality checks (linting, security scanning)
- Container image building
- Automated deployment to staging
- Blue-green deployment to production

### Infrastructure as Code

- Kubernetes manifests (or Terraform for VMs)
- Helm charts for service deployment
- GitOps approach (ArgoCD/FluxCD)

## Next Steps

Refer to:
- [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) for detailed database design
- [API_SPECIFICATION.md](API_SPECIFICATION.md) for API endpoints
- [TECH_STACK.md](TECH_STACK.md) for technology choices and rationale
- [DEPLOYMENT.md](DEPLOYMENT.md) for deployment guide
