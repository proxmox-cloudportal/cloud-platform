# Getting Started Guide

This guide will help you get the Cloud Platform up and running on your local machine.

## Prerequisites

- **Docker & Docker Compose** (recommended) - [Install Docker](https://docs.docker.com/get-docker/)
- OR for manual setup:
  - Python 3.12+
  - Node.js 20+
  - PostgreSQL 16+
  - Redis 7+
  - RabbitMQ 3.13+

## Quick Start with Docker (Recommended)

The fastest way to get started is using Docker Compose, which will set up all services automatically.

### 1. Clone the Repository

```bash
git clone https://github.com/yourorg/cloud-platform.git
cd cloud-platform
```

### 2. Start All Services

```bash
docker-compose up -d
```

This will start:
- PostgreSQL with TimescaleDB (port 5432)
- Redis (port 6379)
- RabbitMQ (port 5672, management UI on port 15672)
- Backend API (port 8000)
- Celery Worker
- Flower (Celery monitoring on port 5555)
- Frontend (port 3000)

### 3. Create Your First User

Open your browser to http://localhost:3000 and you'll be redirected to the login page.

Since this is a fresh install, you need to create your first user via API:

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "username": "admin",
    "password": "ChangeMe123!",
    "first_name": "Admin",
    "last_name": "User"
  }'
```

### 4. Grant Superadmin Privileges

New accounts have no admin privileges by default. Grant superadmin access so you can manage clusters:

```bash
docker exec cloudplatform-api python make_superadmin.py admin@example.com
```

### 5. Login

Now you can login at http://localhost:3000 with:
- **Email**: admin@example.com
- **Password**: ChangeMe123!

### 6. Explore the Platform

- **Frontend Dashboard**: http://localhost:3000
- **API Documentation**: http://localhost:8000/docs
- **RabbitMQ Management**: http://localhost:15672 (guest/guest)
- **Flower (Celery)**: http://localhost:5555

## Manual Setup (Without Docker)

If you prefer to run services manually:

### 1. Setup PostgreSQL

```bash
# Create database
createdb cloudplatform

# Or using psql
psql -U postgres -c "CREATE DATABASE cloudplatform;"
```

### 2. Setup Redis

```bash
# Start Redis with password
redis-server --requirepass cloudplatform_redis_password
```

### 3. Setup RabbitMQ

```bash
# Start RabbitMQ
rabbitmq-server

# Create user (optional)
rabbitmqctl add_user cloudplatform cloudplatform_rabbit_password
rabbitmqctl set_permissions -p / cloudplatform ".*" ".*" ".*"
```

### 4. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your database credentials

# Run migrations
alembic upgrade head

# Start API server
uvicorn app.main:app --reload
```

### 5. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

### 6. Start Celery Worker (optional)

```bash
cd backend
source venv/bin/activate
celery -A app.celery_app worker --loglevel=info
```

## Development Workflow

### Viewing Logs

```bash
# View all logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f api
docker-compose logs -f frontend
docker-compose logs -f postgres
```

### Stopping Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (WARNING: deletes data)
docker-compose down -v
```

### Restarting Services

```bash
# Restart all services
docker-compose restart

# Restart specific service
docker-compose restart api
```

### Running Database Migrations

```bash
# Create a new migration
docker-compose exec api alembic revision --autogenerate -m "Description"

# Apply migrations
docker-compose exec api alembic upgrade head

# Rollback one migration
docker-compose exec api alembic downgrade -1
```

### Accessing Database

```bash
# Using psql
docker-compose exec postgres psql -U cloudplatform -d cloudplatform

# Or use any PostgreSQL client
# Host: localhost
# Port: 5432
# Database: cloudplatform
# Username: cloudplatform
# Password: cloudplatform_dev_password
```

### Accessing Redis CLI

```bash
docker-compose exec redis redis-cli -a cloudplatform_redis_password
```

## API Testing

### Using curl

```bash
# Health check
curl http://localhost:8000/health

# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"ChangeMe123!"}'

# Get current user (use token from login)
curl http://localhost:8000/api/v1/users/me \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Using the Interactive API Docs

