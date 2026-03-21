# API Specification

## Overview

This document defines the RESTful API for the cloud management platform. All APIs follow REST principles, use JSON for data exchange, and are versioned.

## API Design Principles

- **RESTful**: Resources identified by URIs, standard HTTP methods
- **Stateless**: Each request contains all necessary information
- **Versioned**: API version in URL path (`/api/v1/`)
- **Consistent**: Uniform response format across endpoints
- **Paginated**: List endpoints support pagination
- **Filtered**: Support query parameters for filtering
- **Documented**: OpenAPI/Swagger specification

## Base URL

```
https://api.cloudplatform.example.com/api/v1
```

## Authentication

### Methods

1. **JWT Bearer Token** (Primary)
   ```
   Authorization: Bearer <access_token>
   ```

2. **API Key** (For automation)
   ```
   X-API-Key: <api_key>
   ```

### Token Flow

```
POST /auth/login
→ Returns access_token (15 min) + refresh_token (7 days)

POST /auth/refresh
→ Returns new access_token using refresh_token

POST /auth/logout
→ Invalidates tokens
```

### Token Payload

```json
{
  "user_id": "uuid",
  "email": "user@example.com",
  "org_id": "uuid",
  "roles": ["org_admin"],
  "exp": 1234567890
}
```

## Authorization

### Multi-tenancy

- All requests scoped to organization via `X-Organization-ID` header or token
- Users can be members of multiple organizations
- Switch organization context by providing different org ID

### Permission Model

- RBAC with fine-grained permissions
- Format: `{resource}:{action}` (e.g., `vm:create`, `vm:start`)
- Permissions checked on every request
- 403 Forbidden if insufficient permissions

## Standard Response Format

### Success Response

```json
{
  "data": {
    // Response data
  },
  "meta": {
    "timestamp": "2026-01-31T12:00:00Z",
    "request_id": "req_123456"
  }
}
```

### List Response (with pagination)

```json
{
  "data": [
    // Array of resources
  ],
  "meta": {
    "total": 150,
    "page": 1,
    "per_page": 20,
    "total_pages": 8,
    "timestamp": "2026-01-31T12:00:00Z",
    "request_id": "req_123456"
  },
  "links": {
    "first": "/api/v1/vms?page=1",
    "prev": null,
    "next": "/api/v1/vms?page=2",
    "last": "/api/v1/vms?page=8"
  }
}
```

### Error Response

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request parameters",
    "details": [
      {
        "field": "cpu_cores",
        "message": "Must be between 1 and 32"
      }
    ]
  },
  "meta": {
    "timestamp": "2026-01-31T12:00:00Z",
    "request_id": "req_123456"
  }
}
```

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| AUTHENTICATION_REQUIRED | 401 | No valid authentication provided |
| AUTHENTICATION_FAILED | 401 | Invalid credentials |
| TOKEN_EXPIRED | 401 | Access token has expired |
| PERMISSION_DENIED | 403 | Insufficient permissions |
| RESOURCE_NOT_FOUND | 404 | Resource does not exist |
| VALIDATION_ERROR | 400 | Request validation failed |
| QUOTA_EXCEEDED | 429 | Resource quota exceeded |
| RATE_LIMIT_EXCEEDED | 429 | Too many requests |
| CONFLICT | 409 | Resource conflict (e.g., duplicate) |
| INTERNAL_ERROR | 500 | Internal server error |
| SERVICE_UNAVAILABLE | 503 | Service temporarily unavailable |

## Rate Limiting

- **Authenticated Users**: 1000 requests / hour
- **API Keys**: 5000 requests / hour
- **Unauthenticated**: 100 requests / hour

Headers returned:
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 842
X-RateLimit-Reset: 1640995200
```

## API Endpoints

### 1. Authentication & Users

#### POST /auth/register
Register a new user account.

**Request:**
```json
{
  "email": "user@example.com",
  "username": "johndoe",
  "password": "SecurePass123!",
  "first_name": "John",
  "last_name": "Doe"
}
```

