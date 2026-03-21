# Technology Stack

## Overview

This document details the technology choices for the cloud management platform, including rationale for each decision and alternative options considered.

## Technology Selection Criteria

- **Maturity**: Battle-tested in production environments
- **Community**: Active community and good documentation
- **Performance**: Suitable for large-scale deployments
- **Developer Experience**: Good tooling and debugging support
- **Integration**: Works well with other components
- **Cost**: Open-source preferred, minimal licensing costs

## Stack Summary

```
Frontend:      React + TypeScript + Tailwind CSS
Backend:       Python 3.12 + FastAPI + SQLAlchemy
Database:      PostgreSQL 16 + Redis 7
Message Queue: RabbitMQ 3.13
Time-Series:   TimescaleDB (PostgreSQL extension)
Task Queue:    Celery 5.3
API Gateway:   Kong / NGINX
Monitoring:    Prometheus + Grafana
Logging:       Loki / ELK Stack
Container:     Docker + Docker Compose
Orchestration: Kubernetes (production) / Docker Swarm (simple deployments)
```

## Detailed Technology Breakdown

### 1. Backend Services

#### Python 3.12

**Why Python:**
- Excellent Proxmox library (`proxmoxer`)
- Rich ecosystem for APIs, async operations, and data processing
- Fast development cycle
- Strong typing with type hints
- Great for DevOps and automation

**Alternatives Considered:**
- **Go**: Better performance, but less mature Proxmox clients
- **Node.js**: Good for APIs, but Python better for infrastructure automation

#### FastAPI 0.109+

**Why FastAPI:**
- Modern, fast async framework
- Automatic API documentation (OpenAPI/Swagger)
- Type hints for request/response validation
- Built-in dependency injection
- Native async/await support
- Excellent performance (comparable to Node.js)

**Key Features:**
- Pydantic for data validation
- Automatic JSON serialization
- WebSocket support
- Background tasks
- OAuth2 with JWT

**Alternatives Considered:**
- **Django + DRF**: More batteries-included, but heavier and slower
- **Flask**: Simpler but less modern, no native async

**Core Dependencies:**
```python
fastapi==0.109.0
uvicorn[standard]==0.27.0  # ASGI server
pydantic==2.5.0            # Data validation
python-multipart==0.0.6    # Form data parsing
```

#### Proxmox Integration

**proxmoxer 2.0+**

**Why proxmoxer:**
- Official Python library for Proxmox API
- Supports both HTTPS and SSH
- Well-maintained and documented
- Pythonic interface

```python
proxmoxer==2.0.1
requests==2.31.0  # HTTP backend
```

**Integration Pattern:**
```python
from proxmoxer import ProxmoxAPI

proxmox = ProxmoxAPI(
    host='proxmox.example.com',
    user='api@pve',
    token_name='mytoken',
    token_value='secret',
    verify_ssl=True
)

# Create VM
proxmox.nodes('pve-node-01').qemu.create(
    vmid=100,
    name='web-server',
    memory=4096,
    cores=2
)
```

#### SQLAlchemy 2.0+ (ORM)

**Why SQLAlchemy:**
- Most mature Python ORM
- Excellent PostgreSQL support
- Async support (with asyncpg)
- Flexible: can use ORM or Core (SQL builder)
- Migration support via Alembic

```python
sqlalchemy[asyncio]==2.0.25
asyncpg==0.29.0          # Async PostgreSQL driver
alembic==1.13.1          # Database migrations
```

**Example Model:**
```python
from sqlalchemy import Column, String, Integer, DateTime
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime

class Base(DeclarativeBase):
    pass

class VirtualMachine(Base):
    __tablename__ = "virtual_machines"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    cpu_cores = Column(Integer)
    memory_mb = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
```

#### Authentication & Security

**Libraries:**
```python
python-jose[cryptography]==3.3.0  # JWT tokens
passlib[bcrypt]==1.7.4            # Password hashing
python-multipart==0.0.6           # OAuth2 password flow
cryptography==41.0.7              # Encryption
```

**JWT Token Flow:**
- Access tokens: 15 minutes expiry
- Refresh tokens: 7 days expiry
- Argon2 for password hashing
- Token blacklist in Redis

### 2. Database Layer

#### PostgreSQL 16

**Why PostgreSQL:**
- Most advanced open-source RDBMS
- Excellent JSON support (JSONB)
- Robust transaction support (ACID)
- Full-text search
- Table partitioning
- Native UUID support
- TimescaleDB extension for time-series

**Configuration:**
```
max_connections = 200
shared_buffers = 8GB
effective_cache_size = 24GB
work_mem = 64MB
maintenance_work_mem = 2GB
```

**Extensions:**
```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "timescaledb";
```

