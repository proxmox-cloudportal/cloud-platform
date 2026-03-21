# Database Schema Design

## Overview

This document defines the PostgreSQL database schema for the cloud management platform. The schema is designed for multi-tenancy, scalability, and data integrity.

## Design Principles

- **Multi-tenancy**: All resources are scoped to organizations
- **Audit Trail**: Track all changes with timestamps and user attribution
- **Soft Deletes**: Use `deleted_at` for logical deletion
- **UUID Primary Keys**: For distributed systems and security
- **Denormalization**: Strategic denormalization for performance
- **Partitioning**: Time-based partitioning for audit logs and metrics

## Schema Overview

### Core Tables
- users
- organizations
- organization_members
- roles
- permissions
- role_permissions
- user_roles

### Resource Tables
- virtual_machines
- vm_templates
- vm_snapshots
- vm_disks

### Proxmox Integration
- proxmox_clusters
- proxmox_nodes
- proxmox_pools

### Networking
- networks
- ip_addresses
- firewall_rules
- load_balancers

### Storage
- storage_pools
- storage_quotas

### Metering & Quotas
- resource_quotas
- usage_records
- usage_summaries

### Audit & Logs
- audit_logs
- api_keys

## Detailed Schema

### 1. Users & Authentication

#### users
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    is_active BOOLEAN DEFAULT true,
    is_superadmin BOOLEAN DEFAULT false,
    email_verified BOOLEAN DEFAULT false,
    email_verification_token VARCHAR(255),
    password_reset_token VARCHAR(255),
    password_reset_expires TIMESTAMP,
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    deleted_at TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email) WHERE deleted_at IS NULL;
CREATE INDEX idx_users_username ON users(username) WHERE deleted_at IS NULL;
CREATE INDEX idx_users_active ON users(is_active) WHERE deleted_at IS NULL;
```

#### user_sessions
```sql
CREATE TABLE user_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL,
    refresh_token_hash VARCHAR(255),
    ip_address INET,
    user_agent TEXT,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    revoked_at TIMESTAMP
);

CREATE INDEX idx_sessions_user ON user_sessions(user_id);
CREATE INDEX idx_sessions_token ON user_sessions(token_hash);
CREATE INDEX idx_sessions_expires ON user_sessions(expires_at);
```

#### api_keys
```sql
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    key_hash VARCHAR(255) NOT NULL,
    key_prefix VARCHAR(20) NOT NULL, -- First few chars for identification
    scopes JSONB DEFAULT '[]', -- Array of permission scopes
    expires_at TIMESTAMP,
    last_used_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    revoked_at TIMESTAMP
);

CREATE INDEX idx_apikeys_user ON api_keys(user_id);
CREATE INDEX idx_apikeys_org ON api_keys(organization_id);
CREATE INDEX idx_apikeys_prefix ON api_keys(key_prefix);
```

### 2. Organizations & Multi-tenancy

#### organizations
```sql
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    settings JSONB DEFAULT '{}', -- Org-specific settings
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    deleted_at TIMESTAMP
);

CREATE INDEX idx_orgs_slug ON organizations(slug) WHERE deleted_at IS NULL;
CREATE INDEX idx_orgs_active ON organizations(is_active) WHERE deleted_at IS NULL;
```

#### organization_members
```sql
CREATE TABLE organization_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    is_owner BOOLEAN DEFAULT false,
    joined_at TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW(),
    removed_at TIMESTAMP,

    UNIQUE(organization_id, user_id)
);

CREATE INDEX idx_org_members_org ON organization_members(organization_id);
CREATE INDEX idx_org_members_user ON organization_members(user_id);
```

### 3. RBAC (Role-Based Access Control)

#### roles
```sql
CREATE TABLE roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    is_system BOOLEAN DEFAULT false, -- System roles vs custom roles
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(organization_id, name)
);

-- System roles: superadmin, org_admin, org_member, org_billing, org_viewer
CREATE INDEX idx_roles_org ON roles(organization_id);
```

#### permissions
```sql
CREATE TABLE permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resource VARCHAR(100) NOT NULL, -- vm, network, storage, user, org, etc.
    action VARCHAR(50) NOT NULL, -- create, read, update, delete, start, stop, etc.
    description TEXT,

    UNIQUE(resource, action)
);

-- Example permissions:
-- vm:create, vm:read, vm:update, vm:delete, vm:start, vm:stop
-- network:create, network:read, network:update, network:delete
-- storage:read, storage:allocate
-- org:read, org:update, org:members
```

#### role_permissions
```sql
CREATE TABLE role_permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id UUID NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(role_id, permission_id)
);

