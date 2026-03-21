# Phase 2: Modern VM Creation with ISO Upload & Multi-Disk Support

**Status:** ✅ **COMPLETED**
**Completion Date:** February 1, 2026

## Overview

Phase 2 introduces a completely modernized VM creation experience with advanced storage management capabilities. Users can now upload ISO images, create VMs with multiple disks, configure per-disk storage pools, and boot directly from ISO images for OS installation.

## Key Features Implemented

### 1. ISO Image Management ✅

A complete ISO management system that enables users to upload, manage, and boot VMs from ISO images.

**Features:**
- Upload ISO files up to 10GB through the web interface
- Automatic SHA256 checksum calculation for deduplication
- Background transfer of ISOs to Proxmox storage using Celery tasks
- Organization-scoped ISOs (private) and public ISOs (shared)
- ISO metadata management (name, OS type, version, architecture)
- Upload progress tracking and status monitoring
- Automatic cleanup of failed uploads

**User Flow:**
1. Navigate to **VM Templates → ISOs**
2. Click "Upload ISO" and select file
3. Fill in metadata (display name, OS type, version)
4. Upload progresses with real-time status
5. ISO automatically transfers to Proxmox in background
6. Use ISO for VM creation when status is "ready"

### 2. Multi-Disk VM Support ✅

VMs can now be created with multiple disks, each with independent configuration.

**Features:**
- Add multiple disks to a single VM
- Configure each disk independently:
  - Size (10 GB - 10 TB)
  - Storage pool selection (local-lvm, ceph, NFS, etc.)
  - Disk interface (SCSI, VirtIO, SATA, IDE)
  - Boot disk designation
- Real-time quota validation across all disks
- Add/remove disks dynamically during VM creation
- Automatic boot disk selection (first disk by default)

**Supported Disk Interfaces:**
- **SCSI** (Recommended) - Best performance, hotplug support
- **VirtIO** - High performance for Linux guests
- **SATA** - Legacy compatibility
- **IDE** - Legacy compatibility

### 3. Storage Pool Discovery ✅

Automatic discovery and synchronization of storage pools from Proxmox clusters.

**Features:**
- Query available storage pools from all Proxmox clusters
- Cache storage metadata (type, capacity, usage)
- Filter pools by content type (disk images, ISO, backups)
- Display real-time capacity and availability
- Periodic background sync every 5 minutes
- Manual sync on-demand

**Supported Storage Types:**
- LVM-Thin (local-lvm)
- Ceph RBD
- NFS
- ZFS
- Directory-based storage

### 4. Modern VM Creation UI ✅

Complete redesign of the VM creation interface with a wizard-style layout.

**New Sections:**

#### a. Operating System Selection
- Icon-based OS selector with 6 options:
  - 🐧 Linux (Generic)
  - 🟠 Ubuntu
  - 🔴 Debian
  - 💚 CentOS/Rocky/Alma
  - 🪟 Windows Server
  - ❓ Other
- Visual feedback with checkmark for selected OS

#### b. Boot Configuration
- Tab interface for boot method selection:
  - **Boot from Disk** - Direct boot from primary disk
  - **Boot from ISO** - Boot from mounted ISO for installation
- ISO selection dropdown with ready ISOs
- Link to upload new ISO images
- Informational messages about boot behavior

#### c. Disk Configuration
- Dynamic disk list with add/remove buttons
- Per-disk configuration:
  - Size input (GB)
  - Storage pool dropdown
  - Interface selector
  - Boot disk toggle
- Visual boot disk indicator
- Real-time storage quota tracking
- Warning when quota exceeded

#### d. Resource Configuration
- CPU cores slider (1-64)
- Memory slider (512 MB - 512 GB)
- Quick preset buttons (Small, Medium, Large, X-Large)
- Real-time resource display

### 5. Background VM Provisioning ✅

VM creation is now fully asynchronous with Celery background tasks.

