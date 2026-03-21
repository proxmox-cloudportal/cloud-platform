"""
API v1 router combining all endpoint routers.
"""
from fastapi import APIRouter

from app.api.v1.endpoints import auth, users, health, vms, clusters, organizations, quotas, isos, storage, disks, snapshots, networks

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(vms.router)
api_router.include_router(clusters.router)
api_router.include_router(organizations.router)
api_router.include_router(quotas.router)
api_router.include_router(isos.router)
api_router.include_router(storage.router)
api_router.include_router(disks.router)
api_router.include_router(snapshots.router)
api_router.include_router(networks.router)
