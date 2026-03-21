# Cloud Platform - Implementation Notes

## Known Issues

### 1. Issue with server name with space
[2026-02-01 07:44:32,566: INFO/ForkPoolWorker-2] Task app.tasks.vm_tasks.provision_vm_with_disks[942fe587-d6ed-4856-88d9-ec4c7255b610] retry: Retry in 60s: ResourceException("400 Bad Request: Parameter verification failed. - {'name': 'invalid format - value does not look like a valid DNS name\\n'}")

### 2. Set DNS on proxmox server
celery.exceptions.Retry: Retry in 60s: Exception("Download task failed: download failed: wget: unable to resolve host address 'download.rockylinux.org'")

### 3. ISO Attachment Duplicate Key Error - FIXED (2026-02-01)
**Issue:** When attaching an ISO to a VM, received error: `duplicate key value violates unique constraint "uq_vm_disk_interface"` with key `(vm_id, disk_interface, disk_number)=(xxx, ide, 2) already exists`.

**Root Cause:** The attach_iso_to_vm function was querying for existing CD-ROM using `is_cdrom == True` flag, but if a disk with `ide2` already existed without that flag set, the query wouldn't find it. The code would then try to create a new disk with `ide2`, violating the unique constraint on `(vm_id, disk_interface, disk_number)`.

**Fix:** Changed the query to look for any disk with `interface="ide"` and `disk_number=2`, regardless of the `is_cdrom` flag OR `deleted_at` status. When found, the existing disk is updated with the new ISO, the `is_cdrom` flag is set to true, and `deleted_at` is set to NULL to restore soft-deleted CD-ROMs.

**Code Change:**
```python
# Before: Only found disks with is_cdrom=True
result = await db.execute(
    select(VMDisk).where(
        VMDisk.vm_id == vm_id,
        VMDisk.is_cdrom == True,  # Too restrictive!
        VMDisk.deleted_at.is_(None)
    )
)

# After: Find any disk in the ide2 slot (including soft-deleted)
result = await db.execute(
    select(VMDisk).where(
        VMDisk.vm_id == vm_id,
        VMDisk.disk_interface == "ide",
        VMDisk.disk_number == 2
        # No deleted_at filter - find soft-deleted disks too
    )
)
existing_cdrom = result.scalar_one_or_none()
if existing_cdrom:
    existing_cdrom.iso_image_id = iso.id
    existing_cdrom.is_cdrom = True  # Ensure flag is set
    existing_cdrom.status = "creating"
    existing_cdrom.deleted_at = None  # Restore if soft-deleted
```

**Status:** RESOLVED

---

### 4. Console "Error 401: No ticket" - KNOWN LIMITATION (2026-02-01)
**Issue:** VM console shows "Error 401: No ticket" when trying to access directly from the portal.

**Root Cause:** The noVNC console requires two types of authentication:
1. **VNC ticket** - For the VNC websocket connection
2. **PVE Auth Cookie** - For the Proxmox web UI authentication (must be actual HTTP cookie)

The fundamental problem is **cross-domain cookie restrictions**:
- Proxmox's noVNC console page expects `PVEAuthCookie` to be set as an HTTP cookie in the browser
- Browser security (Same-Origin Policy) prevents JavaScript from setting cookies for different domains
- Our application runs on a different domain than Proxmox server
- Passing PVEAuthCookie as a URL parameter doesn't work - Proxmox requires it as an actual cookie