**Alternatives Considered:**
- **MySQL**: Less advanced features, weaker JSON support
- **MongoDB**: Not suitable for relational data, lacks ACID guarantees

#### TimescaleDB 2.13+

**Why TimescaleDB:**
- PostgreSQL extension (no separate database)
- Optimized for time-series data
- Automatic partitioning
- Continuous aggregates
- Data retention policies
- Compression

**Use Cases:**
- VM performance metrics
- Resource usage tracking
- Audit log storage

```sql
-- Convert table to hypertable
SELECT create_hypertable('usage_records', 'recorded_at');

-- Create continuous aggregate
CREATE MATERIALIZED VIEW daily_usage
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', recorded_at) AS day,
    organization_id,
    SUM(quantity) as total_usage
FROM usage_records
GROUP BY day, organization_id;
```

#### Redis 7

**Why Redis:**
- Blazing fast in-memory cache
- Native data structures (strings, hashes, sets, sorted sets)
- Pub/Sub for real-time events
- Session storage
- Rate limiting
- Distributed locks

```python
redis==5.0.1
hiredis==2.3.2  # C parser for better performance
```

**Use Cases:**
- Session storage
- API response caching
- Rate limiting counters
- Real-time VM status
- Task queue backend (with Celery)
- Pub/Sub for WebSocket updates

**Configuration:**
```
maxmemory 4gb
maxmemory-policy allkeys-lru
appendonly yes
```

#### Database Connection Management

**PgBouncer**

**Why PgBouncer:**
- Connection pooling for PostgreSQL
- Reduces connection overhead
- Supports transaction and session pooling
- Essential for high-concurrency applications

**Configuration:**
```
max_client_conn = 1000
default_pool_size = 25
reserve_pool_size = 5
pool_mode = transaction
```

### 3. Message Queue & Task Processing

#### RabbitMQ 3.13

**Why RabbitMQ:**
- Industry standard message broker
- Reliable message delivery
- Multiple exchange types
- Dead letter queues
- Priority queues
- Management UI

**Use Cases:**
- Async task queue (VM provisioning, backups)
- Event distribution between services
- Inter-service communication

**Alternatives Considered:**
- **Redis**: Simpler but less reliable for critical tasks
- **Kafka**: Overkill for this use case, harder to operate

#### Celery 5.3

**Why Celery:**
- Mature distributed task queue
- Native Python support
- Multiple broker support (RabbitMQ, Redis)
- Scheduled tasks (via Celery Beat)
- Task retries and error handling
- Monitoring (Flower)

```python
celery==5.3.4
flower==2.0.1  # Monitoring UI
```

**Task Examples:**
```python
from celery import Celery

celery_app = Celery('tasks', broker='amqp://rabbitmq')

@celery_app.task(bind=True, max_retries=3)
def provision_vm(self, vm_config):
    try:
        # Call Proxmox API to create VM
        proxmox.create_vm(**vm_config)
    except Exception as exc:
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60)
```

**Celery Beat** for scheduled tasks:
- Usage metrics aggregation (hourly)
- Cleanup of expired sessions (daily)
- Backup jobs (daily)
- Quota enforcement checks (every 5 minutes)

### 4. Frontend

#### React 18 + TypeScript

**Why React:**
- Most popular frontend framework
- Large ecosystem and component libraries
- Excellent performance with Virtual DOM
- Strong community support
- Great tooling (React DevTools)

**Why TypeScript:**
- Type safety for large applications
- Better IDE support and autocomplete
- Catch errors at compile time
- Self-documenting code

```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "typescript": "^5.3.3"
  }
}
```

**Alternatives Considered:**
- **Vue.js**: Simpler learning curve, but smaller ecosystem
- **Angular**: Too heavy, steeper learning curve
- **Svelte**: Modern but less mature ecosystem

#### State Management

**TanStack Query (React Query) 5.x**

**Why TanStack Query:**
- Handles server state elegantly
- Automatic caching and invalidation
- Optimistic updates
- Background refetching
- No need for Redux for server data

```typescript
import { useQuery } from '@tanstack/react-query'

function VMList() {
  const { data, isLoading } = useQuery({
    queryKey: ['vms'],
    queryFn: fetchVMs,
    refetchInterval: 30000 // Refetch every 30s
  })
}
```

**Zustand** for client-side state:
```typescript
import create from 'zustand'

const useStore = create((set) => ({
  currentOrg: null,
  setCurrentOrg: (org) => set({ currentOrg: org })
}))
```

#### UI Components

**Tailwind CSS 3.x**

**Why Tailwind:**
- Utility-first CSS framework
- Rapid UI development
- Consistent design system
- Tree-shaking for small bundle sizes
- Great documentation