CREATE INDEX idx_role_perms_role ON role_permissions(role_id);
```

#### user_roles
```sql
CREATE TABLE user_roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    granted_by UUID REFERENCES users(id),
    granted_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,

    UNIQUE(user_id, role_id, organization_id)
);

CREATE INDEX idx_user_roles_user ON user_roles(user_id);
CREATE INDEX idx_user_roles_org ON user_roles(organization_id);
```

### 4. Proxmox Integration

#### proxmox_clusters
```sql
CREATE TABLE proxmox_clusters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    datacenter VARCHAR(100), -- Physical location
    region VARCHAR(50), -- us-east, eu-west, etc.
    api_url VARCHAR(255) NOT NULL,
    api_username VARCHAR(100) NOT NULL,
    api_password_encrypted TEXT NOT NULL, -- Or use Vault
    api_token_id VARCHAR(255),
    api_token_secret_encrypted TEXT,
    is_active BOOLEAN DEFAULT true,
    total_cpu_cores INTEGER,
    total_memory_mb BIGINT,
    total_storage_gb BIGINT,
    load_score INTEGER DEFAULT 0, -- For load balancing
    last_sync TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_clusters_active ON proxmox_clusters(is_active);
CREATE INDEX idx_clusters_region ON proxmox_clusters(region);
```

#### proxmox_nodes
```sql
CREATE TABLE proxmox_nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cluster_id UUID NOT NULL REFERENCES proxmox_clusters(id) ON DELETE CASCADE,
    node_name VARCHAR(255) NOT NULL,
    ip_address INET,
    status VARCHAR(50), -- online, offline, maintenance
    cpu_cores INTEGER,
    memory_mb BIGINT,
    cpu_usage_percent DECIMAL(5,2),
    memory_usage_percent DECIMAL(5,2),
    last_seen TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(cluster_id, node_name)
);

CREATE INDEX idx_nodes_cluster ON proxmox_nodes(cluster_id);
CREATE INDEX idx_nodes_status ON proxmox_nodes(status);
```

#### proxmox_pools
```sql
CREATE TABLE proxmox_pools (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cluster_id UUID NOT NULL REFERENCES proxmox_clusters(id) ON DELETE CASCADE,
    organization_id UUID REFERENCES organizations(id) ON DELETE SET NULL,
    pool_id VARCHAR(100) NOT NULL,
    pool_name VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(cluster_id, pool_id)
);

CREATE INDEX idx_pools_cluster ON proxmox_pools(cluster_id);
CREATE INDEX idx_pools_org ON proxmox_pools(organization_id);
```

### 5. Virtual Machines

#### virtual_machines
```sql
CREATE TABLE virtual_machines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    owner_id UUID NOT NULL REFERENCES users(id),

    -- VM Identification
    name VARCHAR(255) NOT NULL,
    hostname VARCHAR(255),
    description TEXT,
    tags JSONB DEFAULT '[]',

    -- Proxmox Details
    proxmox_cluster_id UUID NOT NULL REFERENCES proxmox_clusters(id),
    proxmox_node_id UUID REFERENCES proxmox_nodes(id),
    proxmox_vmid INTEGER NOT NULL,
    proxmox_pool_id VARCHAR(100),

    -- VM Configuration
    template_id UUID REFERENCES vm_templates(id),
    os_type VARCHAR(50), -- linux, windows, other

    -- Resources
    cpu_cores INTEGER NOT NULL,
    cpu_sockets INTEGER DEFAULT 1,
    memory_mb INTEGER NOT NULL,

    -- Status
    status VARCHAR(50) NOT NULL, -- running, stopped, paused, error, provisioning
    power_state VARCHAR(50), -- on, off

    -- Networking
    primary_ip_address INET,
    mac_addresses JSONB DEFAULT '[]',

    -- Dates
    provisioned_at TIMESTAMP,
    started_at TIMESTAMP,
    stopped_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    deleted_at TIMESTAMP,

    UNIQUE(proxmox_cluster_id, proxmox_vmid)
);

