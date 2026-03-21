-- Update existing clusters to be shared across all organizations
UPDATE proxmox_clusters
SET is_shared = true,
    organization_id = NULL
WHERE deleted_at IS NULL;

-- Verify the change
SELECT id, name, is_shared, organization_id, is_active
FROM proxmox_clusters
WHERE deleted_at IS NULL;
