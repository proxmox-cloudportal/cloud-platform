-- Cleanup script for partial Phase 3 migration
-- Run this to remove partially created tables and start fresh

BEGIN;

-- Drop tables in reverse order (respecting foreign keys)
DROP TABLE IF EXISTS vm_network_interfaces CASCADE;
DROP TABLE IF EXISTS network_ip_allocations CASCADE;
DROP TABLE IF EXISTS network_ip_pools CASCADE;
DROP TABLE IF EXISTS vlan_pool CASCADE;
DROP TABLE IF EXISTS vpc_networks CASCADE;

-- Remove any columns added to proxmox_clusters (if they exist)
ALTER TABLE proxmox_clusters DROP COLUMN IF EXISTS default_bridge;
ALTER TABLE proxmox_clusters DROP COLUMN IF EXISTS supported_bridges;

COMMIT;

-- Now you can run: alembic upgrade head
