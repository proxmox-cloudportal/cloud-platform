"""
Background tasks for ISO image management.
"""
import logging
import hashlib
import requests
from pathlib import Path
from datetime import datetime
from typing import Optional

from celery import Task
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.tasks.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.iso_image import ISOImage
from app.models.proxmox_cluster import ProxmoxCluster
from app.services.proxmox_service import ProxmoxService
from app.core.config import settings

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


@celery_app.task(bind=True, base=DatabaseTask, max_retries=3, default_retry_delay=60)
def transfer_iso_to_proxmox(self, iso_id: str):
    """
    Transfer uploaded ISO file to Proxmox storage.

    This task:
    1. Gets the ISO record from database
    2. Selects a target Proxmox cluster
    3. Finds an available node and ISO-capable storage
    4. Uploads the ISO via Proxmox API
    5. Updates the ISO record with Proxmox details
    6. Optionally cleans up the local file

    Args:
        iso_id: ISO image UUID

    Raises:
        Exception: If transfer fails after max retries
    """
    db = self.db

    try:
        # Get ISO record
        result = db.execute(
            select(ISOImage).where(
                ISOImage.id == iso_id,
                ISOImage.deleted_at.is_(None)
            )
        )
        iso = result.scalar_one_or_none()

        if not iso:
            logger.error(f"ISO {iso_id} not found")
            return {"status": "error", "message": "ISO not found"}

        if iso.upload_status == "ready":
            logger.info(f"ISO {iso_id} already transferred")
            return {"status": "success", "message": "ISO already transferred"}

        # Update status to processing
        iso.upload_status = "processing"
        iso.upload_progress = 10.0
        db.commit()

        # Select target Proxmox cluster
        # For now, use the first active shared cluster
        # TODO: Implement smarter cluster selection logic
        result = db.execute(
            select(ProxmoxCluster).where(
                ProxmoxCluster.is_active == True,
                ProxmoxCluster.is_shared == True,
                ProxmoxCluster.deleted_at.is_(None)
            ).limit(1)
        )
        cluster = result.scalar_one_or_none()

        if not cluster:
            raise Exception("No active Proxmox cluster available")

        logger.info(f"Selected cluster {cluster.name} for ISO {iso_id}")

        # Create Proxmox service
        proxmox = ProxmoxService(cluster=cluster)

        # Get available nodes
        nodes = proxmox.get_nodes()
        if not nodes:
            raise Exception(f"No nodes available in cluster {cluster.name}")

        # Use first node
        node_name = nodes[0]['node']
        logger.info(f"Using node {node_name}")

        iso.upload_progress = 30.0
        db.commit()

        # Get storage pools that support ISO content
        storage_pools = proxmox.get_storage_pools(node_name)
        iso_storage = None

        for storage in storage_pools:
            try:
                # Check if storage supports ISO content
                storage_status = proxmox.get_storage_status(node_name, storage['storage'])
                content_types = storage.get('content', '').split(',')

                if 'iso' in content_types and storage.get('enabled', True):
                    iso_storage = storage['storage']
                    logger.info(f"Selected storage {iso_storage} for ISO")
                    break
            except Exception as e:
                logger.warning(f"Failed to check storage {storage.get('storage')}: {e}")
                continue

        if not iso_storage:
            raise Exception(f"No ISO-capable storage found on node {node_name}")

        iso.upload_progress = 50.0
        db.commit()

        # Upload ISO to Proxmox
        logger.info(f"Uploading ISO {iso.filename} to {iso_storage}")

        try:
            result = proxmox.upload_iso(
                node=node_name,
                storage=iso_storage,
                filename=iso.filename,
                file_path=iso.local_path
            )

            iso.upload_progress = 90.0
            db.commit()

            logger.info(f"ISO upload task started: {result}")

            # Update ISO record with Proxmox details
            iso.proxmox_cluster_id = cluster.id
            iso.proxmox_storage = iso_storage
            iso.proxmox_volid = f"{iso_storage}:iso/{iso.filename}"
            iso.upload_status = "ready"
            iso.upload_progress = 100.0
            iso.synced_to_proxmox_at = datetime.utcnow()
            iso.error_message = None

            db.commit()

            logger.info(f"ISO {iso_id} successfully transferred to Proxmox")

            # TODO: Optionally clean up local file
            # local_path = Path(iso.local_path)
            # if local_path.exists():
            #     local_path.unlink()
            #     iso.local_path = None
            #     db.commit()

            return {
                "status": "success",
                "iso_id": iso_id,
                "proxmox_volid": iso.proxmox_volid
            }

        except Exception as upload_error:
            logger.error(f"Failed to upload ISO to Proxmox: {upload_error}")
            raise

    except Exception as e:
        logger.error(f"Error transferring ISO {iso_id}: {e}")

        # Update ISO status to failed
        try:
            iso.upload_status = "failed"
            iso.error_message = str(e)
            db.commit()
        except:
            pass

        # Retry if not at max retries
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying ISO transfer {iso_id} (attempt {self.request.retries + 1})")
            raise self.retry(exc=e)

        return {"status": "error", "message": str(e)}


