# Cloud Management Platform

A comprehensive cloud management portal built on top of Proxmox VE, designed for large-scale multi-tenant deployments (500+ users, 1000+ VMs). Think VMware vCloud Director, but open-source and built for Proxmox.

## Project Overview

This platform provides a self-service portal for managing virtual infrastructure, enabling organizations to:

- **Provision VMs** from Proxmox clusters with a few clicks
- **Manage resources** (compute, storage, networking) through a modern web interface
- **Track usage** and enforce quotas per organization
- **Scale horizontally** across multiple Proxmox clusters and datacenters
- **Multi-tenancy** with complete isolation between organizations
- **Role-based access control** with fine-grained permissions

## Key Features

### Phase 1: Multi-Tenancy & Quota Management ✅ **COMPLETED**

#### For End Users
- ✅ **Self-service VM provisioning** with real-time quota checking
- ✅ **VM lifecycle management** (start, stop, restart, delete)
- ✅ **Organization membership** with role-based permissions
- ✅ **Resource quota tracking** (CPU, memory, storage, VM count)
- ✅ **Real-time status sync** from Proxmox
- ✅ **Organization switcher** for users in multiple organizations
- ✅ **Quota usage dashboard** with visual progress bars

#### For Organization Administrators
- ✅ **Member management** (invite, update roles, remove)
- ✅ **Organization settings** and member list view
- ✅ **Resource quota enforcement** per organization
- ✅ **VM management** for all organization resources
- ✅ **Usage monitoring** and quota tracking

#### For Superadmins
- ✅ **Proxmox cluster management** (add, test connection, sync)
- ✅ **Global resource quota management**
- ✅ **Cross-organization access**
- ✅ **User promotion to superadmin**
- ✅ **Cluster sharing** across organizations

### Phase 2: Modern VM Creation with ISO Upload & Multi-Disk Support ✅ **COMPLETED**

#### ISO Image Management
- ✅ **Upload ISO files** up to 10GB through web interface
- ✅ **ISO deduplication** via SHA256 checksum
- ✅ **Background ISO transfer** to Proxmox with Celery
- ✅ **Organization-scoped ISOs** (private) and public ISOs (shared)
- ✅ **ISO metadata management** (OS type, version, architecture)
- ✅ **Upload progress tracking** with real-time status

#### Multi-Disk VM Support
- ✅ **Multiple disks per VM** with independent configuration
- ✅ **Per-disk storage pool selection** (local-lvm, ceph, NFS, etc.)
- ✅ **Disk interface selection** (SCSI, VirtIO, SATA, IDE)
- ✅ **Boot disk designation** for each VM
- ✅ **Real-time quota validation** across all disks
- ✅ **Dynamic disk add/remove** during VM creation

#### Modern VM Creation UI
- ✅ **Icon-based OS selection** (Linux, Ubuntu, Debian, CentOS, Windows, Other)
- ✅ **Boot configuration** (Boot from Disk vs Boot from ISO)
- ✅ **Wizard-style interface** with sectioned layout
- ✅ **Quick preset buttons** (Small, Medium, Large, X-Large)
- ✅ **Real-time resource display** and validation

#### Storage Management
- ✅ **Storage pool discovery** from Proxmox clusters
- ✅ **Automatic storage sync** every 5 minutes
- ✅ **Capacity and usage tracking** for all pools
- ✅ **Content type filtering** (disk images, ISO, backups)

#### Background Processing
- ✅ **Asynchronous VM provisioning** with Celery
- ✅ **Automatic rollback** on provisioning failure
- ✅ **Status polling** and auto-refresh in UI
- ✅ **Error handling** with detailed messages

### For Platform Operators
- RESTful API for automation
- Comprehensive audit logging
- Horizontal scalability support
- Webhook integrations (planned)

## Architecture

Built with a modern architecture for scalability and reliability:

- **Frontend**: React 18 + TypeScript + Tailwind CSS + TanStack Query
- **Backend**: Python 3.12 + FastAPI + SQLAlchemy 2.0 (async)
- **Database**: PostgreSQL 16 (asyncpg driver)
- **Message Queue**: RabbitMQ + Celery workers (for async tasks)
- **Orchestration**: Docker Compose (development) / Kubernetes (production)
- **Monitoring**: Built-in health checks + logging