CREATE INDEX idx_vms_org ON virtual_machines(organization_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_vms_owner ON virtual_machines(owner_id);
CREATE INDEX idx_vms_cluster ON virtual_machines(proxmox_cluster_id);
CREATE INDEX idx_vms_status ON virtual_machines(status);
CREATE INDEX idx_vms_name ON virtual_machines(name) WHERE deleted_at IS NULL;
```

#### vm_templates
```sql
CREATE TABLE vm_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    os_type VARCHAR(50),
    os_version VARCHAR(100),

    -- Template source
    proxmox_cluster_id UUID REFERENCES proxmox_clusters(id),
    proxmox_template_id INTEGER,

    -- Default specs
    default_cpu_cores INTEGER DEFAULT 2,
    default_memory_mb INTEGER DEFAULT 2048,
    default_disk_gb INTEGER DEFAULT 20,

    -- Visibility
    is_public BOOLEAN DEFAULT false,
    organization_id UUID REFERENCES organizations(id), -- NULL = global template

    -- Template metadata
    icon_url VARCHAR(500),
    category VARCHAR(100), -- web, database, development, etc.
    min_cpu INTEGER DEFAULT 1,
    min_memory_mb INTEGER DEFAULT 512,

    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_templates_org ON vm_templates(organization_id);
CREATE INDEX idx_templates_public ON vm_templates(is_public);
CREATE INDEX idx_templates_category ON vm_templates(category);
```

#### vm_snapshots
```sql
CREATE TABLE vm_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vm_id UUID NOT NULL REFERENCES virtual_machines(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,

    proxmox_snapshot_name VARCHAR(255) NOT NULL,

    size_mb BIGINT,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    deleted_at TIMESTAMP
);

CREATE INDEX idx_snapshots_vm ON vm_snapshots(vm_id);
CREATE INDEX idx_snapshots_created ON vm_snapshots(created_at);
```

#### vm_disks
```sql
CREATE TABLE vm_disks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vm_id UUID NOT NULL REFERENCES virtual_machines(id) ON DELETE CASCADE,

    disk_name VARCHAR(100), -- scsi0, scsi1, etc.
    storage_pool VARCHAR(100),
    size_gb INTEGER NOT NULL,
    disk_type VARCHAR(50), -- disk, cdrom

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_disks_vm ON vm_disks(vm_id);
```

### 6. Networking

#### networks
```sql
CREATE TABLE networks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    proxmox_cluster_id UUID REFERENCES proxmox_clusters(id),

    name VARCHAR(255) NOT NULL,
    description TEXT,

    -- Network configuration
    vlan_id INTEGER,
    cidr VARCHAR(50), -- e.g., 10.0.1.0/24
    gateway INET,
    dns_servers JSONB DEFAULT '[]',

    -- Network type
    network_type VARCHAR(50), -- private, public, management

    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_networks_org ON networks(organization_id);
CREATE INDEX idx_networks_cluster ON networks(proxmox_cluster_id);
CREATE INDEX idx_networks_vlan ON networks(vlan_id);
```

#### ip_addresses
```sql
CREATE TABLE ip_addresses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    network_id UUID NOT NULL REFERENCES networks(id) ON DELETE CASCADE,

    ip_address INET NOT NULL,
    vm_id UUID REFERENCES virtual_machines(id) ON DELETE SET NULL,

    status VARCHAR(50), -- available, allocated, reserved

    allocated_at TIMESTAMP,
    released_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(network_id, ip_address)
);

CREATE INDEX idx_ips_network ON ip_addresses(network_id);
CREATE INDEX idx_ips_vm ON ip_addresses(vm_id);
CREATE INDEX idx_ips_status ON ip_addresses(status);
```

#### firewall_rules
```sql
CREATE TABLE firewall_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    vm_id UUID REFERENCES virtual_machines(id) ON DELETE CASCADE,
    network_id UUID REFERENCES networks(id) ON DELETE CASCADE,

    rule_name VARCHAR(255),
    rule_order INTEGER,

    -- Rule configuration
    action VARCHAR(20) NOT NULL, -- accept, drop, reject
    direction VARCHAR(20) NOT NULL, -- in, out
    protocol VARCHAR(20), -- tcp, udp, icmp, all
    source_ip INET,
    source_port INTEGER,
    dest_ip INET,
    dest_port INTEGER,

    is_enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_firewall_org ON firewall_rules(organization_id);
CREATE INDEX idx_firewall_vm ON firewall_rules(vm_id);
CREATE INDEX idx_firewall_network ON firewall_rules(network_id);
```

#### load_balancers
```sql
CREATE TABLE load_balancers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    name VARCHAR(255) NOT NULL,
    description TEXT,

    frontend_ip INET,
    frontend_port INTEGER,
    protocol VARCHAR(20), -- http, https, tcp

    algorithm VARCHAR(50), -- roundrobin, leastconn, source

    health_check_enabled BOOLEAN DEFAULT true,
    health_check_path VARCHAR(500),
    health_check_interval INTEGER DEFAULT 30,

    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_lb_org ON load_balancers(organization_id);
