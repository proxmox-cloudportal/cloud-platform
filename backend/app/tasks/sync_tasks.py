"""
Background tasks for synchronizing data from Proxmox clusters.
"""
import logging
from typing import Optional
from datetime import datetime

from celery import Task
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.tasks.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.proxmox_cluster import ProxmoxCluster
from app.models.storage_pool import StoragePool
from app.services.proxmox_service import ProxmoxService

logger = logging.getLogger(__name__)


class DatabaseTask(Task):
    """Base task with database session management."""

    _db: Optional[Session] = None

    @property
    def db(self) -> Session:
        """Get database session."""
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def after_return(self, *args, **kwargs):
        """Close database session after task completes."""
        if self._db is not None:
            self._db.close()
            self._db = None


@celery_app.task(bind=True, base=DatabaseTask)
def sync_all_storage_pools(self):
    """
    Periodic task to sync storage pools from all active Proxmox clusters.

    This task runs every 5 minutes (configured in celery beat schedule).
    """
    db = self.db

    try:
        # Get all active clusters
        result = db.execute(
            select(ProxmoxCluster).where(
                ProxmoxCluster.is_active == True,
                ProxmoxCluster.deleted_at.is_(None)
            )
        )
        clusters = list(result.scalars().all())

        logger.info(f"Syncing storage pools from {len(clusters)} cluster(s)")

        total_synced = 0
        total_errors = 0

        for cluster in clusters:
            try:
                result = sync_storage_pools_for_cluster(cluster.id)
                total_synced += result.get("synced_pools", 0)
                logger.info(f"Synced {result['synced_pools']} pools from cluster {cluster.name}")
            except Exception as e:
                logger.error(f"Failed to sync storage from cluster {cluster.name}: {e}")
                total_errors += 1

        return {
            "status": "completed",
            "clusters_processed": len(clusters),
            "total_pools_synced": total_synced,
            "errors": total_errors
        }

    except Exception as e:
        logger.error(f"Error in sync_all_storage_pools: {e}")
        return {"status": "error", "message": str(e)}


def sync_storage_pools_for_cluster(cluster_id: str) -> dict:
    """
    Sync storage pools from a specific Proxmox cluster.

    Args:
        cluster_id: Proxmox cluster UUID

    Returns:
        Dictionary with sync statistics
    """
    db = SessionLocal()

    try:
        # Get cluster
        result = db.execute(
            select(ProxmoxCluster).where(
                ProxmoxCluster.id == cluster_id,
                ProxmoxCluster.deleted_at.is_(None)
            )
        )
        cluster = result.scalar_one_or_none()

        if not cluster:
            raise Exception(f"Cluster {cluster_id} not found")

        # Create Proxmox service
        proxmox = ProxmoxService(cluster=cluster)

        # Get nodes
        nodes = proxmox.get_nodes()
        if not nodes:
            logger.warning(f"No nodes available in cluster {cluster.name}")
            return {"synced_pools": 0, "added": 0, "updated": 0, "deactivated": 0}

        # Use first node for storage query
        node_name = nodes[0]['node']

        # Get storage pools from Proxmox
        storage_list = proxmox.get_storage_pools(node_name)

        synced_pools = 0
        added = 0
        updated = 0

        for storage_info in storage_list:
            storage_name = storage_info.get('storage')
            if not storage_name:
                continue

            try:
                # Get detailed storage status
                storage_status = proxmox.get_storage_status(node_name, storage_name)

                # Parse content types
                content_str = storage_info.get('content', '')
                content_types = [c.strip() for c in content_str.split(',') if c.strip()]

                # Check if storage pool exists in database
                result = db.execute(
                    select(StoragePool).where(
                        StoragePool.proxmox_cluster_id == cluster_id,
                        StoragePool.storage_name == storage_name,
                        StoragePool.deleted_at.is_(None)
                    )
                )
                storage_pool = result.scalar_one_or_none()

                if storage_pool:
                    # Update existing pool
                    storage_pool.storage_type = storage_info.get('type', 'unknown')
                    storage_pool.content_types = content_types
                    storage_pool.total_bytes = storage_status.get('total')
                    storage_pool.used_bytes = storage_status.get('used')
                    storage_pool.available_bytes = storage_status.get('avail')
                    storage_pool.is_active = storage_info.get('enabled', True)
                    storage_pool.is_shared = storage_info.get('shared', False)
                    storage_pool.last_synced_at = datetime.utcnow()
                    updated += 1
                else:
                    # Create new pool
                    storage_pool = StoragePool(
                        proxmox_cluster_id=cluster_id,
                        storage_name=storage_name,
                        storage_type=storage_info.get('type', 'unknown'),
                        content_types=content_types,
                        total_bytes=storage_status.get('total'),
                        used_bytes=storage_status.get('used'),
                        available_bytes=storage_status.get('avail'),
                        is_active=storage_info.get('enabled', True),
                        is_shared=storage_info.get('shared', False),
                        last_synced_at=datetime.utcnow()
                    )
                    db.add(storage_pool)
                    added += 1

                synced_pools += 1

            except Exception as e:
                logger.error(f"Failed to sync storage {storage_name}: {e}")
                continue

        # Deactivate storage pools that no longer exist in Proxmox
        synced_names = [s.get('storage') for s in storage_list if s.get('storage')]
        result = db.execute(
            select(StoragePool).where(
                StoragePool.proxmox_cluster_id == cluster_id,
                StoragePool.deleted_at.is_(None),
                StoragePool.storage_name.notin_(synced_names)
            )
        )
        missing_pools = list(result.scalars().all())

        deactivated = 0
        for pool in missing_pools:
            pool.is_active = False
            deactivated += 1

        db.commit()

        logger.info(f"Cluster {cluster.name}: synced {synced_pools}, added {added}, updated {updated}, deactivated {deactivated}")

        return {
            "synced_pools": synced_pools,
            "added": added,
            "updated": updated,
            "deactivated": deactivated
        }

    except Exception as e:
        logger.error(f"Error syncing storage pools for cluster {cluster_id}: {e}")
        raise

    finally:
        db.close()
