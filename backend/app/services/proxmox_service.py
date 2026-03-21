"""
Proxmox VE service wrapper for managing VMs via Proxmox API.
"""
from typing import Optional, Dict, Any, List
from proxmoxer import ProxmoxAPI
from proxmoxer.core import ResourceException
import logging

from app.models.proxmox_cluster import ProxmoxCluster

logger = logging.getLogger(__name__)


class ProxmoxService:
    """Service for interacting with Proxmox VE API."""

    def __init__(
        self,
        cluster: Optional[ProxmoxCluster] = None,
        host: Optional[str] = None,
        user: Optional[str] = None,
        token_name: Optional[str] = None,
        token_value: Optional[str] = None,
        password: Optional[str] = None,
        verify_ssl: bool = False,
    ):
        """
        Initialize Proxmox service with cluster credentials.

        Args:
            cluster: ProxmoxCluster model instance (preferred)
            host: Proxmox host (alternative to cluster)
            user: Username (alternative to cluster)
            token_name: API token name (alternative to cluster)
            token_value: API token value (alternative to cluster)
            password: Password (alternative to cluster)
            verify_ssl: Verify SSL certificate
        """
        self.cluster = cluster
        self._host = host
        self._user = user
        self._token_name = token_name
        self._token_value = token_value
        self._password = password
        self._verify_ssl = verify_ssl
        self._proxmox: Optional[ProxmoxAPI] = None

    def _get_connection(self) -> ProxmoxAPI:
        """Get or create Proxmox API connection."""
        if self._proxmox is None:
            # Get credentials from cluster or direct parameters
            if self.cluster:
                host = self.cluster.api_url.replace("https://", "").replace("http://", "").split(":")[0]
                user = self.cluster.api_username
                token_name = self.cluster.api_token_id
                token_value = self.cluster.api_token_secret_encrypted
                password = self.cluster.api_password_encrypted
                verify_ssl = self.cluster.verify_ssl
            else:
                host = self._host
                user = self._user
                token_name = self._token_name
                token_value = self._token_value
                password = self._password
                verify_ssl = self._verify_ssl

            # Use token authentication if available, otherwise password
            if token_name and token_value:
                self._proxmox = ProxmoxAPI(
                    host,
                    user=user,
                    token_name=token_name,
                    token_value=token_value,
                    verify_ssl=verify_ssl,
                )
            else:
                self._proxmox = ProxmoxAPI(
                    host,
                    user=user,
                    password=password,
                    verify_ssl=verify_ssl,
                )

        return self._proxmox

    def get_next_vmid(self) -> int:
        """
        Get next available VMID from Proxmox cluster.

        Returns:
            Next available VMID
        """
        try:
            proxmox = self._get_connection()
            vmid = proxmox.cluster.nextid.get()
            # Ensure we return an integer (Proxmox API may return string)
            return int(vmid) if vmid else 100
        except Exception as e:
            logger.error(f"Failed to get next VMID: {e}")
            # Fallback to a random high number if API call fails
            import random
            return random.randint(1000, 9999)

    def get_nodes(self) -> List[Dict[str, Any]]:
        """
        Get list of nodes in the cluster.

        Returns:
            List of node information dictionaries
        """
        try:
            proxmox = self._get_connection()
            return proxmox.nodes.get()
        except Exception as e:
            logger.error(f"Failed to get nodes: {e}")
            return []

    def get_version(self) -> Dict[str, Any]:
        """
        Get Proxmox VE version information.

        Returns:
            Version information dictionary
        """
        try:
            proxmox = self._get_connection()
            return proxmox.version.get()
        except Exception as e:
            logger.error(f"Failed to get version: {e}")
            return {}

    def select_best_node(self) -> Optional[str]:
        """
        Select the best node for VM placement based on available resources.

        Returns:
            Node name or None if no nodes available
        """
        nodes = self.get_nodes()
        if not nodes:
            return None

        # Find node with most available memory
        best_node = max(nodes, key=lambda n: n.get("maxmem", 0) - n.get("mem", 0))
        return best_node.get("node")

    def create_vm(
        self,
        node: str,
        vmid: int,
        name: str,
        cores: int,
        memory: int,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create a new VM on Proxmox.

        Args:
            node: Node name where VM should be created
            vmid: VM ID
            name: VM name
            cores: Number of CPU cores
            memory: Memory in MB
            **kwargs: Additional VM configuration options

        Returns:
            Task ID and status information

        Raises:
            ResourceException: If VM creation fails
        """
        try:
            proxmox = self._get_connection()

            # Base configuration
            config = {
                "vmid": vmid,
                "name": name,
                "cores": cores,
                "memory": memory,
                "sockets": kwargs.get("sockets", 1),
                "ostype": kwargs.get("ostype", "l26"),  # Linux 2.6+
                "net0": kwargs.get("net0", "virtio,bridge=vmbr0"),
            }

            # Add disk configuration if provided
            if "disk_gb" in kwargs:
                # Use raw format which is universally supported (LVM-Thin, ZFS, Directory)
                # Don't specify format to let Proxmox choose the appropriate one for the storage
                config["scsi0"] = f"local-lvm:{kwargs['disk_gb']}"

            # Create VM
            logger.info(f"Creating VM {vmid} ({name}) on node {node}")
            task = proxmox.nodes(node).qemu.create(**config)

            return {
                "task_id": task,
                "vmid": vmid,
                "node": node,
                "status": "creating"
            }

        except ResourceException as e:
            logger.error(f"Failed to create VM {vmid}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating VM {vmid}: {e}")
            raise

    def start_vm(self, node: str, vmid: int) -> Dict[str, Any]:
        """
        Start a VM.

        Args:
            node: Node name where VM is located
            vmid: VM ID

        Returns:
            Task ID and status
        """
        try:
            proxmox = self._get_connection()
            task = proxmox.nodes(node).qemu(vmid).status.start.post()
            logger.info(f"Started VM {vmid} on node {node}")
            return {"task_id": task, "status": "starting"}
        except Exception as e:
            logger.error(f"Failed to start VM {vmid}: {e}")
            raise

    def stop_vm(self, node: str, vmid: int, force: bool = False) -> Dict[str, Any]:
        """
        Stop a VM.

        Args:
            node: Node name where VM is located
            vmid: VM ID
            force: Force stop (equivalent to power off)

        Returns:
            Task ID and status
        """
        try:
            proxmox = self._get_connection()
            if force:
                task = proxmox.nodes(node).qemu(vmid).status.stop.post()
            else:
                task = proxmox.nodes(node).qemu(vmid).status.shutdown.post()

            logger.info(f"Stopped VM {vmid} on node {node} (force={force})")
            return {"task_id": task, "status": "stopping"}
        except Exception as e:
            logger.error(f"Failed to stop VM {vmid}: {e}")
            raise

    def restart_vm(self, node: str, vmid: int) -> Dict[str, Any]:
        """
        Restart a VM.

        Args:
            node: Node name where VM is located
            vmid: VM ID

        Returns:
            Task ID and status
        """
        try:
            proxmox = self._get_connection()
            task = proxmox.nodes(node).qemu(vmid).status.reboot.post()
            logger.info(f"Restarted VM {vmid} on node {node}")
            return {"task_id": task, "status": "restarting"}
        except Exception as e:
            logger.error(f"Failed to restart VM {vmid}: {e}")
            raise

    def delete_vm(self, node: str, vmid: int) -> Dict[str, Any]:
        """
        Delete a VM.

        Args:
            node: Node name where VM is located
            vmid: VM ID

        Returns:
            Task ID and status
        """
        try:
            proxmox = self._get_connection()
            task = proxmox.nodes(node).qemu(vmid).delete()
            logger.info(f"Deleted VM {vmid} from node {node}")
            return {"task_id": task, "status": "deleting"}
        except Exception as e:
            logger.error(f"Failed to delete VM {vmid}: {e}")
            raise

    def get_console_url(self, node: str, vmid: int) -> Dict[str, Any]:
        """
        Get noVNC console URL for a VM.

        Creates a simple console URL that relies on the user being logged into
        Proxmox in their browser. The browser's existing Proxmox session cookies
        will be used for authentication.

        Args:
            node: Node name where VM is located
            vmid: VM ID

        Returns:
            Dict containing console URL

        Raises:
            Exception: If VM information cannot be retrieved
        """
        try:
            proxmox = self._get_connection()

            # Get VM name for the URL
            vm_config = proxmox.nodes(node).qemu(vmid).config.get()
            vm_name = vm_config.get('name', f'vm-{vmid}')

            # Get cluster host
            if self.cluster:
                api_url = self.cluster.api_url
                host = api_url.replace("https://", "").replace("http://", "").split(":")[0]
                port = 8006  # Default Proxmox web interface port
            else:
                host = self._host
                port = 8006

            # Build simple console URL that uses browser's existing Proxmox session
            console_url = (
                f"https://{host}:{port}/"
                f"?console=kvm&novnc=1&vmid={vmid}&vmname={vm_name}&node={node}"
                f"&resize=off&cmd="
            )

            logger.info(f"Generated console URL for VM {vmid} ({vm_name}) on node {node}")

            return {
                "console_url": console_url,
                "node": node,
                "vmid": vmid,
                "vm_name": vm_name
            }

        except Exception as e:
            logger.error(f"Failed to get console URL for VM {vmid}: {e}")
            raise

    def get_vm_status(self, node: str, vmid: int) -> Dict[str, Any]:
        """
        Get VM status and configuration.

        Args:
            node: Node name where VM is located
            vmid: VM ID

        Returns:
            VM status information
        """
        try:
            proxmox = self._get_connection()
            status = proxmox.nodes(node).qemu(vmid).status.current.get()
            return status
        except Exception as e:
            logger.error(f"Failed to get VM {vmid} status: {e}")
            raise

    def get_vm_config(self, node: str, vmid: int) -> Dict[str, Any]:
        """
        Get VM configuration.

        Args:
            node: Node name where VM is located
            vmid: VM ID

        Returns:
            VM configuration
        """
        try:
            proxmox = self._get_connection()
            config = proxmox.nodes(node).qemu(vmid).config.get()
            return config
        except Exception as e:
            logger.error(f"Failed to get VM {vmid} config: {e}")
            raise

    def test_connection(self) -> bool:
        """
        Test connection to Proxmox cluster.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            proxmox = self._get_connection()
            # Try to get cluster status
            proxmox.cluster.status.get()
            return True
        except Exception as e:
            logger.error(f"Proxmox connection test failed: {e}")
            return False

    # ===== Storage Pool Methods =====

    def get_storage_pools(self, node: str) -> List[Dict[str, Any]]:
        """
        Get list of storage pools available on a node.

        Args:
            node: Node name

        Returns:
            List of storage pool information
        """
        try:
            proxmox = self._get_connection()
            storage_list = proxmox.nodes(node).storage.get()
            logger.info(f"Retrieved {len(storage_list)} storage pools from node {node}")
            return storage_list
        except Exception as e:
            logger.error(f"Failed to get storage pools from node {node}: {e}")
            raise

    def get_storage_status(self, node: str, storage: str) -> Dict[str, Any]:
        """
        Get detailed status of a specific storage pool.

        Args:
            node: Node name
            storage: Storage pool name

        Returns:
            Storage status including capacity information
        """
        try:
            proxmox = self._get_connection()
            status = proxmox.nodes(node).storage(storage).status.get()
            return status
        except Exception as e:
            logger.error(f"Failed to get storage {storage} status on node {node}: {e}")
            raise

    def get_storage_content(self, node: str, storage: str, content_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get content (ISOs, images, etc.) from a storage pool.

        Args:
            node: Node name
            storage: Storage pool name
            content_type: Filter by content type (iso, images, backup, vztmpl)

        Returns:
            List of storage content items
        """
        try:
            proxmox = self._get_connection()
            params = {}
            if content_type:
                params['content'] = content_type

            content = proxmox.nodes(node).storage(storage).content.get(**params)
            return content
        except Exception as e:
            logger.error(f"Failed to get storage {storage} content on node {node}: {e}")
            raise

    # ===== ISO Management Methods =====

    def upload_iso(self, node: str, storage: str, filename: str, file_path: str) -> Dict[str, Any]:
        """
        Upload an ISO file to Proxmox storage.

        Args:
            node: Node name
            storage: Storage pool name
            filename: Name for the ISO file
            file_path: Local path to the ISO file

        Returns:
            Upload task information

        Note:
            This is a placeholder. Actual implementation requires multipart upload
            or SCP transfer to Proxmox node, which is complex. Consider using
            proxmox.nodes(node).storage(storage).upload for actual implementation.
        """
        try:
            proxmox = self._get_connection()

            # Upload ISO using Proxmox API
            with open(file_path, 'rb') as iso_file:
                task = proxmox.nodes(node).storage(storage).upload.post(
                    content='iso',
                    filename=filename,
                    file=iso_file
                )

            logger.info(f"Uploaded ISO {filename} to {storage} on node {node}")
            return {"task_id": task, "status": "uploading"}
        except Exception as e:
            logger.error(f"Failed to upload ISO {filename} to {storage} on node {node}: {e}")
            raise

    def download_iso_from_url(
        self,
        node: str,
        storage: str,
        filename: str,
        url: str,
        checksum: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Download an ISO file from a URL directly to Proxmox storage.

        This uses Proxmox's built-in download-url feature which is more efficient
        than downloading to our backend and then uploading.

        Args:
            node: Node name
            storage: Storage pool name
            filename: Name for the ISO file (with .iso extension)
            url: URL to download the ISO from
            checksum: Optional SHA256 checksum for verification

        Returns:
            Task information including task ID (UPID)

        Raises:
            Exception: If download initiation fails
        """
        try:
            proxmox = self._get_connection()

            # Prepare parameters for download-url API
            params = {
                'content': 'iso',
                'filename': filename,
                'url': url
            }

            # Add checksum verification if provided
            if checksum:
                params['checksum'] = checksum
                params['checksum-algorithm'] = 'sha256'

            # Initiate download task
            task_id = proxmox.nodes(node).storage(storage).post('download-url', **params)

            logger.info(f"Initiated ISO download from URL to {storage} on node {node}: {filename}")
            return {
                "task_id": task_id,
                "status": "downloading",
                "node": node,
                "storage": storage,
                "filename": filename
            }

        except Exception as e:
            logger.error(f"Failed to initiate ISO download from URL for {filename}: {e}")
            raise

    def get_task_status(self, node: str, task_id: str) -> Dict[str, Any]:
        """
        Get the status of a Proxmox task (UPID).

        Args:
            node: Node name where the task is running
            task_id: Task ID (UPID format)

        Returns:
            Dict containing task status information:
            - status: 'running', 'stopped'
            - exitstatus: 'OK' if successful, error message if failed
            - type: task type
            - node: node name
            - upid: task UPID

        Raises:
            Exception: If task status check fails
        """
        try:
            proxmox = self._get_connection()

            # Get task status
            task_status = proxmox.nodes(node).tasks(task_id).status.get()

            logger.debug(f"Task {task_id} status: {task_status.get('status')}")
            return task_status

        except Exception as e:
            logger.error(f"Failed to get task status for {task_id}: {e}")
            raise

    def delete_iso(self, node: str, volid: str) -> Dict[str, Any]:
        """
        Delete an ISO file from Proxmox storage.

        Args:
            node: Node name
            volid: Volume ID (format: storage:iso/filename.iso)

        Returns:
            Task information
        """
        try:
            proxmox = self._get_connection()

            # Parse volid to get storage and volume
            storage, volume = volid.split(':', 1)

            task = proxmox.nodes(node).storage(storage).content(volid).delete()
            logger.info(f"Deleted ISO {volid} from node {node}")
            return {"task_id": task, "status": "deleted"}
        except Exception as e:
            logger.error(f"Failed to delete ISO {volid} from node {node}: {e}")
            raise

    # ===== Multi-Disk VM Creation Methods =====

    def create_vm_base(
        self,
        node: str,
        vmid: int,
        name: str,
        cores: int,
        memory: int,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create a base VM without disks.
        Disks can be added later using set_vm_config.

        Args:
            node: Node name where VM should be created
            vmid: VM ID
            name: VM name
            cores: Number of CPU cores
            memory: Memory in MB
            **kwargs: Additional VM configuration options

        Returns:
            Task ID and status information
        """
        try:
            proxmox = self._get_connection()

            # Base configuration without disks
            config = {
                "vmid": vmid,
                "name": name,
                "cores": cores,
                "memory": memory,
                "sockets": kwargs.get("sockets", 1),
                "ostype": kwargs.get("ostype", "l26"),
                "net0": kwargs.get("net0", "virtio,bridge=vmbr0"),
            }

            # Add any additional configuration
            config.update({k: v for k, v in kwargs.items() if k not in config})

            # Create VM
            logger.info(f"Creating base VM {vmid} ({name}) on node {node}")
            task = proxmox.nodes(node).qemu.create(**config)

            return {
                "task_id": task,
                "vmid": vmid,
                "node": node,
                "status": "creating"
            }

        except ResourceException as e:
            logger.error(f"Failed to create base VM {vmid}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating base VM {vmid}: {e}")
            raise

    def set_vm_config(self, node: str, vmid: int, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Set VM configuration parameters (e.g., add disks, change settings).

        Args:
            node: Node name where VM is located
            vmid: VM ID
            config: Configuration parameters to set

        Returns:
            Task or success status

        Example:
            # Add a disk
            set_vm_config(node, vmid, {"scsi0": "local-lvm:40"})

            # Mount an ISO
            set_vm_config(node, vmid, {"ide2": "local:iso/ubuntu-22.04.iso,media=cdrom"})

            # Set boot order
            set_vm_config(node, vmid, {"boot": "order=ide2;scsi0"})
        """
        try:
            proxmox = self._get_connection()
            result = proxmox.nodes(node).qemu(vmid).config.put(**config)
            logger.info(f"Updated VM {vmid} config on node {node}: {config}")
            return {"status": "updated", "result": result}
        except Exception as e:
            logger.error(f"Failed to set VM {vmid} config on node {node}: {e}")
            raise

    def add_disk_to_vm(
        self,
        node: str,
        vmid: int,
        disk_interface: str,
        disk_number: int,
        storage: str,
        size_gb: int,
        disk_format: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Add a disk to an existing VM.

        Args:
            node: Node name
            vmid: VM ID
            disk_interface: Disk interface (scsi, ide, virtio, sata)
            disk_number: Disk number (0, 1, 2, ...)
            storage: Storage pool name
            size_gb: Disk size in GB
            disk_format: Disk format (raw, qcow2) - optional

        Returns:
            Task or success status
        """
        disk_key = f"{disk_interface}{disk_number}"

        # Format: storage:size or storage:size,format=raw
        if disk_format:
            disk_value = f"{storage}:{size_gb},format={disk_format}"
        else:
            disk_value = f"{storage}:{size_gb}"

        config = {disk_key: disk_value}

        logger.info(f"Adding disk {disk_key} to VM {vmid}: {disk_value}")
        return self.set_vm_config(node, vmid, config)

    def mount_iso_to_vm(
        self,
        node: str,
        vmid: int,
        iso_volid: str,
        disk_interface: str = "ide",
        disk_number: int = 2
    ) -> Dict[str, Any]:
        """
        Mount an ISO file to a VM as a CD-ROM device.

        Args:
            node: Node name
            vmid: VM ID
            iso_volid: ISO volume ID (format: storage:iso/filename.iso)
            disk_interface: Disk interface (default: ide)
            disk_number: Disk number (default: 2 for ide2)

        Returns:
            Task or success status
        """
        disk_key = f"{disk_interface}{disk_number}"
        disk_value = f"{iso_volid},media=cdrom"

        config = {disk_key: disk_value}

        logger.info(f"Mounting ISO {iso_volid} to VM {vmid} as {disk_key}")
        return self.set_vm_config(node, vmid, config)

    def detach_disk_from_vm(
        self,
        node: str,
        vmid: int,
        disk_interface: str,
        disk_number: int
    ) -> Dict[str, Any]:
        """
        Detach/remove a disk from a VM.

        Args:
            node: Node name
            vmid: VM ID
            disk_interface: Disk interface (scsi, ide, virtio, sata)
            disk_number: Disk number

        Returns:
            Task or success status
        """
        disk_key = f"{disk_interface}{disk_number}"
        # Use delete parameter to remove the disk
        config = {"delete": disk_key}

        logger.info(f"Detaching disk {disk_key} from VM {vmid}")
        return self.set_vm_config(node, vmid, config)

    def unmount_iso_from_vm(
        self,
        node: str,
        vmid: int,
        disk_interface: str = "ide",
        disk_number: int = 2
    ) -> Dict[str, Any]:
        """
        Unmount an ISO file from a VM's CD-ROM device.

        Args:
            node: Node name
            vmid: VM ID
            disk_interface: Disk interface (default: ide)
            disk_number: Disk number (default: 2 for ide2)

        Returns:
            Task or success status
        """
        disk_key = f"{disk_interface}{disk_number}"
        # Setting to "none" unmounts the ISO
        config = {disk_key: "none,media=cdrom"}

        logger.info(f"Unmounting ISO from VM {vmid} at {disk_key}")
        return self.set_vm_config(node, vmid, config)

    def resize_disk(
        self,
        node: str,
        vmid: int,
        disk_interface: str,
        disk_number: int,
        new_size_gb: int
    ) -> Dict[str, Any]:
        """
        Resize a VM disk to a larger size.

        Args:
            node: Node name
            vmid: VM ID
            disk_interface: Disk interface (scsi, ide, virtio, sata)
            disk_number: Disk number
            new_size_gb: New disk size in GB (must be larger than current)

        Returns:
            Task or success status
        """
        disk_key = f"{disk_interface}{disk_number}"

        # Size must be specified with unit (e.g., "100G")
        size_value = f"{new_size_gb}G"

        logger.info(f"Resizing disk {disk_key} on VM {vmid} to {new_size_gb}GB")

        try:
            proxmox = self._get_connection()
            result = proxmox.nodes(node).qemu(vmid).resize.put(
                disk=disk_key,
                size=size_value
            )
            logger.info(f"Successfully resized disk {disk_key} on VM {vmid}")
            return {"status": "resized", "result": result}
        except Exception as e:
            logger.error(f"Failed to resize disk {disk_key} on VM {vmid}: {e}")
            raise

    def set_boot_order(self, node: str, vmid: int, boot_order: List[str]) -> Dict[str, Any]:
        """
        Set boot order for a VM.

        Args:
            node: Node name
            vmid: VM ID
            boot_order: List of boot devices (e.g., ['ide2', 'scsi0'])

        Returns:
            Task or success status
        """
        boot_value = f"order={';'.join(boot_order)}"
        config = {"boot": boot_value}

        logger.info(f"Setting boot order for VM {vmid}: {boot_value}")
        return self.set_vm_config(node, vmid, config)

    # Snapshot Management Methods

    def create_snapshot(
        self,
        node: str,
        vmid: int,
        snapshot_name: str,
        description: Optional[str] = None,
        include_memory: bool = False
    ) -> Dict[str, Any]:
        """
        Create a snapshot of a VM.

        Args:
            node: Node name
            vmid: VM ID
            snapshot_name: Name for the snapshot
            description: Optional description
            include_memory: Include VM memory state (for running VMs)

        Returns:
            Task or success status
        """
        try:
            proxmox = self._get_connection()

            params = {
                "snapname": snapshot_name
            }

            if description:
                params["description"] = description

            if include_memory:
                params["vmstate"] = 1

            result = proxmox.nodes(node).qemu(vmid).snapshot.post(**params)

            logger.info(f"Created snapshot '{snapshot_name}' for VM {vmid}")
            return {"status": "created", "result": result, "snapshot_name": snapshot_name}
        except Exception as e:
            logger.error(f"Failed to create snapshot for VM {vmid}: {e}")
            raise

    def list_snapshots(self, node: str, vmid: int) -> List[Dict[str, Any]]:
        """
        List all snapshots for a VM.

        Args:
            node: Node name
            vmid: VM ID

        Returns:
            List of snapshot information
        """
        try:
            proxmox = self._get_connection()
            snapshots = proxmox.nodes(node).qemu(vmid).snapshot.get()

            logger.info(f"Listed {len(snapshots)} snapshots for VM {vmid}")
            return snapshots
        except Exception as e:
            logger.error(f"Failed to list snapshots for VM {vmid}: {e}")
            raise

    def rollback_snapshot(
        self,
        node: str,
        vmid: int,
        snapshot_name: str
    ) -> Dict[str, Any]:
        """
        Rollback VM to a specific snapshot.

        Args:
            node: Node name
            vmid: VM ID
            snapshot_name: Name of snapshot to rollback to

        Returns:
            Task or success status
        """
        try:
            proxmox = self._get_connection()
            result = proxmox.nodes(node).qemu(vmid).snapshot(snapshot_name).rollback.post()

            logger.info(f"Rolled back VM {vmid} to snapshot '{snapshot_name}'")
            return {"status": "rolled_back", "result": result, "snapshot_name": snapshot_name}
        except Exception as e:
            logger.error(f"Failed to rollback VM {vmid} to snapshot '{snapshot_name}': {e}")
            raise

    def delete_snapshot(
        self,
        node: str,
        vmid: int,
        snapshot_name: str
    ) -> Dict[str, Any]:
        """
        Delete a VM snapshot.

        Args:
            node: Node name
            vmid: VM ID
            snapshot_name: Name of snapshot to delete

        Returns:
            Task or success status
        """
        try:
            proxmox = self._get_connection()
            result = proxmox.nodes(node).qemu(vmid).snapshot(snapshot_name).delete()

            logger.info(f"Deleted snapshot '{snapshot_name}' from VM {vmid}")
            return {"status": "deleted", "result": result, "snapshot_name": snapshot_name}
        except Exception as e:
            logger.error(f"Failed to delete snapshot '{snapshot_name}' from VM {vmid}: {e}")
            raise

    # VM Control Methods

    def force_stop_vm(self, node: str, vmid: int) -> Dict[str, Any]:
        """
        Force stop a VM immediately (hard stop).

        This immediately stops the VM process without graceful shutdown.

        Args:
            node: Node name
            vmid: VM ID

        Returns:
            Task or success status
        """
        try:
            proxmox = self._get_connection()
            result = proxmox.nodes(node).qemu(vmid).status.stop.post()

            logger.info(f"Force stopped VM {vmid}")
            return {"status": "force_stopped", "result": result}
        except Exception as e:
            logger.error(f"Failed to force stop VM {vmid}: {e}")
            raise

    def reboot_vm(self, node: str, vmid: int) -> Dict[str, Any]:
        """
        Reboot a VM.

        Args:
            node: Node name
            vmid: VM ID

        Returns:
            Task or success status
        """
        try:
            proxmox = self._get_connection()
            result = proxmox.nodes(node).qemu(vmid).status.reboot.post()

            logger.info(f"Rebooted VM {vmid}")
            return {"status": "rebooted", "result": result}
        except Exception as e:
            logger.error(f"Failed to reboot VM {vmid}: {e}")
            raise

    def reset_vm(self, node: str, vmid: int) -> Dict[str, Any]:
        """
        Reset a VM (hard reset, like pressing reset button).

        Args:
            node: Node name
            vmid: VM ID

        Returns:
            Task or success status
        """
        try:
            proxmox = self._get_connection()
            result = proxmox.nodes(node).qemu(vmid).status.reset.post()

            logger.info(f"Reset VM {vmid}")
            return {"status": "reset", "result": result}
        except Exception as e:
            logger.error(f"Failed to reset VM {vmid}: {e}")
            raise

    def resize_vm(
        self,
        node: str,
        vmid: int,
        cpu_cores: Optional[int] = None,
        cpu_sockets: Optional[int] = None,
        memory_mb: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Resize VM CPU and/or memory.

        Args:
            node: Node name
            vmid: VM ID
            cpu_cores: Number of CPU cores
            cpu_sockets: Number of CPU sockets
            memory_mb: Memory in MB

        Returns:
            Task or success status
        """
        try:
            config = {}

            if cpu_cores is not None:
                config["cores"] = cpu_cores

            if cpu_sockets is not None:
                config["sockets"] = cpu_sockets

            if memory_mb is not None:
                config["memory"] = memory_mb

            if not config:
                raise ValueError("At least one resource (CPU or memory) must be specified")

            logger.info(f"Resizing VM {vmid} with config: {config}")
            return self.set_vm_config(node, vmid, config)
        except Exception as e:
            logger.error(f"Failed to resize VM {vmid}: {e}")
            raise

    def build_network_config(
        self,
        interface_name: str,
        vlan_id: Optional[int] = None,
        bridge: str = "vmbr0",
        model: str = "virtio",
        mac_address: Optional[str] = None,
        firewall: bool = True,
        rate_limit: Optional[int] = None
    ) -> str:
        """Build Proxmox network interface configuration string.

        Creates network configuration with optional VLAN tagging for VPC network isolation.

        Args:
            interface_name: Interface name (net0, net1, net2, net3)
            vlan_id: Optional VLAN ID for network isolation (100-4094)
            bridge: Bridge name (default: vmbr0)
            model: NIC model (virtio, e1000, rtl8139)
            mac_address: Optional MAC address (auto-generated if None)
            firewall: Enable Proxmox firewall on interface
            rate_limit: Optional rate limit in MB/s

        Returns:
            Proxmox network config string

        Examples:
            >>> # Without VLAN (legacy/untagged)
            >>> build_network_config("net0")
            'virtio,bridge=vmbr0,firewall=1'

            >>> # With VLAN tagging for VPC isolation
            >>> build_network_config("net0", vlan_id=100, bridge="vmbr0")
            'virtio,bridge=vmbr0,tag=100,firewall=1'

            >>> # With custom MAC and rate limit
            >>> build_network_config("net1", vlan_id=200, mac_address="AA:BB:CC:DD:EE:FF", rate_limit=100)
            'virtio=AA:BB:CC:DD:EE:FF,bridge=vmbr0,tag=200,firewall=1,rate=100'
        """
        # Start with model
        config_parts = [model]

        # Add MAC address if specified
        if mac_address:
            config_parts[0] = f"{model}={mac_address}"

        # Add bridge (required)
        config_parts.append(f"bridge={bridge}")

        # Add VLAN tag if specified
        if vlan_id is not None:
            if not (1 <= vlan_id <= 4094):
                raise ValueError(f"VLAN ID must be between 1 and 4094, got {vlan_id}")
            config_parts.append(f"tag={vlan_id}")

        # Add firewall setting
        if firewall:
            config_parts.append("firewall=1")
        else:
            config_parts.append("firewall=0")

        # Add rate limit if specified
        if rate_limit is not None:
            config_parts.append(f"rate={rate_limit}")

        config_string = ",".join(config_parts)

        logger.debug(
            f"Built network config for {interface_name}: {config_string} "
            f"(VLAN: {vlan_id if vlan_id else 'untagged'})"
        )

        return config_string

    def attach_network_to_vm(
        self,
        node: str,
        vmid: int,
        interface_name: str,
        vlan_id: Optional[int] = None,
        bridge: str = "vmbr0",
        model: str = "virtio",
        mac_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """Attach network interface to VM with optional VLAN tagging.

        Args:
            node: Node name
            vmid: VM ID
            interface_name: Interface name (net0, net1, net2, net3)
            vlan_id: Optional VLAN ID for network isolation
            bridge: Bridge name
            model: NIC model
            mac_address: Optional MAC address

        Returns:
            Configuration result

        Example:
            >>> proxmox_service.attach_network_to_vm(
            ...     node="pve1",
            ...     vmid=100,
            ...     interface_name="net1",
            ...     vlan_id=100,
            ...     bridge="vmbr0"
            ... )
        """
        # Build network configuration
        net_config = self.build_network_config(
            interface_name=interface_name,
            vlan_id=vlan_id,
            bridge=bridge,
            model=model,
            mac_address=mac_address
        )

        # Apply configuration to VM
        config = {interface_name: net_config}
        result = self.set_vm_config(node, vmid, config)

        logger.info(
            f"Attached network interface {interface_name} to VM {vmid} "
            f"with VLAN {vlan_id} on bridge {bridge}"
        )

        return result

    def detach_network_from_vm(
        self,
        node: str,
        vmid: int,
        interface_name: str
    ) -> Dict[str, Any]:
        """Detach network interface from VM.

        Args:
            node: Node name
            vmid: VM ID
            interface_name: Interface name (net0, net1, net2, net3)

        Returns:
            Configuration result

        Example:
            >>> proxmox_service.detach_network_from_vm("pve1", 100, "net1")
        """
        # Set interface to empty string to delete it
        config = {interface_name: ""}
        result = self.set_vm_config(node, vmid, config)

        logger.info(f"Detached network interface {interface_name} from VM {vmid}")

        return result