**Response:** `201 Created`
```json
{
  "data": {
    "user": {
      "id": "uuid",
      "email": "user@example.com",
      "username": "johndoe",
      "first_name": "John",
      "last_name": "Doe",
      "created_at": "2026-01-31T12:00:00Z"
    }
  }
}
```

#### POST /auth/login
Authenticate user and receive tokens.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!"
}
```

**Response:** `200 OK`
```json
{
  "data": {
    "access_token": "eyJ0eXAiOiJKV1...",
    "refresh_token": "eyJ0eXAiOiJKV1...",
    "token_type": "Bearer",
    "expires_in": 900
  }
}
```

#### POST /auth/refresh
Refresh access token using refresh token.

**Request:**
```json
{
  "refresh_token": "eyJ0eXAiOiJKV1..."
}
```

**Response:** `200 OK`
```json
{
  "data": {
    "access_token": "eyJ0eXAiOiJKV1...",
    "token_type": "Bearer",
    "expires_in": 900
  }
}
```

#### POST /auth/logout
Invalidate current session.

**Response:** `204 No Content`

#### GET /users/me
Get current user profile.

**Response:** `200 OK`
```json
{
  "data": {
    "id": "uuid",
    "email": "user@example.com",
    "username": "johndoe",
    "first_name": "John",
    "last_name": "Doe",
    "is_active": true,
    "organizations": [
      {
        "id": "uuid",
        "name": "Acme Corp",
        "role": "org_admin"
      }
    ],
    "created_at": "2026-01-01T00:00:00Z"
  }
}
```

#### PATCH /users/me
Update current user profile.

**Request:**
```json
{
  "first_name": "Jane",
  "last_name": "Smith"
}
```

**Response:** `200 OK`

#### POST /users/me/api-keys
Create new API key.

**Request:**
```json
{
  "name": "CI/CD Pipeline",
  "scopes": ["vm:create", "vm:read"],
  "expires_at": "2027-01-31T00:00:00Z"
}
```

**Response:** `201 Created`
```json
{
  "data": {
    "id": "uuid",
    "name": "CI/CD Pipeline",
    "key": "cpk_live_1234567890abcdef...",
    "key_prefix": "cpk_...cdef",
    "scopes": ["vm:create", "vm:read"],
    "expires_at": "2027-01-31T00:00:00Z",
    "created_at": "2026-01-31T12:00:00Z"
  },
  "warning": "This key will only be displayed once. Store it securely."
}
```

### 2. Organizations

#### GET /organizations
List organizations current user belongs to.

**Query Parameters:**
- `page` (default: 1)
- `per_page` (default: 20, max: 100)

**Response:** `200 OK`
```json
{
  "data": [
    {
      "id": "uuid",
      "name": "Acme Corp",
      "slug": "acme-corp",
      "description": "Main organization",
      "role": "org_admin",
      "is_active": true,
      "created_at": "2026-01-01T00:00:00Z"
    }
  ],
  "meta": {
    "total": 1,
    "page": 1,
    "per_page": 20
  }
}
```

#### POST /organizations
Create new organization.

**Request:**
```json
{
  "name": "New Startup Inc",
  "slug": "new-startup",
  "description": "Our new organization"
}
```

**Response:** `201 Created`

#### GET /organizations/:org_id
Get organization details.

**Response:** `200 OK`
```json
{
  "data": {
    "id": "uuid",
    "name": "Acme Corp",
    "slug": "acme-corp",
    "description": "Main organization",
    "is_active": true,
    "quotas": {
      "max_vcpu": 100,
      "max_memory_mb": 204800,
      "max_vms": 50,
      "max_storage_gb": 1000
    },
    "current_usage": {
      "vcpu": 24,
      "memory_mb": 49152,
      "vms": 12,
      "storage_gb": 240
    },
    "created_at": "2026-01-01T00:00:00Z"
  }
}
```

#### PATCH /organizations/:org_id
Update organization.

**Permission:** `org:update`

**Request:**
```json
{
  "name": "Acme Corporation",
  "description": "Updated description"
}
```

**Response:** `200 OK`

#### GET /organizations/:org_id/members
List organization members.

**Response:** `200 OK`
```json
{
  "data": [
    {
      "user_id": "uuid",
      "email": "user@example.com",
      "username": "johndoe",
      "first_name": "John",
      "last_name": "Doe",
      "role": "org_admin",
      "joined_at": "2026-01-01T00:00:00Z"
    }
  ]
}
```

#### POST /organizations/:org_id/members
Invite user to organization.

**Permission:** `org:members`

**Request:**
```json
{
  "email": "newuser@example.com",
  "role": "org_member"
}
```

**Response:** `201 Created`

#### DELETE /organizations/:org_id/members/:user_id
Remove member from organization.

**Permission:** `org:members`

**Response:** `204 No Content`

### 3. Virtual Machines

#### GET /vms
List virtual machines.

**Query Parameters:**
- `page`, `per_page`: Pagination
- `status`: Filter by status (running, stopped, etc.)
- `search`: Search by name
- `sort`: Sort field (created_at, name, status)
- `order`: asc or desc

**Response:** `200 OK`
```json
{
  "data": [
    {
      "id": "uuid",
      "name": "web-server-01",
      "hostname": "web01.acme.com",
      "description": "Production web server",
      "status": "running",
      "power_state": "on",
      "cpu_cores": 4,
      "memory_mb": 8192,
      "primary_ip_address": "10.0.1.10",
      "os_type": "linux",
      "cluster": {
        "id": "uuid",
        "name": "Cluster-01",
        "datacenter": "us-east-1"
      },
      "owner": {
        "id": "uuid",
        "username": "johndoe"
      },
      "created_at": "2026-01-15T10:00:00Z",
      "provisioned_at": "2026-01-15T10:05:32Z"
    }
  ],
  "meta": {
    "total": 12,
    "page": 1,
    "per_page": 20
  }
}
```

#### POST /vms
Create new virtual machine.

**Permission:** `vm:create`

**Request:**
```json
{
  "name": "web-server-02",
  "hostname": "web02.acme.com",
  "description": "Development web server",
  "template_id": "uuid",
  "cpu_cores": 2,
  "memory_mb": 4096,
  "disk_gb": 40,
  "network_id": "uuid",
  "tags": ["production", "web"]
}
```

**Response:** `202 Accepted`
```json
{
  "data": {
    "id": "uuid",
    "name": "web-server-02",
    "status": "provisioning",
    "task_id": "task_uuid"
  },
  "message": "VM provisioning started. Check task status for progress."
}
```

#### GET /vms/:vm_id
Get virtual machine details.

**Permission:** `vm:read`

**Response:** `200 OK`
```json
{
  "data": {
    "id": "uuid",
    "name": "web-server-01",
    "hostname": "web01.acme.com",
    "description": "Production web server",
    "status": "running",
    "power_state": "on",
    "cpu_cores": 4,
    "cpu_sockets": 1,
    "memory_mb": 8192,
    "disks": [
      {
        "id": "uuid",
        "disk_name": "scsi0",
        "size_gb": 40,
        "storage_pool": "local-lvm"
      }
    ],
    "network_interfaces": [
      {
        "ip_address": "10.0.1.10",
        "mac_address": "00:11:22:33:44:55",
        "network_id": "uuid",
        "network_name": "prod-network"
      }
    ],
    "proxmox": {
      "cluster_id": "uuid",
      "cluster_name": "Cluster-01",
      "node_name": "pve-node-01",
      "vmid": 100
    },
    "template": {
      "id": "uuid",
      "name": "Ubuntu 24.04"
    },
    "owner": {
      "id": "uuid",
      "username": "johndoe"
    },
    "metrics": {
      "cpu_usage_percent": 15.3,
      "memory_usage_percent": 45.2,
      "disk_read_mb": 125.5,
      "disk_write_mb": 89.2,
      "network_in_mb": 1245.8,
      "network_out_mb": 987.3
    },
    "created_at": "2026-01-15T10:00:00Z",
    "provisioned_at": "2026-01-15T10:05:32Z",
    "started_at": "2026-01-15T10:05:45Z"
  }
}
```

#### PATCH /vms/:vm_id
Update virtual machine configuration.

**Permission:** `vm:update`

**Request:**
```json
{
  "name": "web-server-01-updated",
  "description": "Updated description",
  "cpu_cores": 6,
  "memory_mb": 16384
}
```

**Response:** `200 OK`

#### DELETE /vms/:vm_id
Delete virtual machine.

**Permission:** `vm:delete`

**Query Parameters:**
- `delete_disks` (boolean): Also delete associated disks

**Response:** `202 Accepted`
```json
{
  "data": {
    "task_id": "task_uuid",
    "message": "VM deletion started"
  }
}
```

#### POST /vms/:vm_id/start
Start virtual machine.

**Permission:** `vm:start`

**Response:** `202 Accepted`
```json
{
  "data": {
    "task_id": "task_uuid",
    "message": "VM start initiated"
  }
}
```

#### POST /vms/:vm_id/stop
Stop virtual machine.

**Permission:** `vm:stop`

**Request (optional):**
```json
{
  "force": false
}
```

**Response:** `202 Accepted`

#### POST /vms/:vm_id/restart
Restart virtual machine.

**Permission:** `vm:stop`, `vm:start`

**Response:** `202 Accepted`

#### POST /vms/:vm_id/snapshots
Create VM snapshot.

**Permission:** `vm:snapshot`

**Request:**
```json
{
  "name": "before-upgrade",
  "description": "Snapshot before system upgrade",
  "include_ram": false
}
```

**Response:** `201 Created`
```json
{
  "data": {
    "id": "uuid",
    "name": "before-upgrade",
    "description": "Snapshot before system upgrade",
    "size_mb": 2048,
    "created_at": "2026-01-31T12:00:00Z"
  }
}
```

#### GET /vms/:vm_id/snapshots
List VM snapshots.

**Permission:** `vm:read`

**Response:** `200 OK`

#### POST /vms/:vm_id/snapshots/:snapshot_id/restore
Restore VM from snapshot.

**Permission:** `vm:update`

**Response:** `202 Accepted`

#### DELETE /vms/:vm_id/snapshots/:snapshot_id
Delete snapshot.

**Permission:** `vm:snapshot`

**Response:** `204 No Content`

#### GET /vms/:vm_id/metrics
Get VM performance metrics.

**Permission:** `vm:read`

**Query Parameters:**
- `start`: Start timestamp
- `end`: End timestamp
- `interval`: Data granularity (1m, 5m, 1h)

**Response:** `200 OK`
```json
{
  "data": {
    "metrics": [
      {
        "timestamp": "2026-01-31T12:00:00Z",
        "cpu_usage_percent": 15.3,
        "memory_usage_percent": 45.2,
        "disk_read_iops": 120,
        "disk_write_iops": 80,
        "network_in_mbps": 5.2,
        "network_out_mbps": 3.8
      }
    ]
  }
}
```

#### GET /vms/:vm_id/console
Get VNC/console access details.

**Permission:** `vm:read`

**Response:** `200 OK`
```json
{
  "data": {
    "console_type": "vnc",
    "url": "wss://console.example.com/vnc/...",
    "ticket": "PVE:ticket...",
    "expires_at": "2026-01-31T13:00:00Z"
  }
}
```

### 4. VM Templates

#### GET /templates
List available VM templates.

**Query Parameters:**
- `category`: Filter by category
- `os_type`: Filter by OS type

**Response:** `200 OK`
```json
{
  "data": [
    {
      "id": "uuid",
      "name": "Ubuntu 24.04 LTS",
      "description": "Ubuntu Server 24.04 LTS",
      "os_type": "linux",
      "os_version": "24.04",
      "category": "linux",
      "icon_url": "https://cdn.example.com/ubuntu.png",
      "default_cpu_cores": 2,
      "default_memory_mb": 2048,
      "default_disk_gb": 20,
      "min_cpu": 1,
      "min_memory_mb": 1024,
      "is_public": true
    }
  ]
}
```

#### GET /templates/:template_id
Get template details.

**Response:** `200 OK`

### 5. Networks

#### GET /networks
List networks.

**Permission:** `network:read`

**Response:** `200 OK`
```json
{
  "data": [
    {
      "id": "uuid",
      "name": "prod-network",
      "description": "Production network",
      "vlan_id": 100,
      "cidr": "10.0.1.0/24",
      "gateway": "10.0.1.1",
      "dns_servers": ["8.8.8.8", "8.8.4.4"],
      "network_type": "private",
      "available_ips": 245,
      "total_ips": 254,
      "is_active": true,
      "created_at": "2026-01-01T00:00:00Z"
    }
  ]
}
```

#### POST /networks
Create new network.

**Permission:** `network:create`

**Request:**
```json
{
  "name": "dev-network",
  "description": "Development network",
  "vlan_id": 101,
  "cidr": "10.0.2.0/24",
  "gateway": "10.0.2.1",
  "dns_servers": ["8.8.8.8"],
  "network_type": "private"
}
```

**Response:** `201 Created`

#### GET /networks/:network_id
Get network details.

**Permission:** `network:read`

**Response:** `200 OK`

#### DELETE /networks/:network_id
Delete network.

**Permission:** `network:delete`

**Response:** `204 No Content`

#### GET /networks/:network_id/ips
List IP addresses in network.

**Permission:** `network:read`

**Response:** `200 OK`
```json
{
  "data": [
    {
      "id": "uuid",
      "ip_address": "10.0.1.10",
      "status": "allocated",
      "vm_id": "uuid",
      "vm_name": "web-server-01",
      "allocated_at": "2026-01-15T10:00:00Z"
    }
  ]
}
```

### 6. Storage

#### GET /storage
List storage pools.

**Permission:** `storage:read`

**Response:** `200 OK`
```json
{
  "data": [
    {
      "id": "uuid",
      "pool_name": "local-lvm",
      "storage_type": "lvm",
      "cluster_name": "Cluster-01",
      "total_gb": 1000,
      "allocated_gb": 240,
      "available_gb": 760,
      "usage_percent": 24.0,
      "is_active": true
    }
  ]
}
```

### 7. Quotas & Usage

#### GET /organizations/:org_id/quotas
Get organization quotas.

**Permission:** `org:read`

**Response:** `200 OK`
```json
{
  "data": {
    "max_vcpu": 100,
    "max_memory_mb": 204800,
    "max_vms": 50,
    "max_storage_gb": 1000,
    "max_snapshots": 100,
    "max_networks": 10,
    "max_ips": 500,
    "current_usage": {
      "vcpu": 24,
      "memory_mb": 49152,
      "vms": 12,
      "storage_gb": 240,
      "snapshots": 15,
      "networks": 3,
      "ips": 35
    },
    "usage_percent": {
      "vcpu": 24.0,
      "memory": 24.0,
      "vms": 24.0,
      "storage": 24.0
    }
  }
}
```

#### PATCH /organizations/:org_id/quotas
Update organization quotas (admin only).

**Permission:** `platform_admin`

**Request:**
```json
{
  "max_vcpu": 200,
  "max_memory_mb": 409600
}
```

**Response:** `200 OK`

#### GET /organizations/:org_id/usage
Get usage statistics.

**Permission:** `org:read`

**Query Parameters:**
- `period`: daily, monthly
- `start_date`: Start date (YYYY-MM-DD)
- `end_date`: End date (YYYY-MM-DD)

**Response:** `200 OK`
```json
{
  "data": {
    "period": "daily",
    "start_date": "2026-01-01",
    "end_date": "2026-01-31",
    "summary": {
      "total_vcpu_hours": 17520,
      "total_memory_gb_hours": 35040,
      "total_storage_gb_hours": 7440,
      "avg_vm_count": 12
    },
    "daily_breakdown": [
      {
        "date": "2026-01-01",
        "vcpu_hours": 576,
        "memory_gb_hours": 1152,
        "storage_gb_hours": 240,
        "vm_count": 12
      }
    ]
  }
}
```

### 8. Tasks & Jobs

#### GET /tasks/:task_id
Get task status.

**Response:** `200 OK`
```json
{
  "data": {
    "id": "uuid",
    "type": "vm_create",
    "status": "running",
    "progress": 65,
    "resource_type": "vm",
    "resource_id": "uuid",
    "started_at": "2026-01-31T12:00:00Z",
    "completed_at": null,
    "result": null,
    "error": null
  }
}
```

### 9. Monitoring & Health

#### GET /health
Health check endpoint (unauthenticated).

**Response:** `200 OK`
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-01-31T12:00:00Z"
}
```

