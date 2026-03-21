"""
Role-Based Access Control (RBAC) system.

Defines roles, permissions, and permission matrix for multi-tenant authorization.
"""
from enum import Enum
from typing import Set


class Role(str, Enum):
    """User roles within organizations."""
    SUPERADMIN = "superadmin"      # Global admin, not org-specific
    ORG_ADMIN = "admin"            # Organization administrator
    ORG_MEMBER = "member"          # Regular organization member
    ORG_VIEWER = "viewer"          # Read-only access


class Permission(str, Enum):
    """Resource permissions."""
    # VM permissions
    VM_CREATE = "vm:create"
    VM_READ = "vm:read"
    VM_UPDATE = "vm:update"
    VM_DELETE = "vm:delete"
    VM_START = "vm:start"
    VM_STOP = "vm:stop"
    VM_RESTART = "vm:restart"

    # Cluster permissions
    CLUSTER_CREATE = "cluster:create"
    CLUSTER_READ = "cluster:read"
    CLUSTER_UPDATE = "cluster:update"
    CLUSTER_DELETE = "cluster:delete"
    CLUSTER_SYNC = "cluster:sync"

    # Organization permissions
    ORG_READ = "org:read"
    ORG_UPDATE = "org:update"
    ORG_MEMBER_INVITE = "org:member:invite"
    ORG_MEMBER_REMOVE = "org:member:remove"
    ORG_MEMBER_UPDATE_ROLE = "org:member:update_role"
    ORG_MEMBER_READ = "org:member:read"

    # Quota permissions
    QUOTA_READ = "quota:read"
    QUOTA_UPDATE = "quota:update"

    # Network permissions
    NETWORK_CREATE = "network:create"
    NETWORK_READ = "network:read"
    NETWORK_UPDATE = "network:update"
    NETWORK_DELETE = "network:delete"
    NETWORK_ATTACH = "network:attach"


# Permission matrix - defines what each role can do
ROLE_PERMISSIONS: dict[Role, Set[Permission]] = {
    # Superadmin has all permissions
    Role.SUPERADMIN: {perm for perm in Permission},

    # Organization Admin
    Role.ORG_ADMIN: {
        # VM management
        Permission.VM_CREATE,
        Permission.VM_READ,
        Permission.VM_UPDATE,
        Permission.VM_DELETE,
        Permission.VM_START,
        Permission.VM_STOP,
        Permission.VM_RESTART,

        # Cluster (read-only)
        Permission.CLUSTER_READ,

        # Organization management
        Permission.ORG_READ,
        Permission.ORG_UPDATE,
        Permission.ORG_MEMBER_INVITE,
        Permission.ORG_MEMBER_REMOVE,
        Permission.ORG_MEMBER_UPDATE_ROLE,
        Permission.ORG_MEMBER_READ,

        # Quota (read-only)
        Permission.QUOTA_READ,

        # Network management (full access)
        Permission.NETWORK_CREATE,
        Permission.NETWORK_READ,
        Permission.NETWORK_UPDATE,
        Permission.NETWORK_DELETE,
        Permission.NETWORK_ATTACH,
    },

    # Organization Member
    Role.ORG_MEMBER: {
        # VM management (own VMs only, enforced at application level)
        Permission.VM_CREATE,
        Permission.VM_READ,
        Permission.VM_UPDATE,
        Permission.VM_DELETE,
        Permission.VM_START,
        Permission.VM_STOP,
        Permission.VM_RESTART,

        # Cluster (read-only)
        Permission.CLUSTER_READ,

        # Organization (read-only)
        Permission.ORG_READ,
        Permission.ORG_MEMBER_READ,

        # Quota (read-only)
        Permission.QUOTA_READ,

        # Network (read and attach to existing networks)
        Permission.NETWORK_READ,
        Permission.NETWORK_ATTACH,
    },

    # Organization Viewer
    Role.ORG_VIEWER: {
        # VM (read-only)
        Permission.VM_READ,

        # Cluster (read-only)
        Permission.CLUSTER_READ,

        # Organization (read-only)
        Permission.ORG_READ,
        Permission.ORG_MEMBER_READ,

        # Quota (read-only)
        Permission.QUOTA_READ,

        # Network (read-only)
        Permission.NETWORK_READ,
    }
}


def has_permission(role: Role, permission: Permission) -> bool:
    """
    Check if role has specific permission.

    Args:
        role: User's role
        permission: Permission to check

    Returns:
        True if role has permission, False otherwise
    """
    return permission in ROLE_PERMISSIONS.get(role, set())


def get_role_permissions(role: Role) -> Set[Permission]:
    """
    Get all permissions for a role.

    Args:
        role: User's role

    Returns:
        Set of permissions
    """
    return ROLE_PERMISSIONS.get(role, set())


def is_org_admin_or_higher(role: Role) -> bool:
    """Check if role is organization admin or superadmin."""
    return role in [Role.SUPERADMIN, Role.ORG_ADMIN]


def can_manage_members(role: Role) -> bool:
    """Check if role can manage organization members."""
    return has_permission(role, Permission.ORG_MEMBER_INVITE)


def can_manage_vms(role: Role) -> bool:
    """Check if role can create/delete VMs."""
    return has_permission(role, Permission.VM_CREATE)
