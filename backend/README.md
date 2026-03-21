# Cloud Platform - Backend API

FastAPI-based backend for the Cloud Management Platform.

## Features

- **FastAPI**: Modern, fast web framework for building APIs
- **SQLAlchemy 2.0**: Async ORM for database operations
- **PostgreSQL**: Primary database with TimescaleDB extension
- **Redis**: Caching and session storage
- **JWT Authentication**: Secure token-based authentication
- **Celery**: Distributed task queue for async operations
- **Alembic**: Database migrations
- **Pydantic**: Data validation and settings management

## Prerequisites

- Python 3.12+
- PostgreSQL 16+ (or use Docker Compose)
- Redis 7+ (or use Docker Compose)
- RabbitMQ 3.13+ (or use Docker Compose)

## Quick Start with Docker

The easiest way to get started is using Docker Compose:

```bash
# From the project root
docker-compose up -d

# API will be available at http://localhost:8000
# API docs at http://localhost:8000/docs
```

## Local Development Setup

### 1. Create Virtual Environment

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your configuration
```

### 4. Start Database Services

```bash
# Using Docker for just the databases
docker-compose up -d postgres redis rabbitmq
```

### 5. Run Database Migrations

```bash
# Create initial migration
alembic revision --autogenerate -m "Initial migration"

# Apply migrations
alembic upgrade head
```

### 6. Start Development Server

```bash
# With auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Or using Python directly
python -m app.main
```

The API will be available at:
- API: http://localhost:8000
- Interactive docs (Swagger UI): http://localhost:8000/docs
- Alternative docs (ReDoc): http://localhost:8000/redoc
- OpenAPI schema: http://localhost:8000/openapi.json

## Project Structure

```
backend/
├── alembic/              # Database migrations
│   ├── versions/         # Migration files
│   └── env.py           # Alembic environment
├── app/
│   ├── api/             # API endpoints
│   │   └── v1/
│   │       ├── endpoints/  # Route handlers
│   │       └── router.py   # API router
│   ├── core/            # Core functionality
│   │   ├── config.py    # Settings
│   │   ├── security.py  # Auth utilities
│   │   └── deps.py      # Dependencies
│   ├── db/              # Database
│   │   └── session.py   # DB connection
│   ├── models/          # SQLAlchemy models
│   │   ├── base.py
│   │   ├── user.py
│   │   └── organization.py
│   ├── schemas/         # Pydantic schemas
│   │   ├── user.py
│   │   └── organization.py
│   ├── services/        # Business logic
│   └── main.py          # FastAPI app
├── tests/               # Test suite
├── requirements.txt     # Python dependencies
└── Dockerfile          # Docker image
```

## API Endpoints

### Authentication
- `POST /api/v1/auth/register` - Register new user
- `POST /api/v1/auth/login` - Login and get tokens
- `POST /api/v1/auth/refresh` - Refresh access token
- `POST /api/v1/auth/logout` - Logout
- `GET /api/v1/auth/me` - Get current user

### Users
- `GET /api/v1/users/me` - Get my profile
- `PATCH /api/v1/users/me` - Update my profile
- `GET /api/v1/users` - List all users (admin)
- `GET /api/v1/users/{id}` - Get user by ID (admin)
- `DELETE /api/v1/users/{id}` - Delete user (admin)

### Virtual Machines
- `GET /api/v1/vms` - List VMs in organization
- `POST /api/v1/vms` - Create new VM (with multi-disk support)
- `GET /api/v1/vms/{id}` - Get VM details
- `PATCH /api/v1/vms/{id}` - Update VM configuration
- `DELETE /api/v1/vms/{id}` - Delete VM
- `POST /api/v1/vms/{id}/start` - Start VM
- `POST /api/v1/vms/{id}/stop` - Stop VM
- `POST /api/v1/vms/{id}/restart` - Restart VM
- `POST /api/v1/vms/{id}/sync` - Sync VM status from Proxmox

### ISO Images (Phase 2)
- `POST /api/v1/isos/upload` - Upload ISO file
- `GET /api/v1/isos` - List available ISOs
- `GET /api/v1/isos/{id}` - Get ISO details
- `PATCH /api/v1/isos/{id}` - Update ISO metadata
- `DELETE /api/v1/isos/{id}` - Delete ISO

### Storage Pools (Phase 2)
- `GET /api/v1/storage/pools` - List all accessible storage pools
- `GET /api/v1/storage/clusters/{id}/pools` - List pools for specific cluster
- `GET /api/v1/storage/clusters/{id}/pools/{pool_id}` - Get pool details
- `POST /api/v1/storage/clusters/{id}/pools/sync` - Sync storage pools from Proxmox

### VM Disks (Phase 2)
- `GET /api/v1/vms/{id}/disks` - List VM disks
- `POST /api/v1/vms/{id}/disks` - Attach new disk to VM
- `DELETE /api/v1/vms/{id}/disks/{disk_id}` - Detach disk from VM
- `POST /api/v1/vms/{id}/disks/attach-iso` - Attach ISO to VM as CD-ROM

### Organizations
- `GET /api/v1/organizations/me` - List my organizations
- `GET /api/v1/organizations/members` - List organization members
- `POST /api/v1/organizations/members` - Invite member
- `PATCH /api/v1/organizations/members/{id}` - Update member role
- `DELETE /api/v1/organizations/members/{id}` - Remove member

### Proxmox Clusters
- `GET /api/v1/clusters` - List clusters
- `POST /api/v1/clusters` - Add new cluster
- `GET /api/v1/clusters/{id}` - Get cluster details
- `PATCH /api/v1/clusters/{id}` - Update cluster
- `DELETE /api/v1/clusters/{id}` - Delete cluster
- `POST /api/v1/clusters/test` - Test cluster connection
- `POST /api/v1/clusters/{id}/sync` - Sync cluster status

### Quotas
- `GET /api/v1/quotas` - Get organization quotas
- `GET /api/v1/quotas/usage` - Get current usage
- `PUT /api/v1/quotas/{resource_type}` - Update quota limit (admin)
- `POST /api/v1/quotas/recalculate` - Recalculate usage from VMs

### Health
- `GET /health` - Basic health check
- `GET /health/detailed` - Detailed health with database status

## Database Migrations

```bash
# Create a new migration
alembic revision --autogenerate -m "Description of changes"