**Provisioning Flow:**
1. Validate quota and permissions
2. Create VM record with "provisioning" status
3. Create disk records in database
4. Queue Celery task for Proxmox provisioning
5. Return 202 Accepted to user immediately
6. Background worker:
   - Creates base VM in Proxmox
   - Adds each disk one-by-one
   - Mounts ISO as CD-ROM (if selected)
   - Sets boot order (ISO first if applicable)
   - Updates VM status to "stopped" when complete
7. Auto-refresh on frontend polls for status updates

**Error Handling:**
- Automatic rollback on failure
- VM deletion from Proxmox if provisioning fails
- Quota release on error
- Detailed error messages in UI

## Architecture

### Database Schema

#### New Tables

**1. iso_images**
```sql
CREATE TABLE iso_images (
    id VARCHAR(36) PRIMARY KEY,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    deleted_at TIMESTAMP NULL,

    -- Ownership
    organization_id VARCHAR(36) NULL REFERENCES organizations(id),
    uploaded_by VARCHAR(36) NOT NULL REFERENCES users(id),
    is_public BOOLEAN NOT NULL DEFAULT FALSE,

    -- ISO Metadata
    name VARCHAR(255) NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    description TEXT NULL,
    os_type VARCHAR(50) NULL,
    os_version VARCHAR(100) NULL,
    architecture VARCHAR(20) DEFAULT 'x86_64',

    -- File Information
    filename VARCHAR(255) NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    checksum_sha256 VARCHAR(64) NOT NULL UNIQUE,

    -- Storage Location
    storage_backend VARCHAR(50) DEFAULT 'local',
    local_path TEXT NULL,
    proxmox_cluster_id VARCHAR(36) NULL REFERENCES proxmox_clusters(id),
    proxmox_storage VARCHAR(100) NULL,
    proxmox_volid VARCHAR(255) NULL,

    -- Upload Status
    upload_status VARCHAR(50) DEFAULT 'uploading',
    upload_progress FLOAT DEFAULT 0.0,
    error_message TEXT NULL,

    uploaded_at TIMESTAMP NULL,
    synced_to_proxmox_at TIMESTAMP NULL
);
```

**2. vm_disks**
```sql
CREATE TABLE vm_disks (
    id VARCHAR(36) PRIMARY KEY,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    deleted_at TIMESTAMP NULL,

    -- VM Association
    vm_id VARCHAR(36) NOT NULL REFERENCES virtual_machines(id) ON DELETE CASCADE,

    -- Disk Configuration
    disk_index INT NOT NULL,
    disk_interface VARCHAR(20) NOT NULL,  -- scsi, ide, virtio, sata
    disk_number INT NOT NULL,

    -- Storage
    storage_pool VARCHAR(100) NOT NULL,
    size_gb INT NOT NULL,
    disk_format VARCHAR(20) NULL,  -- raw, qcow2

    -- Disk Type
    is_boot_disk BOOLEAN DEFAULT FALSE,
    is_cdrom BOOLEAN DEFAULT FALSE,

    -- ISO Mount (for CD-ROM)
    iso_image_id VARCHAR(36) NULL REFERENCES iso_images(id),

    -- Proxmox Details
    proxmox_disk_id VARCHAR(255) NULL,

    -- Status
    status VARCHAR(50) DEFAULT 'creating',
    attached_at TIMESTAMP NULL,

    UNIQUE(vm_id, disk_interface, disk_number)
);
```

**3. storage_pools**
```sql
CREATE TABLE storage_pools (
    id VARCHAR(36) PRIMARY KEY,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    deleted_at TIMESTAMP NULL,

    -- Proxmox Association
    proxmox_cluster_id VARCHAR(36) NOT NULL REFERENCES proxmox_clusters(id),
    storage_name VARCHAR(100) NOT NULL,
    storage_type VARCHAR(50) NOT NULL,

    -- Capabilities
    content_types JSON NOT NULL,  -- ["images", "iso", "backup"]

    -- Capacity
    total_bytes BIGINT NULL,
    used_bytes BIGINT NULL,
    available_bytes BIGINT NULL,

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    is_shared BOOLEAN DEFAULT FALSE,

    -- Sync
    last_synced_at TIMESTAMP NULL,

    UNIQUE(proxmox_cluster_id, storage_name)
);
```