#### GET /health/detailed
Detailed health check (authenticated).

**Response:** `200 OK`
```json
{
  "status": "healthy",
  "services": {
    "database": "healthy",
    "redis": "healthy",
    "message_queue": "healthy",
    "proxmox_clusters": "healthy"
  },
  "version": "1.0.0",
  "timestamp": "2026-01-31T12:00:00Z"
}
```

## Webhooks

Clients can subscribe to events via webhooks.

### POST /webhooks
Create webhook subscription.

**Request:**
```json
{
  "url": "https://example.com/webhook",
  "events": ["vm.created", "vm.deleted", "vm.status_changed"],
  "secret": "webhook_secret"
}
```

**Response:** `201 Created`

### Webhook Payload

```json
{
  "event": "vm.created",
  "timestamp": "2026-01-31T12:00:00Z",
  "data": {
    "vm_id": "uuid",
    "name": "web-server-01",
    "organization_id": "uuid"
  }
}
```

Signature header:
```
X-Webhook-Signature: sha256=abcdef123456...
```

## Pagination

All list endpoints support pagination:

**Query Parameters:**
- `page`: Page number (default: 1)
- `per_page`: Items per page (default: 20, max: 100)

**Response includes:**
- `meta.total`: Total items
- `meta.page`: Current page
- `meta.per_page`: Items per page
- `meta.total_pages`: Total pages
- `links`: Pagination links (first, prev, next, last)