```
┌──────────────┐
│   Users      │
└──────┬───────┘
       │
       ▼
┌──────────────────────┐
│   Load Balancer      │
└──────┬───────────────┘
       │
       ├─────────────┬─────────────┐
       ▼             ▼             ▼
┌───────────┐  ┌──────────┐  ┌──────────┐
│ Frontend  │  │ API Layer│  │  Workers │
│ (React)   │  │(FastAPI) │  │ (Celery) │
└───────────┘  └────┬─────┘  └────┬─────┘
                    │             │
       ┌────────────┼─────────────┘
       │            │
       ▼            ▼
┌──────────┐  ┌──────────┐
│PostgreSQL│  │  Redis   │
└──────────┘  └──────────┘
       │
       ▼
┌─────────────────────────┐
│   Proxmox VE Clusters   │
└─────────────────────────┘
```

## Documentation

### 📋 Phase Documentation
- **[PHASE1_ARCHITECTURE.md](docs/PHASE1_ARCHITECTURE.md)** - Complete Phase 1 implementation details
  - Multi-tenancy architecture with organization model
  - RBAC system (4 roles, 20+ permissions)
  - Quota management and enforcement
  - Database schema with ERD diagrams
  - API endpoints and data flow
  - Testing strategy and deployment guide

- **[PHASE2_ISO_MULTIDISK.md](docs/PHASE2_ISO_MULTIDISK.md)** - Complete Phase 2 implementation details
  - ISO image upload and management system
  - Multi-disk VM support with independent configuration
  - Storage pool discovery and synchronization
  - Modern wizard-style VM creation UI
  - Background provisioning with Celery
  - API documentation and usage examples

### Other Documentation
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System architecture overview
- **[DATABASE_SCHEMA.md](DATABASE_SCHEMA.md)** - Database design
- **[API_SPECIFICATION.md](API_SPECIFICATION.md)** - API documentation
- **[TECH_STACK.md](TECH_STACK.md)** - Technology choices
- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Production deployment

## 🚀 Quick Start