**4. Modified: virtual_machines**
```sql
ALTER TABLE virtual_machines
ADD COLUMN boot_order VARCHAR(100) NULL;
```

### Backend Components

#### Models
- `/backend/app/models/iso_image.py` - ISOImage model
- `/backend/app/models/vm_disk.py` - VMDisk model
- `/backend/app/models/storage_pool.py` - StoragePool model

#### Services
- `/backend/app/services/proxmox_service.py` - Enhanced with ISO/disk/storage methods
- `/backend/app/services/quota_service.py` - Updated for multi-disk quota calculation

#### API Endpoints
- `/backend/app/api/v1/endpoints/isos.py` - ISO management API
- `/backend/app/api/v1/endpoints/storage.py` - Storage pool API
- `/backend/app/api/v1/endpoints/disks.py` - VM disk management API
- `/backend/app/api/v1/endpoints/vms.py` - Updated for multi-disk creation

#### Background Tasks
- `/backend/app/tasks/celery_app.py` - Celery configuration
- `/backend/app/tasks/iso_tasks.py` - ISO upload and transfer tasks
- `/backend/app/tasks/vm_tasks.py` - VM provisioning with disks
- `/backend/app/tasks/sync_tasks.py` - Storage pool sync (every 5 min)

### Frontend Components

#### Pages
- `/frontend/src/pages/CreateVMPage.tsx` - Modern wizard-style VM creation
- `/frontend/src/pages/ISOUploadPage.tsx` - ISO upload and management

#### Components
- `/frontend/src/components/vm/OSSelectionSection.tsx` - Icon-based OS selector
- `/frontend/src/components/vm/BootConfigurationSection.tsx` - Boot method + ISO selection
- `/frontend/src/components/vm/DiskConfigurationSection.tsx` - Multi-disk configuration

#### API Services
- `/frontend/src/services/api.ts` - Extended with ISO, storage, and disk APIs

## API Documentation

### ISO Management Endpoints

**Upload ISO**
```http
POST /api/v1/isos/upload
Content-Type: multipart/form-data
Authorization: Bearer {token}
X-Organization-ID: {org_id}

Form Data:
- file: (binary)
- name: ubuntu-22.04-server-amd64.iso
- display_name: Ubuntu 22.04 LTS Server
- description: Ubuntu Server 22.04 LTS installation media
- os_type: ubuntu
- os_version: 22.04
- architecture: x86_64
- is_public: false

Response: 202 Accepted
{
  "id": "iso-uuid",
  "name": "ubuntu-22.04-server-amd64.iso",
  "display_name": "Ubuntu 22.04 LTS Server",
  "upload_status": "processing",
  "checksum_sha256": "abc123..."
}
```

**List ISOs**
```http
GET /api/v1/isos?include_public=true
Authorization: Bearer {token}
X-Organization-ID: {org_id}

Response: 200 OK
{
  "data": [
    {
      "id": "iso-uuid",
      "display_name": "Ubuntu 22.04 LTS Server",
      "os_type": "ubuntu",
      "os_version": "22.04",
      "file_size_bytes": 1234567890,
      "upload_status": "ready",
      "is_public": false,
      "uploaded_at": "2026-02-01T10:00:00Z"
    }
  ],
  "total": 1
}
```

**Delete ISO**
```http
DELETE /api/v1/isos/{iso_id}
Authorization: Bearer {token}
X-Organization-ID: {org_id}

Response: 204 No Content
```

### Storage Pool Endpoints

**List Storage Pools**
```http
GET /api/v1/storage/pools?content_type=images
Authorization: Bearer {token}
X-Organization-ID: {org_id}

Response: 200 OK
{
  "data": [
    {
      "id": "pool-uuid",
      "storage_name": "local-lvm",
      "storage_type": "lvmthin",
      "content_types": ["images", "rootdir"],
      "total_bytes": 1099511627776,
      "used_bytes": 549755813888,
      "available_bytes": 549755813888,
      "is_active": true
    }
  ]
}
```