@celery_app.task(bind=True, base=DatabaseTask, max_retries=3, default_retry_delay=60)
def download_iso_from_url(self, iso_id: str):
    """
    Download ISO from URL using Proxmox's built-in download-url feature.

    This task:
    1. Gets the ISO record from database
    2. Selects a target Proxmox cluster
    3. Initiates download from URL on Proxmox
    4. Monitors the download task status
    5. Updates the ISO record when complete

    Args:
        iso_id: ISO image UUID

    Raises:
        Exception: If download fails after max retries
    """
    db = self.db

    try:
        # Get ISO record
        result = db.execute(
            select(ISOImage).where(
                ISOImage.id == iso_id,
                ISOImage.deleted_at.is_(None)
            )
        )
        iso = result.scalar_one_or_none()

        if not iso:
            logger.error(f"ISO {iso_id} not found")
            return {"status": "error", "message": "ISO not found"}

        if iso.upload_status == "ready":
            logger.info(f"ISO {iso_id} already ready")
            return {"status": "success", "message": "ISO already ready"}

        if not iso.source_url:
            logger.error(f"ISO {iso_id} has no source URL")
            return {"status": "error", "message": "No source URL provided"}

        # Update status to downloading
        iso.download_status = "downloading"
        iso.upload_status = "processing"
        iso.upload_progress = 10.0
        db.commit()

        # Select target Proxmox cluster
        result = db.execute(
            select(ProxmoxCluster).where(
                ProxmoxCluster.is_active == True,
                ProxmoxCluster.is_shared == True,
                ProxmoxCluster.deleted_at.is_(None)
            ).limit(1)
        )
        cluster = result.scalar_one_or_none()

        if not cluster:
            raise Exception("No active Proxmox cluster available")

        logger.info(f"Selected cluster {cluster.name} for ISO {iso_id}")

        # Create Proxmox service
        proxmox = ProxmoxService(cluster=cluster)

        # Get available nodes
        nodes = proxmox.get_nodes()
        if not nodes:
            raise Exception(f"No nodes available in cluster {cluster.name}")

        node_name = nodes[0]['node']
        logger.info(f"Using node {node_name}")

        iso.upload_progress = 20.0
        db.commit()

        # Get storage pools that support ISO content
        storage_pools = proxmox.get_storage_pools(node_name)
        iso_storage = None

        for storage in storage_pools:
            try:
                content_types = storage.get('content', '').split(',')
                if 'iso' in content_types and storage.get('enabled', True):
                    iso_storage = storage['storage']
                    logger.info(f"Selected storage {iso_storage} for ISO")
                    break
            except Exception as e:
                logger.warning(f"Failed to check storage {storage.get('storage')}: {e}")
                continue

        if not iso_storage:
            raise Exception(f"No ISO-capable storage found on node {node_name}")

        iso.upload_progress = 30.0
        db.commit()

        # Initiate download from URL on Proxmox
        logger.info(f"Initiating download of {iso.source_url} to {iso_storage}")

        download_result = proxmox.download_iso_from_url(
            node=node_name,
            storage=iso_storage,
            filename=iso.filename,
            url=iso.source_url,
            checksum=None  # TODO: Add checksum support if available
        )

        task_id = download_result['task_id']
        logger.info(f"Proxmox download task started: {task_id}")

        iso.upload_progress = 40.0
        db.commit()

        # Monitor task status (poll until complete)
        import time
        max_poll_attempts = 600  # 10 minutes max (600 * 1 second)
        poll_count = 0

        while poll_count < max_poll_attempts:
            try:
                task_status = proxmox.get_task_status(node_name, task_id)

                status = task_status.get('status')
                exitstatus = task_status.get('exitstatus')

                if status == 'stopped':
                    if exitstatus == 'OK':
                        # Download successful
                        logger.info(f"ISO download completed successfully: {iso_id}")

                        # Calculate checksum from URL (since we don't have direct file access)
                        url_checksum = hashlib.sha256(iso.source_url.encode()).hexdigest()

                        # Update ISO record
                        iso.proxmox_cluster_id = cluster.id
                        iso.proxmox_storage = iso_storage
                        iso.proxmox_volid = f"{iso_storage}:iso/{iso.filename}"
                        iso.checksum_sha256 = url_checksum
                        iso.upload_status = "ready"
                        iso.download_status = "downloaded"
                        iso.upload_progress = 100.0
                        iso.synced_to_proxmox_at = datetime.utcnow()
                        iso.uploaded_at = datetime.utcnow()
                        iso.error_message = None

                        db.commit()

                        return {
                            "status": "success",
                            "iso_id": iso_id,
                            "proxmox_volid": iso.proxmox_volid
                        }
                    else:
                        # Download failed
                        error_msg = f"Download task failed: {exitstatus}"
                        logger.error(error_msg)
                        raise Exception(error_msg)

                # Still running, update progress
                progress = 40.0 + (poll_count / max_poll_attempts) * 50.0
                iso.upload_progress = min(progress, 90.0)
                db.commit()

                # Wait before next poll
                time.sleep(1)
                poll_count += 1

            except Exception as poll_error:
                logger.error(f"Error polling task status: {poll_error}")
                raise

        # Timeout
        raise Exception(f"Download task timed out after {max_poll_attempts} seconds")

    except Exception as e:
        logger.error(f"Error downloading ISO from URL {iso_id}: {e}")

        # Update ISO status to failed
        try:
            iso.upload_status = "failed"
            iso.download_status = "failed"
            iso.error_message = str(e)
            db.commit()
        except:
            pass

        # Retry if not at max retries
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying ISO URL download {iso_id} (attempt {self.request.retries + 1})")
            raise self.retry(exc=e)

        return {"status": "error", "message": str(e)}