Open http://localhost:8000/docs in your browser for an interactive Swagger UI where you can test all API endpoints.

## Frontend Development

The frontend uses Vite with Hot Module Replacement (HMR), so changes are reflected immediately.

### Directory Structure

```
frontend/src/
├── components/     # Reusable UI components
├── pages/          # Page components (LoginPage, DashboardPage, etc.)
├── services/       # API client and service functions
├── stores/         # Zustand state management stores
├── hooks/          # Custom React hooks
├── types/          # TypeScript type definitions
└── utils/          # Utility functions
```

### Adding a New Page

1. Create page component in `src/pages/`
2. Add route in `src/App.tsx`
3. Add navigation links in your layout/header component

### Making API Calls

Use the pre-configured API client:

```typescript
import { api } from '@/services/api'

// Example: Fetch data
const response = await api.get('/vms')
const vms = response.data.data

// Example: Create resource
const response = await api.post('/vms', {
  name: 'web-server',
  cpu_cores: 2,
  memory_mb: 4096
})
```

## Backend Development

### Project Structure

```
backend/app/
├── api/
│   └── v1/
│       ├── endpoints/  # API route handlers
│       └── router.py   # API router
├── core/              # Core functionality
│   ├── config.py      # Settings
│   ├── security.py    # Auth utilities
│   └── deps.py        # FastAPI dependencies
├── db/                # Database
│   └── session.py     # DB connection
├── models/            # SQLAlchemy models
├── schemas/           # Pydantic schemas
├── services/          # Business logic
└── main.py           # FastAPI app
```

### Adding a New API Endpoint

1. Create endpoint file in `app/api/v1/endpoints/`
2. Define routes using FastAPI router
3. Add router to `app/api/v1/router.py`

Example:

```python
# app/api/v1/endpoints/vms.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.core.deps import get_current_user

router = APIRouter(prefix="/vms", tags=["Virtual Machines"])

@router.get("")
async def list_vms(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    # Your logic here
    return {"data": []}
```

Then add to router:

```python
# app/api/v1/router.py
from app.api.v1.endpoints import vms

api_router.include_router(vms.router)
```

### Adding a Database Model

1. Create model in `app/models/`
2. Import in `app/models/__init__.py`
3. Create Pydantic schemas in `app/schemas/`
4. Generate migration: `alembic revision --autogenerate -m "Add VM model"`
5. Apply migration: `alembic upgrade head`

## Testing

### Backend Tests

```bash
cd backend

# Run all tests
pytest

# Run with coverage
pytest --cov=app tests/

# Run specific test file
pytest tests/test_auth.py
```

### Frontend Tests

```bash
cd frontend

# Run tests (when configured)
npm test
```

## Troubleshooting

### Port Already in Use

If you get "port already in use" errors:

```bash
# Find and kill process using port 8000
lsof -ti:8000 | xargs kill -9

# Or change ports in docker-compose.yml
```

### Database Connection Errors

1. Ensure PostgreSQL is running
2. Check credentials in `.env`
3. Verify DATABASE_URL format: `postgresql+asyncpg://user:pass@host:port/db`

### Frontend Can't Reach API

1. Check VITE_API_URL in frontend environment
2. Ensure CORS is configured correctly in backend
3. Check that API is running on the expected port

### Docker Issues

```bash
# Clean up Docker resources
docker-compose down -v
docker system prune -a

# Rebuild containers
docker-compose up --build
```

## Next Steps

Now that you have the platform running:

1. **Explore the API**: http://localhost:8000/docs
2. **Read the Documentation**:
   - [Architecture](ARCHITECTURE.md)
   - [API Specification](API_SPECIFICATION.md)
   - [Database Schema](DATABASE_SCHEMA.md)
3. **Start Building Features**:
   - Add VM management endpoints
   - Implement network configuration
   - Add monitoring and metrics

## Getting Help

- **Documentation**: Check the `/docs` directory
- **Issues**: Report bugs on GitHub
- **Discussions**: Join GitHub Discussions for questions

Happy coding! 🚀