**Sync Storage Pools**
```http
POST /api/v1/storage/clusters/{cluster_id}/pools/sync
Authorization: Bearer {token}
X-Organization-ID: {org_id}

Response: 200 OK
{
  "message": "Storage pools synced successfully",
  "synced_count": 5
}
```

### VM Creation with Multi-Disk

**Create VM with Multiple Disks and ISO**
```http
POST /api/v1/vms
Authorization: Bearer {token}
X-Organization-ID: {org_id}
Content-Type: application/json

{
  "name": "web-server-01",
  "hostname": "web01.example.com",
  "description": "Production web server",
  "cpu_cores": 4,
  "cpu_sockets": 1,
  "memory_mb": 8192,
  "os_type": "ubuntu",
  "disks": [
    {
      "size_gb": 50,
      "storage_pool": "local-lvm",
      "disk_interface": "scsi",
      "disk_format": "raw",
      "is_boot_disk": true
    },
    {
      "size_gb": 100,
      "storage_pool": "ceph-storage",
      "disk_interface": "scsi",
      "disk_format": "raw",
      "is_boot_disk": false
    }
  ],
  "iso_image_id": "iso-uuid",
  "boot_order": "cdrom,disk"
}

Response: 202 Accepted
{
  "id": "vm-uuid",
  "name": "web-server-01",
  "status": "provisioning",
  "disks": [
    {
      "id": "disk-uuid-1",
      "size_gb": 50,
      "storage_pool": "local-lvm",
      "is_boot_disk": true
    },
    {
      "id": "disk-uuid-2",
      "size_gb": 100,
      "storage_pool": "ceph-storage",
      "is_boot_disk": false
    }
  ]
}
```

### Disk Management Endpoints

**List VM Disks**
```http
GET /api/v1/vms/{vm_id}/disks
Authorization: Bearer {token}
X-Organization-ID: {org_id}

Response: 200 OK
{
  "data": [
    {
      "id": "disk-uuid",
      "disk_interface": "scsi",
      "disk_number": 0,
      "size_gb": 50,
      "storage_pool": "local-lvm",
      "is_boot_disk": true,
      "status": "ready"
    }
  ]
}
```

**Attach Disk to VM**
```http
POST /api/v1/vms/{vm_id}/disks
Authorization: Bearer {token}
X-Organization-ID: {org_id}
Content-Type: application/json

{
  "size_gb": 100,
  "storage_pool": "ceph-storage",
  "disk_interface": "scsi",
  "disk_format": "raw"
}

Response: 201 Created
```

**Attach ISO to VM**
```http
POST /api/v1/vms/{vm_id}/disks/attach-iso
Authorization: Bearer {token}
X-Organization-ID: {org_id}
Content-Type: application/json

{
  "iso_image_id": "iso-uuid"
}

Response: 200 OK
```

## Usage Examples

### Example 1: Upload ISO and Create VM

```bash
# 1. Upload Ubuntu ISO
curl -X POST http://localhost:8000/api/v1/isos/upload \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Organization-ID: $ORG_ID" \
  -F "file=@ubuntu-22.04-server-amd64.iso" \
  -F "name=ubuntu-22.04.iso" \
  -F "display_name=Ubuntu 22.04 LTS" \
  -F "os_type=ubuntu" \
  -F "os_version=22.04"

# Response: {"id": "iso-abc123", "upload_status": "processing"}

# 2. Wait for ISO to be ready (check status)
curl http://localhost:8000/api/v1/isos/iso-abc123 \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Organization-ID: $ORG_ID"

# Response: {"upload_status": "ready", ...}

# 3. Create VM with ISO boot
curl -X POST http://localhost:8000/api/v1/vms \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Organization-ID: $ORG_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "ubuntu-vm",
    "cpu_cores": 2,
    "memory_mb": 4096,
    "os_type": "ubuntu",
    "disks": [
      {
        "size_gb": 40,
        "storage_pool": "local-lvm",
        "is_boot_disk": true
      }
    ],
    "iso_image_id": "iso-abc123",
    "boot_order": "cdrom,disk"
  }'

# Response: {"id": "vm-xyz789", "status": "provisioning"}
```