**Component Library Options:**
- **shadcn/ui**: Beautifully designed components built with Radix UI + Tailwind
- **Headless UI**: Unstyled, accessible components
- **Radix UI**: Primitive components for building design systems

```json
{
  "devDependencies": {
    "tailwindcss": "^3.4.1",
    "autoprefixer": "^10.4.17",
    "postcss": "^8.4.33"
  }
}
```

#### Routing

**React Router 6**

```typescript
import { BrowserRouter, Routes, Route } from 'react-router-dom'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/vms" element={<VMList />} />
        <Route path="/vms/:id" element={<VMDetail />} />
      </Routes>
    </BrowserRouter>
  )
}
```

#### Build Tool

**Vite 5.x**

**Why Vite:**
- Lightning-fast dev server
- Instant HMR (Hot Module Replacement)
- Optimized production builds
- Native ESM support
- Better than Create React App

```json
{
  "devDependencies": {
    "vite": "^5.0.11",
    "@vitejs/plugin-react": "^4.2.1"
  }
}
```

### 5. API Gateway

#### Kong or NGINX

**Kong:**
- Open-source API gateway
- Plugin system (rate limiting, auth, logging)
- Load balancing
- Service discovery
- Management UI (Kong Manager)

**NGINX:**
- Lighter weight alternative
- More control and configuration flexibility
- Can use OpenResty (NGINX + Lua)

**Recommendation:** Kong for production, NGINX for simpler deployments

**Kong Plugins:**
- Rate limiting
- JWT authentication
- CORS
- Request/response transformation
- Prometheus metrics

### 6. Monitoring & Observability

#### Prometheus + Grafana

**Prometheus:**
- Time-series metrics database
- Pull-based metric collection
- PromQL query language
- Alertmanager for notifications

**Grafana:**
- Beautiful dashboards
- Multiple data sources
- Alerting
- User management

**Metrics to Track:**
- API request latency (p50, p95, p99)
- API error rates
- VM provisioning time
- Database query performance
- Queue depth
- Cache hit rates
- Resource utilization per tenant

**Python client:**
```python
prometheus-client==0.19.0
```

**Instrumentation:**
```python
from prometheus_client import Counter, Histogram

request_count = Counter('api_requests_total', 'Total API requests', ['method', 'endpoint'])
request_duration = Histogram('api_request_duration_seconds', 'API request duration')

@request_duration.time()
async def api_endpoint():
    request_count.labels(method='GET', endpoint='/vms').inc()
    # ... endpoint logic
```

#### Logging

**Option 1: Loki + Promtail + Grafana**
- Lightweight alternative to ELK
- Integrates with Grafana
- Label-based log aggregation
- Cost-effective

**Option 2: ELK Stack (Elasticsearch + Logstash + Kibana)**
- More powerful full-text search
- Complex log analysis
- Higher resource requirements

**Recommendation:** Loki for most use cases, ELK if advanced log search is critical

**Python Logging:**
```python
import logging
import structlog

structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ]
)

logger = structlog.get_logger()
logger.info("vm_created", vm_id="uuid", org_id="uuid")
```

#### Distributed Tracing

**Jaeger or Tempo**

**Why Distributed Tracing:**
- Track requests across microservices
- Identify performance bottlenecks
- Visualize service dependencies

**OpenTelemetry** for instrumentation:
```python
opentelemetry-api==1.22.0
opentelemetry-sdk==1.22.0
opentelemetry-instrumentation-fastapi==0.43b0
```

### 7. Containerization & Orchestration

#### Docker

**Why Docker:**
- Standard for containerization
- Consistent environments (dev, staging, prod)
- Easy dependency management
- Portable deployments

**Dockerfile example:**
```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### Docker Compose (Development)

**Why Docker Compose:**
- Multi-container orchestration
- Perfect for local development
- Easy service configuration

```yaml
version: '3.8'

services:
  api:
    build: ./backend
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - redis
    environment:
      DATABASE_URL: postgresql://postgres:password@postgres/cloudplatform

  postgres:
    image: timescale/timescaledb:2.13-pg16
    environment:
      POSTGRES_DB: cloudplatform
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
```

#### Kubernetes (Production)

**Why Kubernetes:**
- Industry standard for container orchestration
- Auto-scaling (HPA, VPA)
- Self-healing
- Rolling updates
- Service discovery
- Load balancing

**Key Components:**
- Deployments for stateless services (API, workers)
- StatefulSets for databases (if not using managed services)
- Services for internal communication
- Ingress for external access
- ConfigMaps and Secrets for configuration
- PersistentVolumes for data storage

**Helm Charts** for deployment:
```yaml
# values.yaml
api:
  replicas: 3
  image:
    repository: cloudplatform/api
    tag: v1.0.0
  resources:
    limits:
      cpu: 1000m
      memory: 2Gi
    requests:
      cpu: 500m
      memory: 1Gi