# Apply migrations
alembic upgrade head

# Rollback last migration
alembic downgrade -1

# Show current revision
alembic current

# Show migration history
alembic history
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app tests/

# Run specific test file
pytest tests/test_auth.py

# Run with verbose output
pytest -v
```

## Code Quality

```bash
# Format code with Black
black app/

# Sort imports
isort app/

# Lint with flake8
flake8 app/

# Type checking with mypy
mypy app/

# Run all checks
black app/ && isort app/ && flake8 app/ && mypy app/
```

## Celery Tasks

Start Celery worker and beat scheduler:

```bash
# Worker (for processing background tasks)
celery -A app.tasks.celery_app worker --loglevel=info

# Beat (for periodic tasks like storage sync)
celery -A app.tasks.celery_app beat --loglevel=info

# Flower (monitoring UI at http://localhost:5555)
celery -A app.tasks.celery_app flower
```

### Background Tasks (Phase 2)

**ISO Tasks:**
- `transfer_iso_to_proxmox` - Upload ISO to Proxmox storage
- `cleanup_iso_storage` - Clean up ISO from Proxmox and local storage

**VM Tasks:**
- `provision_vm_with_disks` - Create VM with multiple disks and ISO boot

**Sync Tasks (Periodic):**
- `sync_all_storage_pools` - Sync storage pools from all clusters (every 5 minutes)

## Environment Variables

See [.env.example](.env.example) for all available configuration options.

Key variables:
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `JWT_SECRET_KEY`: Secret key for JWT tokens (change in production!)
- `CORS_ORIGINS`: Allowed CORS origins
- `ENVIRONMENT`: development, staging, or production

## Production Deployment

See [../DEPLOYMENT.md](../DEPLOYMENT.md) for production deployment instructions.

## Contributing

1. Create a feature branch
2. Make changes
3. Run tests and linting
4. Submit pull request

## License

TBD