**Current Implementation:**
Backend generates a simple console URL that relies on the user's existing Proxmox browser session:
- URL format: `https://proxmox-host:8006/?console=kvm&novnc=1&vmid=VMID&vmname=NAME&node=NODE&resize=off&cmd=`
- No authentication tickets in URL (relies on browser's existing PVEAuthCookie)
- User must be logged into Proxmox web interface separately

**Workaround:**
Users must be logged into Proxmox web interface in a separate browser tab before using the console button. This ensures the PVEAuthCookie is set in the browser's cookies for the Proxmox domain.

**Steps:**
1. Open Proxmox web interface (https://proxmox-server:8006) in a new tab
2. Log in with credentials
3. Return to the cloud platform
4. Click "Console" button - it will now work

**Future Solution Options:**
1. **WebSocket Proxy** (Recommended): Implement full WebSocket proxy through our backend
   - Serve noVNC client from our domain
   - Proxy VNC websocket connections to Proxmox with backend authentication
   - Eliminates cross-domain issues entirely

2. **Backend Token Exchange**: Create a backend endpoint that proxies Proxmox login and sets session cookies

3. **Embedded Console**: Embed Proxmox console in iframe with backend proxy handling authentication

**Technical Details:**
- Console URL relies on browser's existing Proxmox session (PVEAuthCookie)
- Browser Same-Origin Policy prevents cross-domain cookie manipulation
- Simple URL format: `https://host:8006/?console=kvm&novnc=1&vmid=VMID&vmname=NAME&node=NODE&resize=off&cmd=`
- No authentication tickets embedded in URL
- User must maintain active Proxmox web session in browser

---

## Recently Implemented Features

### ISO Upload from URL (2026-02-01)

**Feature:** Users can now upload ISOs by providing a URL instead of uploading files directly.

**Implementation:**
- **Backend:**
  - Added `source_url`, `source_type`, and `download_status` fields to `ISOImage` model
  - Created `ISOUploadFromURL` schema for API request validation
  - Added POST `/api/v1/isos/upload-from-url` endpoint
  - Implemented `download_iso_from_url` Celery task that:
    - Uses Proxmox's native `download-url` API
    - Polls task status until completion (max 10 minutes)
    - Calculates checksum from URL for deduplication
  - Added `download_iso_from_url()` and `get_task_status()` methods to `ProxmoxService`

- **Frontend:**
  - Updated `ISOUploadPage.tsx` with tab-based UI
  - Two upload methods: "Upload from File" and "Upload from URL"
  - URL validation (http://, https://, ftp://)
  - Progress tracking during download

**Technical Details:**
- Proxmox downloads ISOs directly from URL to storage (no intermediate backend storage)
- Temporary checksum format: `pending-{iso_id}` (unique per upload)
- Final checksum: SHA256 hash of source URL
- Background processing with retry logic (3 attempts, 60s delay)

**Files Modified:**
- `/backend/app/models/iso_image.py` - Added URL source fields
- `/backend/app/schemas/iso_image.py` - Added `ISOUploadFromURL` schema
- `/backend/app/api/v1/endpoints/isos.py` - Added upload-from-url endpoint
- `/backend/app/services/proxmox_service.py` - Added download methods
- `/backend/app/tasks/iso_tasks.py` - Added `download_iso_from_url` task
- `/frontend/src/pages/ISOUploadPage.tsx` - Tab-based UI
- `/frontend/src/services/api.ts` - Added `uploadFromURL()` method

---

### VM Detail Page with Tabbed UI (2026-02-01)

**Feature:** VM detail page now uses a tabbed interface for better organization and navigation.

**Implementation:**
- **Three-Tab Layout:**
  1. **Monitor Tab**: Performance metrics and monitoring (placeholder for future implementation)
  2. **Detail Tab**: VM information, resource configuration, and Proxmox details
  3. **Storage Tab**: Disk and ISO management

- **Frontend:**
  - Updated `VMDetailPage.tsx` with tab navigation
  - Tab state management with active tab highlighting
  - Content organized by functional areas
  - Clean, intuitive navigation between different VM aspects

**User Experience:**
- Default opens on "Detail" tab showing VM information
- Click "Monitor" to view performance metrics
- Click "Storage" to manage disks and ISOs
- Tab selection persists within the session
- Active tab clearly indicated with colored border

**Technical Details:**
- Tab state managed with React useState hook
- Conditional rendering based on active tab
- Responsive design maintained across all tabs
- Clean separation of concerns

**Files Modified:**
- `/frontend/src/pages/VMDetailPage.tsx` - Added tabbed interface

---

### VM Disk and ISO Management (2026-02-01)

**Feature:** Users can now manage VM disks and ISO images directly from the VM detail page (Storage tab).

**Implementation:**
- **Backend:**
  - Added disk management endpoints at `/api/v1/vms/{vm_id}/disks`:
    - GET - List all disks attached to a VM
    - POST - Attach a new disk to VM
    - DELETE - Detach/remove a disk from VM
  - Added ISO management endpoint:
    - POST `/api/v1/vms/{vm_id}/disks/attach-iso` - Attach ISO as CD-ROM
  - Implemented `add_disk_to_vm()` and `mount_iso_to_vm()` methods in `ProxmoxService`
  - Quota enforcement for disk additions
  - Prevents deletion of boot disk

- **Frontend:**
  - Created `DiskManagement` component for VM detail page
  - Features:
    - View all attached disks (hard disks and CD-ROM)
    - Add new disk with configurable:
      - Size (GB)
      - Storage pool selection
      - Interface type (SCSI, SATA, VirtIO, IDE)
      - Disk format (RAW, QCOW2)
    - Attach ISO image as CD-ROM
    - Detach/remove disks (except boot disk)
    - Eject ISO from CD-ROM
  - Real-time status display for each disk
  - Boot disk clearly marked

**User Experience:**
- **Disk Management Section** on VM detail page shows:
  - Hard Disks: List with size, interface, storage pool, and status
  - CD-ROM: Shows mounted ISO or empty state
  - "Add Disk" button opens inline form
  - "Attach ISO" button opens ISO selection form
  - Detach/Eject buttons for removable disks and ISOs

**Technical Details:**
- Disk interface options: SCSI (default), SATA, VirtIO, IDE
- Disk format options: RAW (default), QCOW2
- Storage pool fetched from Proxmox cluster
- ISO images filtered to show only "ready" status
- Quota checked before adding new disks
- Background disk attachment via Proxmox API

**Files Created:**
- `/backend/app/api/v1/endpoints/disks.py` - Disk management endpoints
- `/frontend/src/components/vm/DiskManagement.tsx` - Disk management UI

**Files Modified:**
- `/backend/app/services/proxmox_service.py` - Added disk/ISO methods
- `/backend/app/api/v1/router.py` - Registered disk router
- `/frontend/src/pages/VMDetailPage.tsx` - Integrated DiskManagement component
- `/frontend/src/services/api.ts` - Added disksApi methods

**Security:**
- Disk operations require VM_UPDATE permission
- Organization-scoped access (users can only manage their org's VM disks)
- Boot disk protection (cannot be detached)
- Quota validation before disk addition

---

### VM Console Access (2026-02-01)

**Feature:** Users can now access VM console directly from the web interface using noVNC.

**Implementation:**
- **Backend:**
  - Added GET `/api/v1/vms/{vm_id}/console` endpoint
  - Implemented `get_console_url()` method in `ProxmoxService` that:
    - Creates VNC proxy ticket via Proxmox API
    - Builds noVNC console URL with ticket embedded
    - Returns ready-to-use console URL
  - Permission-based access (requires `VM_READ` permission)

- **Frontend:**
  - Added "Console" button to VM detail page (for running VMs)
  - Added "Console" button to VM list page (for running VMs)
  - Console opens in new popup window (1024x768)
  - Window features: resizable, scrollable, no menubar/toolbar
  - Named window target `'vmConsole'` reuses same window

**User Experience:**
- **VM List:** Console button appears between Stop and View buttons for running VMs
- **VM Detail:** Console button appears between Restart and Stop buttons for running VMs
- Click opens noVNC console in new popup window
- Window can be resized as needed
- Multiple clicks reuse the same window

**Technical Details:**
- Uses Proxmox's noVNC web console with VNC proxy tickets
- Ticket-based authentication (secure, time-limited)
- Window opens with: `width=1024,height=768,menubar=no,toolbar=no,location=no,status=no,resizable=yes,scrollbars=yes`
- Only available for VMs in "running" state

**Files Modified:**
- `/backend/app/services/proxmox_service.py` - Added `get_console_url()` method
- `/backend/app/api/v1/endpoints/vms.py` - Added console endpoint
- `/frontend/src/services/api.ts` - Added `getConsole()` method
- `/frontend/src/pages/VMDetailPage.tsx` - Added console button and mutation
- `/frontend/src/pages/VMsPage.tsx` - Added console button and mutation

**Security:**
- Console access requires VM_READ permission
- Organization-scoped access (users can only access their org's VMs)
- VNC tickets are time-limited and generated per session
- Secure WebSocket connection (wss://) for console data

---

## Usage Examples

### ISO Upload from URL
```bash
# API Request
curl -X POST http://localhost:8000/api/v1/isos/upload-from-url \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Organization-ID: $ORG_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://releases.ubuntu.com/22.04/ubuntu-22.04.3-live-server-amd64.iso",
    "display_name": "Ubuntu 22.04 LTS Server",
    "description": "Ubuntu 22.04.3 LTS",
    "os_type": "linux",
    "os_version": "22.04",
    "architecture": "x86_64",
    "is_public": false
  }'

# Response
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "upload_url": null,
  "message": "ISO download from URL initiated. Processing in background."
}
```

### VM Disk Management
```bash
# List VM Disks
curl -X GET http://localhost:8000/api/v1/vms/{vm_id}/disks \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Organization-ID: $ORG_ID"

# Response
{
  "data": [
    {
      "id": "disk-uuid",
      "disk_interface": "scsi",
      "disk_number": 0,
      "storage_pool": "local-lvm",
      "size_gb": 40,
      "is_boot_disk": true,
      "is_cdrom": false,
      "status": "ready"
    }
  ],
  "total": 1
}

# Attach New Disk
curl -X POST http://localhost:8000/api/v1/vms/{vm_id}/disks \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Organization-ID: $ORG_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "size_gb": 100,
    "storage_pool": "local-lvm",
    "disk_interface": "scsi",
    "disk_format": "raw"
  }'

# Attach ISO as CD-ROM
curl -X POST http://localhost:8000/api/v1/vms/{vm_id}/disks/attach-iso \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Organization-ID: $ORG_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "iso_image_id": "iso-uuid"
  }'

# Detach Disk
curl -X DELETE http://localhost:8000/api/v1/vms/{vm_id}/disks/{disk_id} \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Organization-ID: $ORG_ID"
```

### VM Console Access
```bash
# API Request
curl -X GET http://localhost:8000/api/v1/vms/{vm_id}/console \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Organization-ID: $ORG_ID"

# Response
{
  "console_url": "https://proxmox.example.com:8006/?console=kvm&novnc=1&vmid=100&vmname=my-vm&node=pve&resize=off&cmd=",
  "message": "Console URL generated successfully",
  "workaround_note": "If you see 'Error 401: No ticket', please log into Proxmox web interface first: https://proxmox.example.com:8006"
}
```

**Important Workaround:**
Due to browser security restrictions (cross-domain cookies), you must:
1. Open Proxmox web interface in a separate tab: `https://proxmox-server:8006`
2. Log in with your Proxmox credentials
3. Keep that tab open (or at least logged in)
4. Then click the "Console" button in the cloud platform

This ensures the PVEAuthCookie is set in your browser for the Proxmox domain.

---

## Testing

### ISO Upload from URL
1. Navigate to ISO upload page
2. Click "Upload from URL" tab
3. Enter ISO URL (e.g., Ubuntu release URL)
4. Fill in display name and metadata
5. Click "Download ISO from URL"
6. Check ISO list - status should show "processing" then "ready"

### VM Detail Page Tabs

**Testing Steps:**

1. **Tab Navigation:**
   - Navigate to any VM detail page
   - Should see three tabs: Monitor, Detail, Storage
   - Detail tab should be active by default
   - Click each tab and verify content switches
   - Active tab should have blue underline

2. **Detail Tab:**
   - Should show VM Information section
   - Should show Resource Configuration section
   - Should show Proxmox Details section
   - All information displayed correctly

3. **Monitor Tab:**
   - Should show Performance Metrics placeholder
   - Placeholder indicates "coming soon"

4. **Storage Tab:**
   - Should show Disks & Storage section
   - Same functionality as before, just in separate tab

### VM Disk Management

**Testing Steps:**

1. **View VM Disks:**
   - Navigate to a VM detail page
   - Click on "Storage" tab
   - Should see "Disks & Storage" section
   - Should see list of attached disks
   - Boot disk should be marked with "Boot" badge

2. **Add New Disk:**
   - Click "Add Disk" button
   - Form appears with fields:
     - Size (GB)
     - Storage Pool dropdown
     - Interface (SCSI/SATA/VirtIO/IDE)
     - Format (RAW/QCOW2)
   - Fill in details and click "Attach Disk"
   - Disk appears in list with "creating" then "ready" status
   - Verify disk added in Proxmox

3. **Attach ISO:**
   - Click "Attach ISO" button
   - Select ISO from dropdown (only "ready" ISOs shown)
   - Click "Attach ISO"
   - ISO appears in CD-ROM section
   - Verify ISO mounted in Proxmox

4. **Detach Disk:**
   - Click "Detach" button on a non-boot disk
   - Confirm deletion
   - Disk removed from list
   - Quota updated

5. **Eject ISO:**
   - Click "Eject" button on CD-ROM
   - Confirm deletion
   - CD-ROM shows "No ISO attached"

6. **Error Handling:**
   - Try to detach boot disk → Should show error
   - Try to add disk exceeding quota → Should show quota error
   - Try to attach non-ready ISO → Should show error

### VM Console Access

**Prerequisites:**
1. Open Proxmox web interface in a separate browser tab: `https://proxmox-server:8006`
2. Log in with your Proxmox credentials
3. Keep that tab open (required for authentication cookies)

**Testing Steps:**

1. **From VM List:**
   - Navigate to VMs page
   - Find a running VM
   - Click "Console" button
   - Alert shows workaround note (if not logged into Proxmox)
   - Console window opens

2. **From VM Detail:**
   - Navigate to a running VM's detail page
   - Click "Console" button in header
   - Alert shows workaround note (if not logged into Proxmox)
   - Console window opens

3. **Verify:**
   - Console shows VM display (not "Error 401: No ticket")
   - Keyboard input works
   - Mouse tracking works
   - Window is resizable

4. **Troubleshooting:**
   - If you see "Error 401: No ticket":
     - Make sure you're logged into Proxmox web interface in another tab
     - Refresh the Proxmox login if session expired
     - Try clicking Console button again