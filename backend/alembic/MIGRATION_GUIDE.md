# Multi-Tenancy Database Migration Guide

This guide explains how to run the database migrations for the multi-tenancy and quota management feature.

## Overview

Three migrations have been created to implement multi-tenancy:

1. **a1b2c3d4e5f6** - Add multi-tenancy tables
2. **b2c3d4e5f6g7** - Migrate existing data to default organization
3. **c3d4e5f6g7h8** - Make VM organization_id required

## Migration Order

**IMPORTANT:** These migrations must be run in order. Do not skip any migration.

### Migration 1: Add Multi-Tenancy Tables
Creates:
- `organization_members` table (user-organization membership with roles)
- `resource_quotas` table (per-organization quota limits and usage)
- Adds `organization_id` and `is_shared` columns to `proxmox_clusters`

### Migration 2: Migrate Existing Data
- Creates "Default Organization"
- Assigns all existing VMs to default organization
- Creates organization memberships for all VM owners (as admins)
- Marks all existing Proxmox clusters as shared
- Creates default quotas with generous limits:
  - CPU: 100 cores
  - Memory: 512 GB
  - Storage: 5000 GB
  - VMs: 50
  - Clusters: 5
- Calculates initial quota usage from existing VMs

### Migration 3: Make Organization Required
- Makes `virtual_machines.organization_id` NOT NULL
- Ensures all VMs must belong to an organization

## Running Migrations

### Prerequisites

1. Backup your database:
```bash
mysqldump -u root -p cloud_platform > backup_$(date +%Y%m%d_%H%M%S).sql
```

2. Ensure the backend application is stopped or in maintenance mode

### Execute Migrations

From the backend directory:

```bash
cd /Users/sangtran/Documents/Learn\ AI/cloud-platform/backend

# Review pending migrations
alembic current
alembic history

# Run all pending migrations
alembic upgrade head

# Or run migrations one at a time
alembic upgrade a1b2c3d4e5f6  # Create tables
alembic upgrade b2c3d4e5f6g7  # Migrate data
alembic upgrade c3d4e5f6g7h8  # Make org required
```

### Verification

After running migrations, verify the results:

```sql
-- Check tables were created
SHOW TABLES LIKE 'organization_members';
SHOW TABLES LIKE 'resource_quotas';

-- Verify default organization was created
SELECT * FROM organizations WHERE slug = 'default';

-- Check all VMs have organization_id
SELECT COUNT(*) FROM virtual_machines WHERE organization_id IS NULL;
-- Should return 0

-- Verify organization memberships were created
SELECT COUNT(*) FROM organization_members;
-- Should match number of distinct VM owners

-- Check quota records were created
SELECT * FROM resource_quotas;
-- Should show 5 quota records (cpu_cores, memory_gb, storage_gb, vm_count, cluster_count)

-- Verify quota usage was calculated
SELECT resource_type, used_value, limit_value
FROM resource_quotas
WHERE organization_id = (SELECT id FROM organizations WHERE slug = 'default');
```

## Rollback

If you need to rollback the migrations:

```bash
# Rollback all three migrations
alembic downgrade dff514f1022e

# Or rollback one at a time (in reverse order)
alembic downgrade b2c3d4e5f6g7  # Remove NOT NULL constraint
alembic downgrade a1b2c3d4e5f6  # Remove migrated data
alembic downgrade dff514f1022e  # Drop tables
```

**WARNING:** Rolling back migration 2 (migrate_existing_data) will:
- Remove all organization memberships
- Delete all quota records
- Delete the default organization
- Set all VM organization_ids to NULL

## Troubleshooting

### Error: "Cannot make organization_id NOT NULL: X VMs still have NULL organization_id"

This means migration 2 (data migration) didn't run successfully or VMs were created after migration 2.

**Solution:**
1. Run this SQL to assign unassigned VMs to default org:
```sql
UPDATE virtual_machines
SET organization_id = (SELECT id FROM organizations WHERE slug = 'default')
WHERE organization_id IS NULL;
```

2. Re-run migration 3:
```bash
alembic upgrade c3d4e5f6g7h8
```

### Error: "Duplicate entry for key 'uq_user_org'"

This means organization memberships already exist.

**Solution:**
- This is expected if you're re-running migration 2
- The migration checks for existing memberships and skips them
- Verify memberships: `SELECT * FROM organization_members;`

### Error: "Foreign key constraint fails"

This likely means the organizations table doesn't have the default organization.

**Solution:**
1. Check if default org exists:
```sql
SELECT * FROM organizations WHERE slug = 'default';
```

2. If not, manually create it:
```sql
INSERT INTO organizations (id, name, slug, description, created_at, updated_at)
VALUES (UUID(), 'Default Organization', 'default', 'Default organization for migrated resources', NOW(), NOW());
```

3. Re-run migration 2

## Post-Migration Steps

1. **Restart the backend application** with the new code that includes:
   - Organization context dependencies
   - RBAC permission checks
   - Quota enforcement

2. **Update the frontend** to:
   - Send `X-Organization-ID` header with API requests
   - Display organization switcher
   - Show quota usage

3. **Test the system**:
   - Login as an existing user
   - Verify you can see your VMs
   - Try creating a new VM
   - Check quota usage updates

## Notes

- All existing users who owned VMs are automatically made admins of the default organization
- New users will need to be invited to organizations by admins
- Superadmins can access all organizations without membership
- All existing Proxmox clusters are marked as shared (accessible by all organizations)
- Default quotas are generous to avoid disrupting existing usage
- Quota usage is calculated from actual VM resources in the database