```

#### load_balancer_backends
```sql
CREATE TABLE load_balancer_backends (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    load_balancer_id UUID NOT NULL REFERENCES load_balancers(id) ON DELETE CASCADE,
    vm_id UUID NOT NULL REFERENCES virtual_machines(id) ON DELETE CASCADE,

    backend_ip INET NOT NULL,
    backend_port INTEGER NOT NULL,
    weight INTEGER DEFAULT 1,
    is_enabled BOOLEAN DEFAULT true,

    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_lb_backends_lb ON load_balancer_backends(load_balancer_id);
CREATE INDEX idx_lb_backends_vm ON load_balancer_backends(vm_id);
```

### 7. Storage

#### storage_pools
```sql
CREATE TABLE storage_pools (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proxmox_cluster_id UUID NOT NULL REFERENCES proxmox_clusters(id) ON DELETE CASCADE,

    pool_name VARCHAR(255) NOT NULL,
    storage_type VARCHAR(50), -- dir, lvm, ceph, nfs, etc.

    total_gb BIGINT,
    allocated_gb BIGINT DEFAULT 0,
    available_gb BIGINT,

    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(proxmox_cluster_id, pool_name)
);

CREATE INDEX idx_storage_cluster ON storage_pools(proxmox_cluster_id);
```

### 8. Resource Quotas

#### resource_quotas
```sql
CREATE TABLE resource_quotas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Compute quotas
    max_vcpu INTEGER,
    max_memory_mb BIGINT,
    max_vms INTEGER,

    -- Storage quotas
    max_storage_gb BIGINT,
    max_snapshots INTEGER,

    -- Network quotas
    max_networks INTEGER,
    max_ips INTEGER,
    max_load_balancers INTEGER,

    -- Enforced or soft limit
    is_enforced BOOLEAN DEFAULT true,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(organization_id)
);

CREATE INDEX idx_quotas_org ON resource_quotas(organization_id);
```

### 9. Usage Tracking & Metering

#### usage_records
```sql
CREATE TABLE usage_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    vm_id UUID REFERENCES virtual_machines(id) ON DELETE SET NULL,

    -- Resource usage
    resource_type VARCHAR(50) NOT NULL, -- cpu, memory, storage, network_egress
    quantity DECIMAL(15, 4) NOT NULL,
    unit VARCHAR(20) NOT NULL, -- hours, gb, gb_hours

    -- Timestamp
    recorded_at TIMESTAMP NOT NULL DEFAULT NOW(),
    period_start TIMESTAMP NOT NULL,
    period_end TIMESTAMP NOT NULL,

    -- Metadata
    metadata JSONB DEFAULT '{}'
) PARTITION BY RANGE (recorded_at);

-- Create partitions by month
CREATE TABLE usage_records_2026_01 PARTITION OF usage_records
    FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');

CREATE INDEX idx_usage_org ON usage_records(organization_id, recorded_at);
CREATE INDEX idx_usage_vm ON usage_records(vm_id);
CREATE INDEX idx_usage_period ON usage_records(period_start, period_end);
```

#### usage_summaries
```sql
CREATE TABLE usage_summaries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    summary_period VARCHAR(20) NOT NULL, -- daily, monthly
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,

    -- Aggregated usage
    total_vcpu_hours DECIMAL(15, 2),
    total_memory_gb_hours DECIMAL(15, 2),
    total_storage_gb_hours DECIMAL(15, 2),
    total_network_gb DECIMAL(15, 2),

    -- VM counts
    vm_count_avg INTEGER,
    vm_count_max INTEGER,

    created_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(organization_id, summary_period, period_start)
);

CREATE INDEX idx_usage_summary_org ON usage_summaries(organization_id);
CREATE INDEX idx_usage_summary_period ON usage_summaries(period_start);
```

### 10. Audit Logs

#### audit_logs
```sql
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id) ON DELETE SET NULL,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,

    -- Action details
    action VARCHAR(100) NOT NULL, -- vm.create, vm.delete, user.login, etc.
    resource_type VARCHAR(50), -- vm, network, user, org, etc.
    resource_id UUID,

    -- Request details
    ip_address INET,
    user_agent TEXT,

    -- Change tracking
    old_values JSONB,
    new_values JSONB,

    -- Result
    status VARCHAR(20), -- success, failure
    error_message TEXT,

    created_at TIMESTAMP DEFAULT NOW()
) PARTITION BY RANGE (created_at);