```

**Alternative for Simpler Deployments:** Docker Swarm

### 8. CI/CD

#### GitHub Actions

**Why GitHub Actions:**
- Integrated with GitHub
- Free for public repos
- Good marketplace of actions
- Matrix builds for testing

**Pipeline Stages:**
1. **Lint & Format**: Black, isort, flake8, mypy
2. **Test**: pytest with coverage
3. **Build**: Docker image
4. **Security Scan**: Trivy, Bandit
5. **Deploy**: Push to registry, update K8s

```yaml
name: CI/CD

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -r requirements-dev.txt
      - run: pytest --cov=app tests/

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: docker/build-push-action@v5
        with:
          push: true
          tags: cloudplatform/api:${{ github.sha }}
```

**Alternatives:**
- **GitLab CI**: More features, self-hosted option
- **Jenkins**: Highly customizable, but more complex
- **CircleCI**: Good performance, paid

### 9. Development Tools

#### Code Quality

```python
# requirements-dev.txt
pytest==7.4.4              # Testing framework
pytest-asyncio==0.23.3     # Async test support
pytest-cov==4.1.0          # Coverage reporting
black==24.1.1              # Code formatting
isort==5.13.2              # Import sorting
flake8==7.0.0              # Linting
mypy==1.8.0                # Type checking
bandit==1.7.6              # Security linting
pre-commit==3.6.0          # Git hooks
```

#### Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    rev: 24.1.1
    hooks:
      - id: black
  - repo: https://github.com/pycqa/isort
    rev: 5.13.2
    hooks:
      - id: isort
  - repo: https://github.com/pycqa/flake8
    rev: 7.0.0
    hooks:
      - id: flake8
```

#### API Documentation

**Swagger UI** (included with FastAPI):
- Automatic API docs at `/docs`
- Interactive API testing
- OpenAPI schema at `/openapi.json`

**ReDoc** (alternative docs):
- Different style, same OpenAPI schema
- Available at `/redoc`

### 10. Infrastructure as Code

#### Terraform (Optional)

**Why Terraform:**
- Declarative infrastructure definition
- Multi-cloud support
- State management
- Plan before apply

**Use Cases:**
- Provision cloud VMs for Kubernetes nodes
- Set up networking (VPCs, subnets)
- Configure load balancers
- Manage DNS records

```hcl
resource "proxmox_vm_qemu" "k8s_node" {
  count       = 3
  name        = "k8s-node-${count.index + 1}"
  target_node = "pve-node-01"

  cores   = 4
  memory  = 8192
  sockets = 1

  disk {
    storage = "local-lvm"
    size    = "40G"
  }
}
```

## Development Environment Setup

### Prerequisites

```bash
# Python 3.12+
python --version

# Node.js 20+
node --version

# Docker & Docker Compose
docker --version
docker-compose --version

# Git
git --version
```

### Backend Setup

```bash
# Clone repo
git clone https://github.com/yourorg/cloud-platform.git
cd cloud-platform/backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Set up pre-commit hooks
pre-commit install

# Copy environment file
cp .env.example .env

# Run database migrations
alembic upgrade head

# Start development server
uvicorn app.main:app --reload
```

### Frontend Setup

```bash
cd ../frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

### Docker Development

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f api

# Run tests
docker-compose exec api pytest

# Stop all services
docker-compose down
```

## Production Deployment Considerations

### Scalability

- **Horizontal scaling**: Deploy multiple API instances behind load balancer
- **Database**: Use read replicas for scaling reads
- **Caching**: Redis cluster for distributed caching
- **CDN**: CloudFlare or Fastly for static assets

### Security

- **HTTPS**: TLS 1.3 everywhere
- **Secrets**: HashiCorp Vault or Kubernetes Secrets
- **Network**: Private networks, bastion hosts
- **Updates**: Automated security patching
- **Backups**: Automated, encrypted, tested regularly

### Monitoring

- **Uptime**: UptimeRobot or StatusCake
- **APM**: Sentry for error tracking
- **Alerts**: PagerDuty for on-call
- **SLA**: 99.9% uptime target

## Cost Optimization

- **Right-sizing**: Monitor and adjust resource allocations
- **Caching**: Reduce database queries
- **Compression**: Gzip responses
- **Database**: Connection pooling, query optimization
- **CDN**: Cache static assets
- **Auto-scaling**: Scale down during low traffic

## Next Steps

Refer to:
- [DEPLOYMENT.md](DEPLOYMENT.md) for deployment procedures
- [ARCHITECTURE.md](ARCHITECTURE.md) for system design