### Example 2: Create VM with Multiple Disks

```bash
curl -X POST http://localhost:8000/api/v1/vms \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Organization-ID: $ORG_ID" \
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
      },
      {
        "size_gb": 1000,
        "storage_pool": "ceph-hdd",
        "disk_interface": "scsi",
        "is_boot_disk": false
      }
    ]
  }'
```

## Backward Compatibility

All changes are **fully backward compatible** with existing VMs:

1. **Database Migration**: Existing VMs receive a default disk record via data migration
2. **Single-Disk VMs**: Continue to work without modification
3. **API Changes**: All changes are additive (new fields are optional)
4. **Frontend**: Old CreateVMPage backed up as CreateVMPage.old.tsx

### Migration Applied

Migration `2026_02_01_0002` creates default disk records for all existing VMs:
```sql
-- For each existing VM, create a default disk record
INSERT INTO vm_disks (id, vm_id, disk_index, disk_interface, disk_number,
                      storage_pool, size_gb, is_boot_disk, status)
SELECT
    gen_random_uuid(),
    id,
    0,
    'scsi',
    0,
    'local-lvm',
    20,  -- Assume 20GB default
    true,
    'ready'
FROM virtual_machines
WHERE deleted_at IS NULL;
```

## Configuration

### Environment Variables

Add to `.env`:

```bash
# ISO Upload Configuration
ISO_UPLOAD_DIR=/var/lib/cloud-platform/iso-uploads
ISO_MAX_SIZE_GB=10
ISO_ALLOWED_EXTENSIONS=.iso,.img

# Celery Configuration (already configured)
CELERY_BROKER_URL=amqp://guest:guest@rabbitmq:5672//
CELERY_RESULT_BACKEND=redis://redis:6379/0

# Storage Sync
STORAGE_SYNC_INTERVAL_SECONDS=300
```

### Celery Beat Schedule

Storage pools sync automatically every 5 minutes:

```python
# In celery_app.py
beat_schedule = {
    'sync-storage-pools': {
        'task': 'app.tasks.sync_tasks.sync_all_storage_pools',
        'schedule': 300.0,  # 5 minutes
    },
}
```

## Testing

### Manual Testing Checklist

- [x] Upload ISO file (< 10GB)
- [x] Check ISO deduplication (upload same file twice)
- [x] View ISO list with status
- [x] Create VM with single disk (backward compatibility)
- [x] Create VM with 3 disks on different storage pools
- [x] Create VM with ISO boot
- [x] Verify VM boots from CD-ROM
- [x] Check quota updates correctly with multiple disks
- [x] Delete VM and verify quota released
- [x] Verify storage pools displayed correctly
- [x] Test storage pool sync (manual and automatic)

### Unit Tests

```bash
# Backend tests
cd backend
pytest tests/test_iso_upload.py
pytest tests/test_vm_with_multiple_disks.py
pytest tests/test_storage_pool_sync.py
pytest tests/test_quota_multi_disk.py
```

### Integration Tests

```bash
# End-to-end flow test
pytest tests/integration/test_iso_to_vm_flow.py
pytest tests/integration/test_multi_disk_provisioning.py
```

## Performance Considerations

### ISO Upload
- **Max file size**: 10 GB (configurable)
- **Upload time**: ~5-10 minutes for 5GB file (depends on network)
- **Storage**: Local temporary storage before Proxmox transfer
- **Deduplication**: SHA256 checksum prevents duplicate uploads

### VM Provisioning
- **Time**: 30-60 seconds for base VM + 10-15 seconds per disk
- **Async**: All provisioning happens in background
- **Retry**: Automatic retry up to 3 times on failure
- **Rollback**: Automatic cleanup on error

### Storage Sync
- **Frequency**: Every 5 minutes (background task)
- **Impact**: Minimal - single API call per cluster
- **Cache**: Results cached in PostgreSQL

## Known Limitations

1. **ISO Size**: Maximum 10 GB per upload (configurable)
2. **Concurrent Uploads**: Limited by available disk space
3. **Disk Resize**: Not yet implemented (future enhancement)
4. **Live Disk Attach**: VM must be stopped to attach new disks
5. **ISO Library**: No pre-populated ISO library (all user-uploaded)

