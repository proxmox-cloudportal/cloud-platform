# Phase 1 Architecture: Multi-Tenancy & Quota Management

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [System Architecture](#system-architecture)
3. [Database Design](#database-design)
4. [Backend Architecture](#backend-architecture)
5. [Frontend Architecture](#frontend-architecture)
6. [Security Model](#security-model)
7. [API Design](#api-design)
8. [Data Flow](#data-flow)
9. [Implementation Guide](#implementation-guide)
10. [Testing Strategy](#testing-strategy)
11. [Deployment Guide](#deployment-guide)
12. [Monitoring & Operations](#monitoring--operations)

---

## Executive Summary

### Overview
Phase 1 implements organization-based multi-tenancy with role-based access control (RBAC) and resource quota management for the cloud platform. This provides the foundation for isolated, secure resource management across multiple tenants.

### Key Features
- **Multi-Tenancy**: Organizations as primary tenant boundary with user membership
- **RBAC**: 4 roles (Superadmin, Org Admin, Org Member, Org Viewer) with 20+ granular permissions
- **Quota Management**: Per-organization resource limits with real-time enforcement
- **Backward Compatibility**: Seamless migration of existing resources to default organization

### Technology Stack
- **Backend**: Python 3.11+, FastAPI, SQLAlchemy 2.0, Alembic
- **Frontend**: React 18, TypeScript, Zustand, TailwindCSS
- **Database**: MySQL 8.0+
- **Authentication**: JWT tokens with refresh mechanism

---

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend (React)                      │
│  ┌─────────────────┐  ┌──────────────┐  ┌────────────────┐ │
│  │ Org Switcher    │  │ Quota Page   │  │ Org Settings   │ │
│  │ Component       │  │              │  │ Page           │ │
│  └─────────────────┘  └──────────────┘  └────────────────┘ │
│                                                               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │          Auth Store (Zustand)                         │  │
│  │  - Current Organization                               │  │
│  │  - Organization Memberships                           │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ HTTPS/JSON + X-Organization-ID Header
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                     API Gateway (FastAPI)                    │
│  ┌───────────────────────────────────────────────────────┐  │
│  │        Request Interceptor (Middleware)               │  │
│  │  - JWT Validation                                     │  │
│  │  - Organization Context Extraction                    │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   Authorization Layer (RBAC)                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Org Context  │  │ Permission   │  │ Role Matrix  │      │
│  │ Dependencies │  │ Checker      │  │              │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      Business Logic Layer                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Quota        │  │ VM           │  │ Organization │      │
│  │ Service      │  │ Service      │  │ Service      │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Data Access Layer (ORM)                   │
│                     SQLAlchemy 2.0 Models                    │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Database (MySQL 8.0+)                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │  users   │  │   orgs   │  │org_members│ │quotas    │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│  ┌──────────┐  ┌──────────┐                                │
│  │   vms    │  │ clusters │                                │
│  └──────────┘  └──────────┘                                │
└─────────────────────────────────────────────────────────────┘
```

### Component Interaction Flow

```
User Action → Frontend Component → API Call with Org Header
    ↓
API Endpoint → Dependency Injection → get_organization_context()
    ↓
Organization Context Validation:
    - Verify X-Organization-ID header
    - Validate user membership in organization
    - Load user's role in organization
    - Create OrgContext object
    ↓
Permission Check → RequirePermission(Permission.XXX)
    ↓
    ├─ If Superadmin: ✓ Allow all
    ├─ Else: Check role permissions in ROLE_PERMISSIONS matrix
    └─ If denied: HTTP 403 Forbidden
    ↓
Business Logic:
    ├─ For VM Create: Check quotas → QuotaService.check_quota_availability()
    ├─ Filter resources by organization_id
    └─ Enforce ownership (members only see own VMs)
    ↓
Database Operation → Return Response
```

---

## Database Design

### Entity Relationship Diagram

```
┌─────────────────────┐
│      users          │
│─────────────────────│
│ id (PK)             │
│ email               │
│ username            │
│ password_hash       │
│ is_superadmin       │
│ created_at          │
│ deleted_at          │
└─────────────────────┘
          │ 1
          │
          │ N
          ▼
┌─────────────────────┐         ┌─────────────────────┐
│ organization_members│ N     1 │   organizations     │
│─────────────────────│◄────────│─────────────────────│
│ id (PK)             │         │ id (PK)             │
│ user_id (FK)        │         │ name                │
│ organization_id (FK)│         │ slug (UNIQUE)       │
│ role                │         │ description         │
│ joined_at           │         │ created_at          │
│ invited_by (FK)     │         │ deleted_at          │
│ created_at          │         └─────────────────────┘
│ deleted_at          │                   │ 1
└─────────────────────┘                   │
                                          │ N
                                          ▼
                        ┌─────────────────────────────┐
                        │   resource_quotas           │
                        │─────────────────────────────│
                        │ id (PK)                     │
                        │ organization_id (FK)        │
                        │ resource_type (cpu_cores,   │
                        │   memory_gb, storage_gb,    │
                        │   vm_count, cluster_count)  │
                        │ limit_value                 │
                        │ used_value                  │
                        │ last_calculated_at          │
                        │ created_at                  │
                        │ deleted_at                  │
                        └─────────────────────────────┘
                                          │ 1
                                          │
                                          │ N
                                          ▼
                        ┌─────────────────────────────┐
                        │   virtual_machines          │
                        │─────────────────────────────│
                        │ id (PK)                     │
                        │ organization_id (FK) NOT NULL│
                        │ owner_id (FK)               │
                        │ name                        │
                        │ cpu_cores                   │
                        │ memory_mb                   │
                        │ disk_gb                     │
                        │ status                      │
                        │ created_at                  │
                        │ deleted_at                  │
                        └─────────────────────────────┘

                        ┌─────────────────────────────┐
                        │   proxmox_clusters          │
                        │─────────────────────────────│
                        │ id (PK)                     │
                        │ organization_id (FK) NULL   │
                        │ is_shared BOOLEAN           │
                        │ name                        │
                        │ api_url                     │
                        │ created_at                  │
                        │ deleted_at                  │
                        └─────────────────────────────┘
```

### Key Constraints & Indexes

**organization_members:**
- UNIQUE(user_id, organization_id) - User can only be member once per org
- INDEX(user_id) - Fast lookup of user's organizations
- INDEX(organization_id, role) - Fast filtering by org and role

**resource_quotas:**
- UNIQUE(organization_id, resource_type) - One quota per resource per org
- CHECK(limit_value >= 0) - Non-negative limits
- CHECK(used_value >= 0) - Non-negative usage
- INDEX(organization_id, resource_type) - Fast quota lookups

**virtual_machines:**
- NOT NULL organization_id - Every VM must belong to an org (after migration)
- INDEX(organization_id) - Fast filtering by organization
- INDEX(owner_id) - Fast lookup of user's VMs

**proxmox_clusters:**
- INDEX(organization_id) - Fast filtering by organization
- is_shared=true means cluster available to all organizations

---

## Backend Architecture

### Layered Architecture

```
┌───────────────────────────────────────────────────────────┐
│                     API Layer (FastAPI)                    │
│  /app/api/v1/endpoints/                                    │
│  - vms.py          : VM CRUD + lifecycle operations        │
│  - organizations.py: Member management                     │
│  - quotas.py       : Quota viewing and updates             │
│  - auth.py         : Authentication                        │
│  - users.py        : User profile management               │
│  - clusters.py     : Cluster management                    │
└───────────────────────────────────────────────────────────┘
                            ▲
                            │ Uses
                            ▼
┌───────────────────────────────────────────────────────────┐
│                  Dependency Layer                          │
│  /app/core/deps.py                                         │
│                                                            │
│  get_organization_context(org_id: str) → OrgContext       │
│  ├─ Validates X-Organization-ID header                    │
│  ├─ Checks user membership in organization                │
│  ├─ Loads user's role                                     │
│  └─ Returns OrgContext with permission checker            │
│                                                            │
│  RequirePermission(permission: Permission)                 │
│  ├─ Factory for permission-based dependencies             │
│  └─ Returns dependency that checks permission             │
│                                                            │
│  get_current_org_admin() → OrgContext                     │
│  └─ Shorthand for admin-only endpoints                   │
└───────────────────────────────────────────────────────────┘
                            ▲
                            │ Uses
                            ▼
┌───────────────────────────────────────────────────────────┐
│                   RBAC Layer                               │
│  /app/core/rbac.py                                         │
│                                                            │
│  Role(Enum):                                               │
│  - SUPERADMIN : Global admin                              │
│  - ORG_ADMIN  : Organization administrator                │
│  - ORG_MEMBER : Standard member                           │
│  - ORG_VIEWER : Read-only viewer                          │
│                                                            │
│  Permission(Enum): 20+ granular permissions               │
│  - VM_CREATE, VM_READ, VM_UPDATE, VM_DELETE, ...         │
│  - ORG_MEMBER_INVITE, ORG_MEMBER_UPDATE_ROLE, ...        │
│  - QUOTA_READ, QUOTA_UPDATE, ...                          │
│                                                            │
│  ROLE_PERMISSIONS: Dict[Role, Set[Permission]]            │
│  └─ Maps each role to its allowed permissions             │
│                                                            │
│  has_permission(role, permission) → bool                  │
│  └─ Checks if role has specific permission                │
└───────────────────────────────────────────────────────────┘
                            ▲
                            │ Uses
                            ▼
┌───────────────────────────────────────────────────────────┐
│                  Service Layer                             │
│  /app/services/                                            │
│                                                            │
│  QuotaService:                                             │
│  - check_quota_availability() : Pre-check before VM create│
│  - increment_usage()          : Update after allocation   │
│  - decrement_usage()          : Update after deallocation │
│  - recalculate_usage()        : Fix drift from DB         │
│  - get_all_quotas()           : Ensure all quotas exist   │
│  - update_quota_limit()       : Admin quota adjustment    │
│                                                            │
│  (Future: VMService, ProxmoxService, etc.)                │
└───────────────────────────────────────────────────────────┘
                            ▲
                            │ Uses
                            ▼
┌───────────────────────────────────────────────────────────┐
│                   Model Layer (ORM)                        │
│  /app/models/                                              │
│  - user.py                : User model                     │
│  - organization.py        : Organization model             │
│  - organization_member.py : Membership model               │
│  - resource_quota.py      : Quota model                    │
│  - virtual_machine.py     : VM model                       │
│  - proxmox_cluster.py     : Cluster model                  │
│                                                            │
│  All models extend BaseModel with:                         │
│  - id (UUID primary key)                                  │
│  - created_at, updated_at (timestamps)                    │
│  - deleted_at (soft delete)                               │
└───────────────────────────────────────────────────────────┘
                            ▲
                            │ SQLAlchemy 2.0
                            ▼
┌───────────────────────────────────────────────────────────┐
│                      Database (MySQL)                      │
└───────────────────────────────────────────────────────────┘
```

### Key Design Patterns

**1. Dependency Injection (FastAPI)**
```python
@router.post("/vms")
async def create_vm(
    vm_data: VMCreateRequest,
    org_context: OrgContext = Depends(RequirePermission(Permission.VM_CREATE)),
    db: AsyncSession = Depends(get_db)
):
    # org_context is automatically validated and injected
    # Permission check happens before function execution
    pass
```

**2. Factory Pattern (Permission Dependencies)**
```python
def RequirePermission(permission: Permission):
    async def _require_permission(
        org_context: OrgContext = Depends(get_organization_context)
    ) -> OrgContext:
        if not org_context.has_permission(permission):
            raise HTTPException(403, f"Permission denied: {permission.value}")
        return org_context
    return _require_permission
```

**3. Service Layer Pattern**
```python
class QuotaService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def check_quota_availability(self, org_id, cpu, memory, storage, vm_count):
        # Business logic isolated from API layer
        pass
```

**4. Repository Pattern (via SQLAlchemy)**
```python
result = await db.execute(
    select(VirtualMachine).where(
        VirtualMachine.organization_id == org_id,
        VirtualMachine.deleted_at.is_(None)
    )
)
vms = result.scalars().all()
```

---

## Frontend Architecture

### Component Hierarchy

```
App
├─ LoginPage
└─ Layout (Authenticated Routes)
    ├─ Sidebar
    │   ├─ Logo
    │   ├─ OrganizationSwitcher ← New
    │   │   └─ Dropdown with org list
    │   ├─ Navigation Links
    │   │   ├─ Dashboard
    │   │   ├─ Virtual Machines
    │   │   ├─ Proxmox Clusters
    │   │   ├─ Resource Quotas ← New
    │   │   ├─ Organization ← New
    │   │   └─ Settings
    │   └─ User Profile
    │
    └─ Main Content Area
        ├─ DashboardPage
        ├─ VMsPage
        ├─ CreateVMPage
        ├─ VMDetailPage
        ├─ ClustersPage
        ├─ CreateClusterPage
        ├─ QuotaPage ← New
        └─ OrganizationSettingsPage ← New
```

### State Management (Zustand)

```typescript
// authStore.ts - Global state
interface AuthState {
  // User authentication
  user: User | null
  accessToken: string | null
  isAuthenticated: boolean

  // Organization context ← New
  currentOrganization: Organization | null
  organizations: OrganizationMembership[]

  // Actions
  setAuth(user, tokens): void
  clearAuth(): void
  setOrganizations(orgs): void
  setCurrentOrganization(org): void ← New
}
```

### API Service Architecture

```typescript
// api.ts structure
export const api = axios.create({ baseURL: API_URL })

// Request Interceptor
api.interceptors.request.use((config) => {
  // Add JWT token
  config.headers.Authorization = `Bearer ${token}`

  // Add organization context ← New
  const org = JSON.parse(localStorage.getItem('current_organization'))
  config.headers['X-Organization-ID'] = org.id

  return config
})

// API Modules
export const authApi = { login, register, getCurrentUser }
export const vmsApi = { list, create, update, delete, start, stop }
export const organizationsApi = { ← New
  listMyOrganizations,
  listMembers,
  inviteMember,
  updateMemberRole,
  removeMember
}
export const quotasApi = { ← New
  getQuotas,
  getUsage,
  updateLimit,
  recalculate
}
```

### React Component Patterns

**1. Custom Hooks (Future Enhancement)**
```typescript
// useOrganization.ts
function useOrganization() {
  const { currentOrganization, setCurrentOrganization } = useAuthStore()

  const switchOrganization = (org: Organization) => {
    setCurrentOrganization(org)
    window.location.reload() // Refresh with new context
  }

  return { currentOrganization, switchOrganization }
}
```

**2. Protected Components**
```typescript
// RoleGuard.tsx (Future)
function RoleGuard({ requiredRole, children }) {
  const { organizations, currentOrganization } = useAuthStore()
  const membership = organizations.find(o => o.organization.id === currentOrganization?.id)

  if (membership?.role !== requiredRole) {
    return <AccessDenied />
  }

  return children
}
```

---

## Security Model

### Authentication Flow

```
1. User Login
   ├─ POST /auth/login {email, password}
   ├─ Backend validates credentials
   ├─ Returns: { access_token, refresh_token, user }
   └─ Frontend stores tokens in localStorage

2. API Request with Auth
   ├─ Frontend includes: Authorization: Bearer {access_token}
   ├─ Backend validates JWT signature and expiry
   ├─ Extracts user_id from token
   └─ Loads User from database

3. Token Refresh (on 401)
   ├─ POST /auth/refresh {refresh_token}
   ├─ Backend validates refresh token
   ├─ Issues new access_token
   └─ Frontend retries original request
```

### Authorization Flow

```
1. Organization Context Extraction
   ├─ Read X-Organization-ID header
   ├─ Query organization_members table
   ├─ WHERE user_id = current_user.id
   │   AND organization_id = header_org_id
   │   AND deleted_at IS NULL
   └─ If not found → HTTP 403

2. Role-Based Permission Check
   ├─ Check if user.is_superadmin → Allow all
   ├─ Else: Lookup role in ROLE_PERMISSIONS
   ├─ Check if Permission.XXX in allowed_permissions
   └─ If not allowed → HTTP 403

3. Resource-Level Authorization
   ├─ For VM operations:
   │   ├─ Filter by organization_id
   │   └─ If role == MEMBER: Filter by owner_id
   │
   ├─ For Organization operations:
   │   └─ User must be member of target organization
   │
   └─ For Quota updates:
       └─ Require SUPERADMIN role
```

### Permission Matrix

| Resource Action | Superadmin | Org Admin | Org Member | Org Viewer |
|----------------|-----------|-----------|------------|-----------|
| **VM Operations** |
| View all org VMs | ✓ | ✓ | Own only | ✓ |
| Create VM | ✓ | ✓ | ✓ | ✗ |
| Update VM | ✓ | ✓ | Own only | ✗ |
| Delete VM | ✓ | ✓ | Own only | ✗ |
| Start/Stop/Restart VM | ✓ | ✓ | Own only | ✗ |
| **Organization Management** |
| View members | ✓ | ✓ | ✓ | ✓ |
| Invite member | ✓ | ✓ | ✗ | ✗ |
| Update member role | ✓ | ✓ | ✗ | ✗ |
| Remove member | ✓ | ✓ | ✗ | ✗ |
| **Quota Management** |
| View quotas | ✓ | ✓ | ✓ | ✓ |
| Update quota limits | ✓ | ✗ | ✗ | ✗ |
| Recalculate usage | ✓ | ✗ | ✗ | ✗ |
| **Cluster Management** |
| View clusters | ✓ | ✓ | ✓ | ✓ |
| Create cluster | ✓ | ✗ | ✗ | ✗ |
| Update cluster | ✓ | ✗ | ✗ | ✗ |
| Delete cluster | ✓ | ✗ | ✗ | ✗ |

### Security Best Practices Implemented

1. **Password Security**
   - Passwords hashed with bcrypt (cost factor 12)
   - No plain-text passwords stored or logged

2. **Token Security**
   - Access tokens expire after 30 minutes
   - Refresh tokens expire after 7 days
   - Tokens invalidated on logout

3. **SQL Injection Prevention**
   - SQLAlchemy ORM with parameterized queries
   - No raw SQL string concatenation

4. **Authorization Bypass Prevention**
   - Organization context validated on every request
   - No client-side permission checks only
   - Database-level foreign key constraints

5. **Soft Deletes**
   - Resources marked deleted, not removed
   - Maintains audit trail and referential integrity

---

## API Design

### REST API Endpoints

#### Virtual Machines
```
GET    /api/v1/vms
       Headers: X-Organization-ID
       Params: page, per_page, status, search
       Returns: List of VMs (filtered by org and role)

POST   /api/v1/vms
       Headers: X-Organization-ID
       Body: { name, cpu_cores, memory_mb, disk_gb, ... }
       Process: 1. Check quota availability
                2. Select cluster (org-specific or shared)
                3. Create VM record with organization_id
                4. Increment quota usage
                5. Provision on Proxmox
                6. Rollback quota on failure
       Returns: Created VM

GET    /api/v1/vms/{vm_id}
       Headers: X-Organization-ID
       Authorization: Must be in same org, admin or owner
       Returns: VM details

PATCH  /api/v1/vms/{vm_id}
       Headers: X-Organization-ID
       Body: { name?, cpu_cores?, memory_mb?, ... }
       Authorization: Admin or owner only
       Returns: Updated VM

DELETE /api/v1/vms/{vm_id}
       Headers: X-Organization-ID
       Process: 1. Delete VM from Proxmox
                2. Soft delete DB record
                3. Decrement quota usage
       Authorization: Admin or owner only

POST   /api/v1/vms/{vm_id}/start
POST   /api/v1/vms/{vm_id}/stop
POST   /api/v1/vms/{vm_id}/restart
       Headers: X-Organization-ID
       Authorization: Admin or owner only
       Returns: Action status
```

#### Organizations
```
GET    /api/v1/organizations/me
       Returns: List of organizations user belongs to
       Response: [
         {
           organization: { id, name, slug, description },
           role: "admin" | "member" | "viewer",
           joined_at: "2024-01-31T..."
         }
       ]

GET    /api/v1/organizations/{org_id}/members
       Headers: X-Organization-ID
       Authorization: Must be member of org
       Returns: List of organization members

POST   /api/v1/organizations/{org_id}/members
       Headers: X-Organization-ID
       Body: { user_id, role }
       Authorization: ORG_MEMBER_INVITE permission (admin)
       Returns: Created membership

PATCH  /api/v1/organizations/{org_id}/members/{user_id}
       Headers: X-Organization-ID
       Body: { role }
       Authorization: ORG_MEMBER_UPDATE_ROLE permission (admin)
       Validation: Cannot demote yourself if last admin
       Returns: Updated membership

DELETE /api/v1/organizations/{org_id}/members/{user_id}
       Headers: X-Organization-ID
       Authorization: ORG_MEMBER_REMOVE permission (admin)
       Validation: Cannot remove yourself if last admin
       Process: Soft delete membership
```

#### Quotas
```
GET    /api/v1/quotas
       Headers: X-Organization-ID
       Returns: List of all quota limits for organization
       Response: [
         {
           id, organization_id, resource_type,
           limit_value, used_value, last_calculated_at
         }
       ]

GET    /api/v1/quotas/usage
       Headers: X-Organization-ID
       Returns: Detailed usage with percentages
       Response: {
         organization_id,
         resources: [
           {
             resource_type: "cpu_cores",
             resource_name: "CPU Cores",
             used: 10, limit: 100, remaining: 90,
             usage_percentage: 10.0,
             last_calculated: "2024-01-31T..."
           }
         ]
       }

PUT    /api/v1/quotas/{resource_type}
       Headers: X-Organization-ID
       Body: { limit_value }
       Authorization: QUOTA_UPDATE permission (superadmin only)
       Returns: Updated quota

POST   /api/v1/quotas/recalculate
       Headers: X-Organization-ID
       Authorization: Superadmin only
       Process: Recalculates usage from actual DB resources
       Returns: { message, organization_id }
```

### Error Responses

```json
{
  "detail": "Human-readable error message"
}
```

**Common HTTP Status Codes:**
- 400 Bad Request - Validation error, quota exceeded
- 401 Unauthorized - Invalid or missing token
- 403 Forbidden - Permission denied, not org member
- 404 Not Found - Resource not found
- 422 Unprocessable Entity - Pydantic validation error
- 500 Internal Server Error - Unexpected server error

---

## Data Flow

### VM Creation Flow with Quota Enforcement

```
Frontend                Backend                    Database
   │                       │                          │
   │ POST /api/v1/vms      │                          │
   │ X-Org-ID: org-123     │                          │
   │ {cpu:4, mem:8, disk:50}│                          │
   ├──────────────────────>│                          │
   │                       │                          │
   │                       │ 1. Validate JWT         │
   │                       │    Extract user         │
   │                       │                          │
   │                       │ 2. Validate org context │
   │                       │ SELECT * FROM org_members│
   │                       │ WHERE user_id=? AND org_id=?
   │                       ├─────────────────────────>│
   │                       │<─────────────────────────┤
   │                       │ membership found          │
   │                       │                          │
   │                       │ 3. Check permission     │
   │                       │    role.has(VM_CREATE)?  │
   │                       │    ✓ Yes                │
   │                       │                          │
   │                       │ 4. Check quota availability
   │                       │ SELECT * FROM quotas    │
   │                       │ WHERE org_id=?          │
   │                       ├─────────────────────────>│
   │                       │<─────────────────────────┤
   │                       │ cpu: used=10, limit=100  │
   │                       │ mem: used=50, limit=512  │
   │                       │                          │
   │                       │ QuotaService.check():   │
   │                       │ - cpu: 10+4 <= 100 ✓    │
   │                       │ - mem: 50+8 <= 512 ✓    │
   │                       │ - storage: 500+50<=5000✓│
   │                       │ - vm_count: 5+1 <= 50 ✓ │
   │                       │                          │
   │                       │ 5. Select cluster       │
   │                       │ SELECT * FROM clusters  │
   │                       │ WHERE (org_id=? OR      │
   │                       │        is_shared=true)  │
   │                       ├─────────────────────────>│
   │                       │<─────────────────────────┤
   │                       │ cluster found            │
   │                       │                          │
   │                       │ 6. Create VM record     │
   │                       │ INSERT INTO vms (...)   │
   │                       │ VALUES (org_id=org-123,...)
   │                       ├─────────────────────────>│
   │                       │<─────────────────────────┤
   │                       │ vm_id=vm-456            │
   │                       │                          │
   │                       │ 7. Increment quota usage│
   │                       │ UPDATE quotas SET       │
   │                       │   used_value = used+4   │
   │                       │ WHERE org_id=? AND      │
   │                       │   resource_type='cpu'   │
   │                       ├─────────────────────────>│
   │                       │<─────────────────────────┤
   │                       │                          │
   │                       │ 8. Provision on Proxmox │
   │                       │ proxmox.create_vm(...)  │
   │                       │                          │
   │                       │ IF ERROR:               │
   │                       │   - Rollback DB         │
   │                       │   - Decrement quota     │
   │                       │   - Return error        │
   │                       │                          │
   │<──────────────────────┤                          │
   │ 201 Created           │                          │
   │ {vm details}          │                          │
```

### Organization Switching Flow

```
Frontend                Backend                    Database
   │                       │                          │
   │ User clicks org       │                          │
   │ dropdown              │                          │
   │                       │                          │
   │ Select "Org B"        │                          │
   │                       │                          │
   │ setCurrentOrganization│                          │
   │ (orgB)                │                          │
   │                       │                          │
   │ localStorage.setItem  │                          │
   │ ('current_org', orgB) │                          │
   │                       │                          │
   │ window.location.reload│                          │
   │                       │                          │
   │ ─── Page Reloads ──── │                          │
   │                       │                          │
   │ All API calls now     │                          │
   │ include:              │                          │
   │ X-Organization-ID: orgB                          │
   │                       │                          │
   │ GET /api/v1/vms       │                          │
   ├──────────────────────>│                          │
   │                       │                          │
   │                       │ SELECT * FROM vms       │
   │                       │ WHERE organization_id=orgB
   │                       │   AND deleted_at IS NULL│
   │                       ├─────────────────────────>│
   │                       │<─────────────────────────┤
   │                       │ VMs from Org B only     │
   │<──────────────────────┤                          │
   │ Display Org B's VMs   │                          │
```

---

## Implementation Guide

### Step-by-Step Implementation (Already Completed)

#### Phase 1.1: Database Models ✅
```bash
Files Created:
- /backend/app/models/organization_member.py
- /backend/app/models/resource_quota.py

Files Modified:
- /backend/app/models/organization.py (added relationships)
- /backend/app/models/virtual_machine.py (added organization relationship)
- /backend/app/models/proxmox_cluster.py (added org_id, is_shared)
```

#### Phase 1.2: RBAC System ✅
```bash
Files Created:
- /backend/app/core/rbac.py (Role, Permission enums, ROLE_PERMISSIONS)

Files Modified:
- /backend/app/core/deps.py (added OrgContext, get_organization_context, RequirePermission)
```

#### Phase 1.3: Services ✅
```bash
Files Created:
- /backend/app/services/quota_service.py (QuotaService class)
```

#### Phase 1.4: API Endpoints ✅
```bash
Files Modified:
- /backend/app/api/v1/endpoints/vms.py (added org context, quota checks)

Files Created:
- /backend/app/api/v1/endpoints/organizations.py (member management)
- /backend/app/api/v1/endpoints/quotas.py (quota management)

Files Modified:
- /backend/app/api/v1/router.py (registered new routers)
```

#### Phase 1.5: Schemas ✅
```bash
Files Created:
- /backend/app/schemas/organization_member.py
- /backend/app/schemas/quota.py
```

#### Phase 1.6: Database Migrations ✅
```bash
Files Created:
- /backend/alembic/versions/2026_01_31_1830-*_add_multi_tenancy_tables.py
- /backend/alembic/versions/2026_01_31_1831-*_migrate_existing_data_to_default_org.py
- /backend/alembic/versions/2026_01_31_1832-*_make_vm_organization_required.py
- /backend/alembic/MIGRATION_GUIDE.md

Files Modified:
- /backend/alembic/env.py (imported new models)
```

#### Phase 1.7: Frontend State & API ✅
```bash
Files Modified:
- /frontend/src/stores/authStore.ts (added org context)
- /frontend/src/services/api.ts (added X-Org-ID header, org/quota APIs)
```

#### Phase 1.8: Frontend Components ✅
```bash
Files Created:
- /frontend/src/components/OrganizationSwitcher.tsx
- /frontend/src/pages/QuotaPage.tsx
- /frontend/src/pages/OrganizationSettingsPage.tsx

Files Modified:
- /frontend/src/components/Sidebar.tsx (added switcher, new nav items)
- /frontend/src/App.tsx (added new routes)
```

### Running the Implementation

#### 1. Database Migration
```bash
cd backend

# Backup database
mysqldump -u root -p cloud_platform > backup_$(date +%Y%m%d_%H%M%S).sql

# Run migrations
alembic upgrade head

# Verify
mysql -u root -p cloud_platform -e "
  SELECT COUNT(*) FROM organization_members;
  SELECT COUNT(*) FROM resource_quotas;
  SELECT * FROM organizations WHERE slug='default';
"
```

#### 2. Backend Startup
```bash
cd backend

# Install dependencies (if not done)
pip install -r requirements.txt

# Start server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Check logs for errors
tail -f logs/app.log
```

#### 3. Frontend Startup
```bash
cd frontend

# Install dependencies (if not done)
npm install

# Start dev server
npm run dev

# Build for production
npm run build
```

#### 4. Post-Deployment Verification

**Backend Health Check:**
```bash
curl http://localhost:8000/api/v1/health
```

**Login and Get Organizations:**
```bash
# Login
TOKEN=$(curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"password"}' \
  | jq -r '.access_token')

# Get organizations
curl http://localhost:8000/api/v1/organizations/me \
  -H "Authorization: Bearer $TOKEN"

# Get quotas (replace ORG_ID)
curl http://localhost:8000/api/v1/quotas/usage \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Organization-ID: <ORG_ID>"
```

---

## Testing Strategy

### Unit Tests

**Backend Tests (pytest):**
```python
# tests/test_rbac.py
def test_superadmin_has_all_permissions():
    assert has_permission(Role.SUPERADMIN, Permission.VM_CREATE)
    assert has_permission(Role.SUPERADMIN, Permission.QUOTA_UPDATE)

def test_org_member_limited_permissions():
    assert has_permission(Role.ORG_MEMBER, Permission.VM_CREATE)
    assert not has_permission(Role.ORG_MEMBER, Permission.ORG_MEMBER_INVITE)

# tests/test_quota_service.py
@pytest.mark.asyncio
async def test_quota_check_within_limit(db_session):
    quota_service = QuotaService(db_session)
    result = await quota_service.check_quota_availability(
        org_id="test-org",
        cpu_cores=10,
        memory_gb=16,
        storage_gb=100,
        vm_count=1
    )
    assert result.is_available == True

@pytest.mark.asyncio
async def test_quota_check_exceeds_limit(db_session):
    quota_service = QuotaService(db_session)
    result = await quota_service.check_quota_availability(
        org_id="test-org",
        cpu_cores=200,  # Exceeds limit of 100
        memory_gb=16,
        storage_gb=100,
        vm_count=1
    )
    assert result.is_available == False
    assert "cpu_cores" in result.exceeded_resources
```

### Integration Tests

**API Tests:**
```python
# tests/test_vm_with_quota.py
@pytest.mark.asyncio
async def test_create_vm_within_quota(client, auth_headers, org_id):
    response = await client.post(
        "/api/v1/vms",
        headers={**auth_headers, "X-Organization-ID": org_id},
        json={
            "name": "test-vm",
            "cpu_cores": 2,
            "memory_mb": 2048,
            "disk_gb": 20
        }
    )
    assert response.status_code == 201

    # Verify quota was incremented
    response = await client.get(
        "/api/v1/quotas",
        headers={**auth_headers, "X-Organization-ID": org_id}
    )
    cpu_quota = next(q for q in response.json() if q["resource_type"] == "cpu_cores")
    assert cpu_quota["used_value"] == 2

@pytest.mark.asyncio
async def test_create_vm_exceeds_quota(client, auth_headers, org_id):
    response = await client.post(
        "/api/v1/vms",
        headers={**auth_headers, "X-Organization-ID": org_id},
        json={
            "name": "test-vm",
            "cpu_cores": 200,  # Exceeds limit
            "memory_mb": 2048,
            "disk_gb": 20
        }
    )
    assert response.status_code == 400
    assert "quota exceeded" in response.json()["detail"].lower()
```

### Manual Test Cases

**Scenario 1: Multi-Organization Access**
1. Create User A
2. Create Org 1 and Org 2
3. Add User A to both orgs with different roles (admin in Org 1, member in Org 2)
4. Login as User A
5. Switch to Org 1 → Should see all VMs
6. Switch to Org 2 → Should see only own VMs
7. Try to invite member in Org 2 → Should fail (no permission)

**Scenario 2: Quota Enforcement**
1. Set CPU quota to 10 cores for test org
2. Create VM with 5 cores → Success
3. Check quota usage → Should show 5/10 used
4. Try to create VM with 6 cores → Should fail (quota exceeded)
5. Delete first VM → Quota should decrease to 0/10
6. Create VM with 6 cores → Should succeed

**Scenario 3: Role-Based Access**
1. Org Admin: Create VM, invite member, update member role → All succeed
2. Org Member: Create VM → Success, Invite member → Fail
3. Org Viewer: View VMs → Success, Create VM → Fail

---

## Deployment Guide

### Production Deployment Checklist

#### 1. Pre-Deployment
- [ ] Backup database
- [ ] Review migration scripts
- [ ] Test migrations on staging environment
- [ ] Update environment variables
- [ ] Build frontend assets
- [ ] Run test suite

#### 2. Database Migration
```bash
# On production server
cd /opt/cloud-platform/backend

# Backup
mysqldump -u app_user -p cloud_platform > /backups/db_$(date +%Y%m%d_%H%M%S).sql

# Run migrations
alembic upgrade head

# Verify
mysql -u app_user -p cloud_platform -e "SELECT version_num FROM alembic_version;"
```

#### 3. Backend Deployment
```bash
# Pull latest code
cd /opt/cloud-platform
git pull origin main

# Install dependencies
cd backend
pip install -r requirements.txt

# Restart service
sudo systemctl restart cloud-platform-api
sudo systemctl status cloud-platform-api

# Check logs
sudo journalctl -u cloud-platform-api -f
```

#### 4. Frontend Deployment
```bash
cd /opt/cloud-platform/frontend

# Build
npm run build

# Deploy to nginx
sudo cp -r dist/* /var/www/cloud-platform/

# Reload nginx
sudo nginx -t
sudo systemctl reload nginx
```

#### 5. Post-Deployment Verification
```bash
# Health check
curl https://api.cloud-platform.com/api/v1/health

# Test auth
curl https://api.cloud-platform.com/api/v1/auth/me \
  -H "Authorization: Bearer $TOKEN"

# Test organization endpoint
curl https://api.cloud-platform.com/api/v1/organizations/me \
  -H "Authorization: Bearer $TOKEN"

# Check error logs
tail -f /var/log/cloud-platform/error.log
```

### Environment Variables

**Backend (.env):**
```bash
# Database
DATABASE_URL=mysql+asyncpg://user:password@localhost:3306/cloud_platform

# Security
SECRET_KEY=<generate-random-64-char-string>
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# CORS
ALLOWED_ORIGINS=https://cloud-platform.com,https://www.cloud-platform.com

# Proxmox (existing)
# ...
```

**Frontend (.env):**
```bash
VITE_API_URL=https://api.cloud-platform.com/api/v1
```

### Nginx Configuration

```nginx
# Frontend
server {
    listen 443 ssl http2;
    server_name cloud-platform.com www.cloud-platform.com;

    ssl_certificate /etc/letsencrypt/live/cloud-platform.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/cloud-platform.com/privkey.pem;

    root /var/www/cloud-platform;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }
}

# Backend API
server {
    listen 443 ssl http2;
    server_name api.cloud-platform.com;

    ssl_certificate /etc/letsencrypt/live/api.cloud-platform.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.cloud-platform.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## Monitoring & Operations

### Key Metrics to Monitor

**Application Metrics:**
- Request rate by endpoint
- Response time (p50, p95, p99)
- Error rate (4xx, 5xx)
- Active users
- Organization count
- VM creation/deletion rate

**Resource Metrics:**
- Quota usage percentage by organization
- VMs per organization
- Database connection pool usage
- API server CPU/memory usage

**Business Metrics:**
- Organizations near quota limits (>80%)
- Failed VM creations due to quota
- Average VMs per organization
- Organization member churn

### Logging Strategy

**Structured Logging (JSON):**
```python
import structlog

logger = structlog.get_logger()

# Log organization context
logger.info(
    "vm_created",
    vm_id=vm.id,
    organization_id=org_context.org_id,
    user_id=org_context.user.id,
    cpu_cores=vm.cpu_cores,
    memory_mb=vm.memory_mb
)

# Log quota events
logger.warning(
    "quota_approaching_limit",
    organization_id=org_id,
    resource_type="cpu_cores",
    usage_percentage=85.3,
    used=85,
    limit=100
)
```

**Log Aggregation:**
- Ship logs to Elasticsearch/Loki
- Create dashboards for quota usage trends
- Alert on quota >90% usage
- Alert on repeated permission denied errors

### Operational Procedures

**Quota Adjustment:**
```bash
# Superadmin increases org CPU quota
curl -X PUT https://api.cloud-platform.com/api/v1/quotas/cpu_cores \
  -H "Authorization: Bearer $SUPERADMIN_TOKEN" \
  -H "X-Organization-ID: $ORG_ID" \
  -H "Content-Type: application/json" \
  -d '{"limit_value": 200}'
```

**Quota Drift Fix:**
```bash
# Recalculate quotas from actual usage
curl -X POST https://api.cloud-platform.com/api/v1/quotas/recalculate \
  -H "Authorization: Bearer $SUPERADMIN_TOKEN" \
  -H "X-Organization-ID: $ORG_ID"
```

**Emergency: Disable Organization (Future)**
```sql
-- Soft delete all VMs
UPDATE virtual_machines
SET deleted_at = NOW()
WHERE organization_id = 'problem-org-id';

-- Remove all members except admins
UPDATE organization_members
SET deleted_at = NOW()
WHERE organization_id = 'problem-org-id'
  AND role != 'admin';
```

---

## Next Steps (Phase 2+)

### Phase 2: VPC Networking (Deferred)
- VLAN-based network isolation
- VPC, Subnet, and IPAM models
- Automatic network provisioning in Proxmox
- Network ACLs and security groups

### Phase 3: Advanced Features
- **Audit Logging**: Track all organization actions
- **Billing Integration**: Usage-based billing per organization
- **Custom Roles**: Admin-defined roles with custom permissions
- **Resource Tagging**: Cost allocation and filtering
- **Scheduled Operations**: Automated VM start/stop schedules
- **Backup Management**: Per-organization backup policies
- **Notifications**: Quota alerts, maintenance notifications

### Phase 4: Scale & Performance
- **Caching Layer**: Redis for quota lookups
- **Read Replicas**: Separate read/write database connections
- **Async Task Queue**: Celery for long-running operations
- **API Rate Limiting**: Per-organization rate limits
- **Multi-Region**: Cross-region organization replication

---

## Appendix

### Code References

**Backend Files:**
- Database Models: `/backend/app/models/`
- RBAC System: `/backend/app/core/rbac.py`
- Dependencies: `/backend/app/core/deps.py`
- Services: `/backend/app/services/quota_service.py`
- API Endpoints: `/backend/app/api/v1/endpoints/`
- Migrations: `/backend/alembic/versions/`

**Frontend Files:**
- State Management: `/frontend/src/stores/authStore.ts`
- API Service: `/frontend/src/services/api.ts`
- Components: `/frontend/src/components/OrganizationSwitcher.tsx`
- Pages: `/frontend/src/pages/{Quota,OrganizationSettings}Page.tsx`

### Database Schema SQL

See migration files for complete SQL:
- `/backend/alembic/versions/2026_01_31_1830-*_add_multi_tenancy_tables.py`

### API Documentation

Once deployed, access interactive API docs:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Support & Troubleshooting

For issues:
1. Check `/backend/alembic/MIGRATION_GUIDE.md` for migration problems
2. Review logs: `tail -f /var/log/cloud-platform/*.log`
3. Verify organization membership: `SELECT * FROM organization_members WHERE user_id='...'`
4. Check quota accuracy: Run `/api/v1/quotas/recalculate`

---

**Document Version:** 1.0
**Last Updated:** 2026-01-31
**Author:** Cloud Platform Team
**Status:** ✅ Implemented