### Prerequisites
- **Docker & Docker Compose** - [Install Docker](https://docs.docker.com/get-docker/)
- **PostgreSQL 16** (if running locally without Docker)
- **Python 3.12+** (for backend development)
- **Node.js 20+** (for frontend development)

### Setup and Run

**1. Start the Backend:**

```bash
cd backend

# Run database migrations
alembic upgrade head

# Start the FastAPI server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**2. Start the Frontend:**

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

**3. Create Your First User:**

```bash
# Register a new user
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

**4. Setup Organizations and Users:**

```bash
# After migrations, users need to be added to the default organization
cd backend
python add_users_to_default_org.py

# Promote user to superadmin (optional)
python make_superadmin.py admin@example.com
```

**5. Add a Proxmox Cluster:**

Login to http://localhost:3000 as a superadmin and navigate to Clusters → Add Cluster. Provide your Proxmox API details (API URL, credentials, etc.).

### Access Points

- **Frontend Dashboard**: http://localhost:3000
- **API Documentation**: http://localhost:8000/docs
- **API Base URL**: http://localhost:8000/api/v1

### Test Connection

```bash
# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"ChangeMe123!"}'

# Use the access_token from response
export TOKEN="<access_token>"

# Get organizations
curl http://localhost:8000/api/v1/organizations/me \
  -H "Authorization: Bearer $TOKEN"

# Create a VM (requires X-Organization-ID header)
curl -X POST http://localhost:8000/api/v1/vms \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Organization-ID: <org_id>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "test-vm",
    "hostname": "test-vm",
    "cpu_cores": 2,
    "cpu_sockets": 1,
    "memory_mb": 2048,
    "os_type": "linux"
  }'
```

## Project Status

**Current Phase:** Phase 2.1 Complete ✅ → Phase 3 Planning

### ✅ Phase 1 Completed (Multi-Tenancy & Quota Management)
- ✅ **Multi-tenant architecture** with organizations
- ✅ **RBAC system** (Superadmin, Org Admin, Org Member, Org Viewer)
- ✅ **Organization management** (members, roles, invitations)
- ✅ **Resource quota system** (CPU, memory, storage, VM count, cluster count)
- ✅ **Quota enforcement** (pre-creation checks and real-time tracking)
- ✅ **VM provisioning** with Proxmox integration
- ✅ **VM lifecycle management** (start, stop, restart, delete)
- ✅ **VM status synchronization** from Proxmox
- ✅ **Proxmox cluster management** (add, test, sync)
- ✅ **Frontend dashboards** (VMs, Quotas, Organization Settings)
- ✅ **Auto-refresh for provisioning VMs**
- ✅ **Database migrations** with Alembic
- ✅ **PostgreSQL compatibility** and optimization
- ✅ **Helper scripts** (add users, make superadmin)

### ✅ Phase 2 Completed (Modern VM Creation with ISO Upload & Multi-Disk Support)
- ✅ **ISO image upload and management** (up to 10GB files)
- ✅ **ISO deduplication** via SHA256 checksum
- ✅ **Background ISO transfer** to Proxmox with Celery tasks
- ✅ **Organization-scoped and public ISOs**
- ✅ **Multi-disk VM support** with independent configuration
- ✅ **Per-disk storage pool selection** (local-lvm, ceph, NFS, etc.)
- ✅ **Disk interface selection** (SCSI, VirtIO, SATA, IDE)
- ✅ **Boot from ISO** capability for OS installation
- ✅ **Storage pool discovery and sync** from Proxmox
- ✅ **Modern wizard-style VM creation UI**
- ✅ **Icon-based OS selection** (6 OS options)
- ✅ **Asynchronous VM provisioning** with error handling
- ✅ **Real-time quota validation** for multi-disk VMs
- ✅ **Automatic rollback** on provisioning failure
- ✅ **Full backward compatibility** with existing VMs

### ✅ Phase 2.1 Completed (Advanced VM Management & Disk Operations)
- ✅ **Advanced VM lifecycle operations** (Force Stop, Reset, Restart)
- ✅ **Reorganized UI** (Start/Stop as primary actions, More dropdown for advanced)
- ✅ **VNC console access** for running VMs (via Proxmox noVNC)
- ✅ **Dynamic disk management** (attach, detach, resize)
- ✅ **Disk resize** with real-time quota validation
- ✅ **ISO attachment to CD-ROM** for running VMs
- ✅ **VM snapshot management** (create, rollback, delete)
- ✅ **Memory state preservation** in snapshots
- ✅ **VM resize** (CPU and memory) with quota enforcement
- ✅ **React Portal dropdowns** for table menus (no clipping)
- ✅ **Boot disk protection** (cannot delete boot disk)
- ✅ **Storage tab** in VM detail page
- ✅ **Snapshots tab** in VM detail page

### Phase 2.1: Advanced VM Management & Disk Operations ✅ **COMPLETED**

#### VM Lifecycle Operations
- ✅ **Reorganized VM actions** (Start/Stop moved to primary buttons)
- ✅ **Force Stop** with immediate hard stop (no graceful shutdown)
- ✅ **VM Reset** (hard reset like pressing reset button)
- ✅ **VM Restart** with graceful shutdown
- ✅ **Actions available on stopped VMs** (Force Stop, Reset)
- ✅ **VNC Console access** for running VMs
- ✅ **Real-time VM status updates** with auto-refresh

#### Disk Management
- ✅ **Dynamic disk resize** (increase disk size online)
- ✅ **Disk attach/detach** (add or remove disks from VMs)
- ✅ **ISO attachment** to CD-ROM (mount ISO to VMs)
- ✅ **Storage pool selection** per disk
- ✅ **Boot disk protection** (cannot delete boot disk)
- ✅ **Real-time disk status** tracking
- ✅ **Quota validation** for disk operations

#### Snapshot Management
- ✅ **VM snapshot creation** with optional memory state
- ✅ **Snapshot rollback** to previous states
- ✅ **Snapshot deletion** and management
- ✅ **Snapshot metadata** (description, creation time)
- ✅ **Memory state preservation** for running VMs
- ✅ **Parent snapshot tracking** for snapshot chains

### Key Fixes Applied
- ✅ Fixed cluster test endpoint (proper connection validation)
- ✅ Fixed disk format compatibility (LVM-Thin support)
- ✅ Fixed VM status handling (async provisioning flow)
- ✅ Fixed ostype mapping (Proxmox compatibility)
- ✅ Fixed VMID type handling (string to int conversion)
- ✅ Fixed cluster sharing (is_shared flag)
- ✅ Fixed authentication UI (radio button labels)
- ✅ Fixed Force Stop API (use Proxmox stop instead of shutdown)
- ✅ Fixed VM resize quota calculation (MB to GB conversion)
- ✅ Fixed dropdown menu visibility in tables (React Portal)

### 🚧 Phase 3 Roadmap (VPC Networking)
- ⬜ **VLAN-based network isolation** per organization
- ⬜ **VPC and Subnet management** (IPAM)
- ⬜ **Automatic network configuration** in Proxmox
- ⬜ **IP address management** and allocation
- ⬜ **Network security groups** and firewall rules

### 📋 Phase 4+ Roadmap (Advanced Features)
- ⬜ **VM templates and catalogs** (pre-configured VMs)
- ✅ **Snapshots and backups** management (Phase 2.1)
- ✅ **Disk resize** (expand disks) (Phase 2.1)
- ✅ **Live disk attach/detach** (Phase 2.1)
- ✅ **VM console access** (VNC/noVNC) (Phase 2.1)
- ⬜ **Disk migration** (move between storage pools)
- ⬜ **Audit logging** for all organization actions
- ⬜ **Organization-level settings** and billing
- ⬜ **Custom roles and permissions**
- ⬜ **Resource tagging** and cost allocation
- ⬜ **Advanced monitoring and alerts**
- ⬜ **Multi-cluster load balancing**
- ⬜ **API integrations and webhooks**

## API Examples

### Basic Operations

```bash
# Authenticate
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"password"}'

# List your organizations
curl http://localhost:8000/api/v1/organizations/me \
  -H "Authorization: Bearer <token>"

# Check quotas
curl http://localhost:8000/api/v1/quotas \
  -H "Authorization: Bearer <token>" \
  -H "X-Organization-ID: <org_id>"
```

### ISO Management (Phase 2)

```bash
# Upload an ISO
curl -X POST http://localhost:8000/api/v1/isos/upload \
  -H "Authorization: Bearer <token>" \
  -H "X-Organization-ID: <org_id>" \
  -F "file=@ubuntu-22.04-server-amd64.iso" \
  -F "name=ubuntu-22.04.iso" \
  -F "display_name=Ubuntu 22.04 LTS" \
  -F "os_type=ubuntu" \
  -F "os_version=22.04"

# List available ISOs
curl http://localhost:8000/api/v1/isos?include_public=true \
  -H "Authorization: Bearer <token>" \
  -H "X-Organization-ID: <org_id>"
```

### VM Creation

```bash
# Create a simple VM (single disk)
curl -X POST http://localhost:8000/api/v1/vms \
  -H "Authorization: Bearer <token>" \
  -H "X-Organization-ID: <org_id>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "web-server",
    "cpu_cores": 2,
    "memory_mb": 4096,
    "os_type": "linux",
    "disks": [
      {
        "size_gb": 40,
        "storage_pool": "local-lvm",
        "is_boot_disk": true
      }
    ]
  }'

# Create VM with multiple disks and ISO boot (Phase 2)
curl -X POST http://localhost:8000/api/v1/vms \
  -H "Authorization: Bearer <token>" \
  -H "X-Organization-ID: <org_id>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "database-server",
    "cpu_cores": 8,
    "memory_mb": 16384,
    "os_type": "linux",
    "disks": [
      {
        "size_gb": 50,
        "storage_pool": "local-lvm",
        "disk_interface": "scsi",
        "is_boot_disk": true
      },
      {
        "size_gb": 500,
        "storage_pool": "ceph-ssd",
        "disk_interface": "scsi",
        "is_boot_disk": false
      }
    ],
    "iso_image_id": "<iso_id>",
    "boot_order": "cdrom,disk"
  }'

# List VMs in organization
curl http://localhost:8000/api/v1/vms \
  -H "Authorization: Bearer <token>" \
  -H "X-Organization-ID: <org_id>"

# Sync VM status from Proxmox
curl -X POST http://localhost:8000/api/v1/vms/<vm_id>/sync \
  -H "Authorization: Bearer <token>" \
  -H "X-Organization-ID: <org_id>"
```

### Storage Management (Phase 2)

```bash
# List available storage pools
curl http://localhost:8000/api/v1/storage/pools \
  -H "Authorization: Bearer <token>" \
  -H "X-Organization-ID: <org_id>"

# Sync storage pools from Proxmox
curl -X POST http://localhost:8000/api/v1/storage/clusters/<cluster_id>/pools/sync \
  -H "Authorization: Bearer <token>" \
  -H "X-Organization-ID: <org_id>"
```

### Disk Management (Phase 2.1)

```bash
# List VM disks
curl http://localhost:8000/api/v1/vms/<vm_id>/disks \
  -H "Authorization: Bearer <token>" \
  -H "X-Organization-ID: <org_id>"

# Add a disk to VM
curl -X POST http://localhost:8000/api/v1/vms/<vm_id>/disks \
  -H "Authorization: Bearer <token>" \
  -H "X-Organization-ID: <org_id>" \
  -H "Content-Type: application/json" \
  -d '{
    "size_gb": 100,
    "storage_pool": "ceph-ssd",
    "disk_interface": "scsi",
    "disk_format": "raw"
  }'

# Resize a disk
curl -X PATCH http://localhost:8000/api/v1/vms/<vm_id>/disks/<disk_id>/resize \
  -H "Authorization: Bearer <token>" \
  -H "X-Organization-ID: <org_id>" \
  -H "Content-Type: application/json" \
  -d '{
    "new_size_gb": 200
  }'

# Attach ISO to VM
curl -X POST http://localhost:8000/api/v1/vms/<vm_id>/disks/attach-iso \
  -H "Authorization: Bearer <token>" \
  -H "X-Organization-ID: <org_id>" \
  -H "Content-Type: application/json" \
  -d '{
    "iso_image_id": "<iso_id>"
  }'

# Detach disk from VM
curl -X DELETE http://localhost:8000/api/v1/vms/<vm_id>/disks/<disk_id> \
  -H "Authorization: Bearer <token>" \
  -H "X-Organization-ID: <org_id>"
```

### Snapshot Management (Phase 2.1)

```bash
# List VM snapshots
curl http://localhost:8000/api/v1/vms/<vm_id>/snapshots \
  -H "Authorization: Bearer <token>" \
  -H "X-Organization-ID: <org_id>"

# Create a snapshot
curl -X POST http://localhost:8000/api/v1/vms/<vm_id>/snapshots \
  -H "Authorization: Bearer <token>" \
  -H "X-Organization-ID: <org_id>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "before-upgrade",
    "description": "Snapshot before system upgrade",
    "include_memory": true
  }'

# Rollback to a snapshot
curl -X POST http://localhost:8000/api/v1/vms/<vm_id>/snapshots/<snapshot_name>/rollback \
  -H "Authorization: Bearer <token>" \
  -H "X-Organization-ID: <org_id>"

# Delete a snapshot
curl -X DELETE http://localhost:8000/api/v1/vms/<vm_id>/snapshots/<snapshot_name> \
  -H "Authorization: Bearer <token>" \
  -H "X-Organization-ID: <org_id>"
```

### Advanced VM Operations (Phase 2.1)

```bash
# Force stop VM (immediate hard stop)
curl -X POST http://localhost:8000/api/v1/vms/<vm_id>/force-stop \
  -H "Authorization: Bearer <token>" \
  -H "X-Organization-ID: <org_id>"

# Reset VM (hard reset)
curl -X POST http://localhost:8000/api/v1/vms/<vm_id>/reset \
  -H "Authorization: Bearer <token>" \
  -H "X-Organization-ID: <org_id>"

# Restart VM (graceful)
curl -X POST http://localhost:8000/api/v1/vms/<vm_id>/restart \
  -H "Authorization: Bearer <token>" \
  -H "X-Organization-ID: <org_id>"

# Get VM console URL
curl http://localhost:8000/api/v1/vms/<vm_id>/console \
  -H "Authorization: Bearer <token>" \
  -H "X-Organization-ID: <org_id>"

# Resize VM resources
curl -X PATCH http://localhost:8000/api/v1/vms/<vm_id>/resize \
  -H "Authorization: Bearer <token>" \
  -H "X-Organization-ID: <org_id>" \
  -H "Content-Type: application/json" \
  -d '{
    "cpu_cores": 4,
    "memory_mb": 8192
  }'
```

Full API documentation: [API_SPECIFICATION.md](API_SPECIFICATION.md) or http://localhost:8000/docs

## Security

Security features implemented:
- ✅ JWT-based authentication with refresh tokens
- ✅ RBAC with 4 roles and 20+ granular permissions
- ✅ Organization-scoped resource access
- ✅ Permission-based API endpoint protection
- ✅ Soft delete pattern for audit trail
- ✅ Password hashing (bcrypt)
- ⬜ API rate limiting (planned)
- ⬜ Audit logging (planned)

## Multi-Tenancy Implementation

### Organization Context
All API requests (except auth) require the `X-Organization-ID` header to specify which organization context the request operates in. This ensures complete isolation between organizations.

### Roles and Permissions

| Role | Permissions |
|------|-------------|
| **Superadmin** | Full access to all organizations and resources, manage clusters, update quotas |
| **Org Admin** | Manage organization members, view/manage all org VMs, update org settings |
| **Org Member** | Create/manage own VMs, view own resources, read-only org info |
| **Org Viewer** | Read-only access to organization resources |

### Resource Quotas

Each organization has quota limits for:
- **CPU cores** - Total vCPUs across all VMs
- **Memory** - Total RAM in GB
- **Storage** - Total disk space in GB
- **VM count** - Maximum number of VMs
- **Cluster count** - Number of dedicated clusters (if any)

Quotas are enforced **before** resource creation and tracked in real-time.

## Target Scale

Designed to support:
- **500+ users** across multiple organizations
- **1000+ VMs** with real-time management
- **Multiple Proxmox clusters** (shared or org-specific)
- **Multi-datacenter deployments** (Phase 3+)
- **99.9% uptime SLA** with HA architecture

## Contributing

Contributions welcome! Areas where help is needed:

1. **Backend Development**
   - Phase 2: VPC networking implementation
   - Background jobs for status syncing
   - Advanced monitoring and alerts

2. **Frontend Development**
   - VM console access (VNC/noVNC)
   - Advanced dashboards and visualizations
   - Mobile-responsive improvements

3. **DevOps**
   - Kubernetes deployment manifests
   - CI/CD pipelines
   - Monitoring setup (Prometheus/Grafana)

4. **Documentation**
   - User guides and tutorials
   - API integration examples
   - Video walkthroughs

## Troubleshooting

### Common Issues

**VMs stuck in "provisioning" status:**
```bash
# Update status manually
UPDATE virtual_machines SET status = 'stopped' WHERE status = 'provisioning';

# Or use the sync endpoint
curl -X POST http://localhost:8000/api/v1/vms/<vm_id>/sync \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Organization-ID: $ORG_ID"
```

**User has no organizations:**
```bash
# Add user to default organization
cd backend
python add_users_to_default_org.py
```

**Need to make user superadmin:**
```bash
# Promote user to superadmin
cd backend
python make_superadmin.py user@example.com
```

**Cluster not showing for VM creation:**
```sql
-- Make sure cluster is shared
UPDATE proxmox_clusters SET is_shared = true WHERE deleted_at IS NULL;
```

## License

TBD - Likely MIT or Apache 2.0

## Acknowledgments

Built with:
- [Proxmox VE](https://www.proxmox.com/en/proxmox-ve) - Open-source virtualization platform
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [React](https://react.dev/) - UI library
- [PostgreSQL](https://www.postgresql.org/) - Database
- [Proxmoxer](https://github.com/proxmoxer/proxmoxer) - Proxmox API client
- [SQLAlchemy](https://www.sqlalchemy.org/) - SQL toolkit and ORM
- [Alembic](https://alembic.sqlalchemy.org/) - Database migrations
- [TanStack Query](https://tanstack.com/query) - Data fetching and caching
- [Tailwind CSS](https://tailwindcss.com/) - Utility-first CSS framework

Inspired by:
- VMware vCloud Director
- OpenStack Horizon
- Proxmox Virtual Environment

## Authors

- **Architecture Design & Implementation**: Claude Code + Development Team
- **Phase 1 Multi-Tenancy**: Complete ✅
- **Active Development**: Ongoing

## Support

- **Documentation**: See docs/ folder and PHASE1_ARCHITECTURE.md
- **API Docs**: http://localhost:8000/docs
- **Issues**: Report bugs and request features via GitHub Issues

---

**Phase 1, 2 & 2.1 Complete! 🎉**

✅ **Phase 1**: Multi-tenant cloud management with quota enforcement
✅ **Phase 2**: Modern VM creation with ISO upload and multi-disk support
✅ **Phase 2.1**: Advanced VM management, disk operations, and snapshots

Start managing your Proxmox infrastructure with:
- **Organizational isolation** and resource control
- **ISO-based VM deployment** with custom images
- **Advanced multi-disk** storage configuration
- **Dynamic disk management** (resize, attach, detach)
- **VM snapshots** for backup and recovery
- **Advanced VM operations** (force stop, reset, console access)
- **Beautiful, modern UI** with improved UX

Next up: **Phase 3** - VPC Networking with VLAN isolation! 🚀