-- Create partitions by month
CREATE TABLE audit_logs_2026_01 PARTITION OF audit_logs
    FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');

CREATE INDEX idx_audit_org ON audit_logs(organization_id, created_at);
CREATE INDEX idx_audit_user ON audit_logs(user_id, created_at);
CREATE INDEX idx_audit_action ON audit_logs(action, created_at);
CREATE INDEX idx_audit_resource ON audit_logs(resource_type, resource_id);
```

## Database Relationships Diagram

```
users ──────┬──── user_sessions
            ├──── api_keys
            ├──── organization_members ──── organizations
            ├──── user_roles ──── roles ──── role_permissions ──── permissions
            └──── virtual_machines

organizations ──┬──── organization_members
                ├──── resource_quotas
                ├──── usage_records
                ├──── usage_summaries
                ├──── virtual_machines
                ├──── networks
                └──── audit_logs

proxmox_clusters ──┬──── proxmox_nodes
                   ├──── proxmox_pools
                   ├──── virtual_machines
                   ├──── networks
                   └──── storage_pools

virtual_machines ──┬──── vm_snapshots
                   ├──── vm_disks
                   ├──── ip_addresses
                   └──── firewall_rules

networks ──┬──── ip_addresses
           └──── firewall_rules

load_balancers ──── load_balancer_backends ──── virtual_machines
```

## Migration Strategy

### Initial Setup
1. Create database and enable required extensions
2. Create tables in dependency order
3. Seed system data (permissions, default roles)
4. Create initial partitions for time-series tables

### Extensions Required
```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
```

### Seed Data

#### Default Permissions
```sql
INSERT INTO permissions (resource, action, description) VALUES
    ('vm', 'create', 'Create virtual machines'),
    ('vm', 'read', 'View virtual machines'),
    ('vm', 'update', 'Modify virtual machines'),
    ('vm', 'delete', 'Delete virtual machines'),
    ('vm', 'start', 'Start virtual machines'),
    ('vm', 'stop', 'Stop virtual machines'),
    ('vm', 'snapshot', 'Create VM snapshots'),
    ('network', 'create', 'Create networks'),
    ('network', 'read', 'View networks'),
    ('network', 'update', 'Modify networks'),
    ('network', 'delete', 'Delete networks'),
    ('storage', 'read', 'View storage'),
    ('storage', 'allocate', 'Allocate storage'),
    ('org', 'read', 'View organization'),
    ('org', 'update', 'Update organization'),
    ('org', 'members', 'Manage members');
```

#### Default System Roles
```sql
-- Platform superadmin (not tied to any org)
INSERT INTO roles (id, name, description, is_system) VALUES
    ('00000000-0000-0000-0000-000000000001', 'platform_admin', 'Platform administrator', true);

-- Organization roles (will be duplicated per org)
INSERT INTO roles (name, description, is_system) VALUES
    ('org_owner', 'Organization owner with full access', true),
    ('org_admin', 'Organization administrator', true),
    ('org_member', 'Organization member with VM management', true),
    ('org_viewer', 'Read-only access', true);
```

## Optimization & Maintenance

### Indexing Strategy
- Primary keys on all tables (UUID)
- Foreign keys indexed automatically
- Composite indexes for common query patterns
- Partial indexes for soft-deleted rows

### Partitioning
- `audit_logs`: Monthly partitions
- `usage_records`: Monthly partitions
- Automated partition creation via cron job or pg_partman

### Maintenance Tasks
- Regular VACUUM and ANALYZE
- Partition pruning for old audit logs (retain 12 months)
- Usage data aggregation (daily job)
- Index maintenance and rebuilding

### Performance Considerations
- Connection pooling (PgBouncer)
- Read replicas for reporting queries
- Materialized views for dashboard queries
- Query optimization with EXPLAIN ANALYZE

## Backup Strategy

- Full daily backups with WAL archiving
- Point-in-time recovery (PITR) enabled
- Backup retention: 30 days
- Test restore monthly
- Geo-redundant backup storage

## Next Steps

Refer to:
- [API_SPECIFICATION.md](API_SPECIFICATION.md) for API endpoints that use this schema
- [ARCHITECTURE.md](ARCHITECTURE.md) for how services interact with the database