## Filtering & Sorting

List endpoints support filtering and sorting:

**Query Parameters:**
- Field-specific filters: `?status=running&cpu_cores=4`
- Search: `?search=web-server`
- Sort: `?sort=created_at&order=desc`
- Date range: `?created_after=2026-01-01&created_before=2026-01-31`

## Versioning

- API version in URL: `/api/v1/`, `/api/v2/`
- Backward compatibility maintained for 12 months after new version release
- Deprecation warnings in response headers:
  ```
  X-API-Deprecation: This endpoint is deprecated. Use /api/v2/vms instead.
  X-API-Sunset: 2027-01-31
  ```

## Best Practices

1. **Use ETags for caching**: Check `ETag` header and use `If-None-Match`
2. **Handle rate limits**: Check `X-RateLimit-*` headers
3. **Retry with backoff**: For 5xx errors and 429
4. **Use pagination**: Don't fetch all data at once
5. **Validate webhooks**: Verify signature on webhook payloads
6. **Use API keys for automation**: Don't use user tokens in scripts
7. **Monitor task status**: For async operations, poll `/tasks/:task_id`

## OpenAPI Specification

Full OpenAPI 3.0 specification available at:
```
GET /api/v1/openapi.json
```

Interactive docs (Swagger UI):
```
https://api.cloudplatform.example.com/docs
```

## SDK Support

Official SDKs planned for:
- Python
- JavaScript/TypeScript
- Go
- CLI tool

## Next Steps

Refer to:
- [ARCHITECTURE.md](ARCHITECTURE.md) for system design
- [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) for data model
- [TECH_STACK.md](TECH_STACK.md) for implementation details