@celery_app.task(bind=True, base=DatabaseTask)
def cleanup_iso_storage(self, iso_id: str):
    """
    Clean up ISO files from Proxmox and local storage after deletion.

    Args:
        iso_id: ISO image UUID
    """
    db = self.db

    try:
        # Get ISO record (including soft-deleted)
        result = db.execute(
            select(ISOImage).where(ISOImage.id == iso_id)
        )
        iso = result.scalar_one_or_none()

        if not iso:
            logger.error(f"ISO {iso_id} not found")
            return {"status": "error", "message": "ISO not found"}

        # Delete from Proxmox if it exists there
        if iso.proxmox_volid and iso.proxmox_cluster_id:
            try:
                result = db.execute(
                    select(ProxmoxCluster).where(
                        ProxmoxCluster.id == iso.proxmox_cluster_id
                    )
                )
                cluster = result.scalar_one_or_none()

                if cluster:
                    proxmox = ProxmoxService(cluster=cluster)

                    # Get first available node
                    nodes = proxmox.get_nodes()
                    if nodes:
                        node_name = nodes[0]['node']
                        proxmox.delete_iso(node_name, iso.proxmox_volid)
                        logger.info(f"Deleted ISO {iso.proxmox_volid} from Proxmox")

            except Exception as e:
                logger.error(f"Failed to delete ISO from Proxmox: {e}")
                # Continue with local cleanup even if Proxmox cleanup fails

        # Delete local file if it exists
        if iso.local_path:
            try:
                local_path = Path(iso.local_path)
                if local_path.exists():
                    local_path.unlink()
                    logger.info(f"Deleted local ISO file {iso.local_path}")
            except Exception as e:
                logger.error(f"Failed to delete local ISO file: {e}")

        logger.info(f"Cleanup completed for ISO {iso_id}")
        return {"status": "success", "iso_id": iso_id}

    except Exception as e:
        logger.error(f"Error cleaning up ISO {iso_id}: {e}")
        return {"status": "error", "message": str(e)}