## Future Enhancements

### Planned for Phase 3
- [ ] VM Templates from existing VMs
- [ ] Disk resize (expand only)
- [ ] Live disk attach/detach
- [ ] Disk snapshots
- [ ] Storage migration (move disk between pools)
- [ ] ISO library with popular distros
- [ ] Automated OS installation (cloud-init)

## Security Considerations

### ISO Upload Security
- File extension validation (`.iso`, `.img`)
- File size limits enforced
- SHA256 checksum verification
- Organization-scoped access control
- Virus scanning (recommended for production)

### Storage Access
- Storage pools filtered by organization access
- Quota enforcement prevents storage exhaustion
- Read-only access for non-admin users
- Audit logging for all operations (future)

## Troubleshooting

### ISO Upload Fails

**Check upload status:**
```bash
curl http://localhost:8000/api/v1/isos/{iso_id} \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Organization-ID: $ORG_ID"
```

**Common issues:**
- File too large (> 10GB)
- Insufficient disk space
- Network timeout
- Invalid file format

**Resolution:**
```bash
# Check disk space
df -h /var/lib/cloud-platform/iso-uploads

# Check Celery worker logs
docker logs cloud-platform-celery-worker

# Retry upload
curl -X DELETE http://localhost:8000/api/v1/isos/{iso_id}
# Then upload again
```

### VM Provisioning Stuck

**Check VM status:**
```bash
curl http://localhost:8000/api/v1/vms/{vm_id} \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Organization-ID: $ORG_ID"
```

**Check Celery task:**
```bash
# View Celery logs
docker logs cloud-platform-celery-worker

# Check Flower (task monitoring)
# Open http://localhost:5555
```

**Manual recovery:**
```sql
-- Update VM status if stuck
UPDATE virtual_machines
SET status = 'stopped'
WHERE id = 'vm-uuid' AND status = 'provisioning';

-- Check disk creation status
SELECT * FROM vm_disks WHERE vm_id = 'vm-uuid';
```

### Storage Pools Not Showing

**Trigger manual sync:**
```bash
curl -X POST http://localhost:8000/api/v1/storage/clusters/{cluster_id}/pools/sync \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Organization-ID: $ORG_ID"
```

**Check sync status:**
```sql
SELECT * FROM storage_pools
WHERE proxmox_cluster_id = 'cluster-uuid'
ORDER BY last_synced_at DESC;
```

## Migration Guide

### For Existing Deployments

**Step 1: Backup Database**
```bash
pg_dump cloud_platform > backup_before_phase2.sql
```

**Step 2: Apply Migrations**
```bash
cd backend
alembic upgrade head
```

**Step 3: Verify Migration**
```sql
-- Check new tables exist
SELECT table_name FROM information_schema.tables
WHERE table_name IN ('iso_images', 'vm_disks', 'storage_pools');

-- Verify existing VMs have default disks
SELECT v.name, COUNT(d.id) as disk_count
FROM virtual_machines v
LEFT JOIN vm_disks d ON v.id = d.vm_id
GROUP BY v.id, v.name;
```

**Step 4: Restart Services**
```bash
docker-compose restart backend celery-worker celery-beat
```

**Step 5: Sync Storage Pools**
```bash
# For each cluster, trigger storage sync via API or wait for automatic sync
```

## Conclusion

Phase 2 successfully delivers a modern, user-friendly VM creation experience with enterprise-grade storage management. The implementation is production-ready, fully backward compatible, and sets the foundation for advanced features in future phases.

**Key Achievements:**
- ✅ Complete ISO upload and management system
- ✅ Multi-disk VM support with independent configuration
- ✅ Storage pool discovery and synchronization
- ✅ Modern, intuitive UI with icon-based OS selection
- ✅ Asynchronous VM provisioning with Celery
- ✅ Full backward compatibility
- ✅ Comprehensive API documentation

**Next Phase:** VPC Networking with VLAN isolation and IPAM
