"""
ISO Image management endpoints for uploading, listing, and managing ISO files.
"""
from typing import List, Optional
from pathlib import Path
import hashlib
import uuid

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    UploadFile,
    File,
    Form,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func

from app.db.session import get_db
from app.models.iso_image import ISOImage
from app.schemas.iso_image import (
    ISOResponse,
    ISOListResponse,
    ISOUpdate,
    ISOUploadInitResponse,
    ISOUploadFromURL,
)
from app.core.deps import get_current_user, OrgContext, RequirePermission
from app.core.rbac import Permission
from app.models.user import User
from app.core.config import settings

router = APIRouter(prefix="/isos", tags=["ISO Images"])


def calculate_file_checksum(file_path: Path) -> str:
    """Calculate SHA256 checksum of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        # Read file in chunks to handle large files
        for byte_block in iter(lambda: f.read(8192), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


@router.post("/upload", response_model=ISOUploadInitResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_iso(
    file: UploadFile = File(..., description="ISO file to upload"),
    name: str = Form(..., description="ISO filename"),
    display_name: str = Form(..., description="Display name"),
    description: Optional[str] = Form(None, description="Description"),
    os_type: Optional[str] = Form(None, description="OS type (linux, windows, etc.)"),
    os_version: Optional[str] = Form(None, description="OS version"),
    architecture: str = Form("x86_64", description="CPU architecture"),
    is_public: bool = Form(False, description="Make ISO public to all organizations"),
    org_context: OrgContext = Depends(RequirePermission(Permission.VM_CREATE)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload an ISO file for VM installation.

    Accepts multipart/form-data with ISO file and metadata.
    The file is saved locally and queued for transfer to Proxmox storage.

    **Permissions Required:** VM_CREATE
    """
    # Validate file extension
    if not file.filename or not file.filename.lower().endswith('.iso'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an ISO image (.iso extension)"
        )

    # Check file size limit (default 10GB)
    max_size_bytes = getattr(settings, 'ISO_MAX_SIZE_GB', 10) * 1024 * 1024 * 1024
    file_size = 0

    # Create upload directory if it doesn't exist
    upload_dir = Path(getattr(settings, 'ISO_UPLOAD_DIR', '/tmp/cloud-platform/iso-uploads'))
    org_upload_dir = upload_dir / str(org_context.org_id)
    org_upload_dir.mkdir(parents=True, exist_ok=True)

    # Generate unique filename
    iso_id = str(uuid.uuid4())
    local_filename = f"{iso_id}_{file.filename}"
    local_path = org_upload_dir / local_filename

    try:
        # Save file locally
        with open(local_path, 'wb') as f:
            while chunk := await file.read(8192):
                file_size += len(chunk)
                if file_size > max_size_bytes:
                    # Clean up partial file
                    local_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File size exceeds maximum allowed size of {max_size_bytes / (1024**3):.1f}GB"
                    )
                f.write(chunk)

        # Calculate checksum
        checksum = calculate_file_checksum(local_path)

        # Check for duplicate ISO by checksum
        result = await db.execute(
            select(ISOImage).where(
                ISOImage.checksum_sha256 == checksum,
                ISOImage.deleted_at.is_(None)
            )
        )
        existing_iso = result.scalar_one_or_none()

        if existing_iso:
            # Clean up uploaded file
            local_path.unlink(missing_ok=True)

            # Check if user has access to existing ISO
            if existing_iso.is_public or existing_iso.organization_id == org_context.org_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"ISO with same content already exists: {existing_iso.display_name} (ID: {existing_iso.id})"
                )
            else:
                # ISO exists but user can't access it - treat as duplicate without revealing details
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="ISO with same content already exists"
                )

        # Create ISO record
        iso_image = ISOImage(
            id=iso_id,
            organization_id=None if is_public else org_context.org_id,
            uploaded_by=current_user.id,
            is_public=is_public,
            name=name,
            display_name=display_name,
            description=description,
            os_type=os_type,
            os_version=os_version,
            architecture=architecture,
            filename=file.filename,
            file_size_bytes=file_size,
            checksum_sha256=checksum,
            storage_backend="local",
            local_path=str(local_path),
            upload_status="processing",
            upload_progress=0.0,
        )

        db.add(iso_image)
        await db.commit()
        await db.refresh(iso_image)

        # TODO: Queue background task to transfer ISO to Proxmox
        # from app.tasks.iso_tasks import transfer_iso_to_proxmox
        # transfer_iso_to_proxmox.delay(iso_id)

        return ISOUploadInitResponse(
            id=iso_id,
            upload_url=None,
            message="ISO upload completed. Processing transfer to Proxmox storage in background."
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Clean up file on error
        if local_path.exists():
            local_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload ISO: {str(e)}"
        )


@router.post("/upload-from-url", response_model=ISOUploadInitResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_iso_from_url(
    iso_data: ISOUploadFromURL,
    org_context: OrgContext = Depends(RequirePermission(Permission.VM_CREATE)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload an ISO file from a URL using Proxmox's built-in download feature.

    This endpoint initiates a download task on Proxmox that fetches the ISO
    directly from the provided URL, which is more efficient than uploading
    through the backend.

    **Permissions Required:** VM_CREATE
    """
    # Validate URL
    if not iso_data.url.startswith(('http://', 'https://', 'ftp://')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL must start with http://, https://, or ftp://"
        )

    # Extract filename from URL or use display_name
    from urllib.parse import urlparse
    parsed_url = urlparse(iso_data.url)
    url_filename = Path(parsed_url.path).name

    if not url_filename or not url_filename.lower().endswith('.iso'):
        # Use sanitized display_name as filename
        sanitized_name = "".join(c for c in iso_data.display_name if c.isalnum() or c in (' ', '-', '_'))
        sanitized_name = sanitized_name.replace(' ', '-')
        url_filename = f"{sanitized_name}.iso"

    # Generate ISO ID
    iso_id = str(uuid.uuid4())

    try:
        # Create ISO record with source_type='url'
        iso_image = ISOImage(
            id=iso_id,
            organization_id=None if iso_data.is_public else org_context.org_id,
            uploaded_by=current_user.id,
            is_public=iso_data.is_public,
            name=url_filename,
            display_name=iso_data.display_name,
            description=iso_data.description,
            os_type=iso_data.os_type,
            os_version=iso_data.os_version,
            architecture=iso_data.architecture,
            filename=url_filename,
            file_size_bytes=0,  # Will be updated after download
            checksum_sha256=f"pending-{iso_id}",  # Use unique temporary value, will be updated after download
            source_url=iso_data.url,
            source_type="url",
            storage_backend="proxmox",
            upload_status="processing",
            download_status="downloading",
            upload_progress=0.0,
        )

        db.add(iso_image)
        await db.commit()
        await db.refresh(iso_image)

        # Queue background task to download ISO from URL via Proxmox
        from app.tasks.iso_tasks import download_iso_from_url
        download_iso_from_url.delay(iso_id)

        return ISOUploadInitResponse(
            id=iso_id,
            upload_url=None,
            message=f"ISO download from URL initiated. Proxmox is fetching the file in background."
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate ISO download from URL: {str(e)}"
        )


@router.get("", response_model=ISOListResponse)
async def list_isos(
    page: int = 1,
    per_page: int = 20,
    include_public: bool = True,
    os_type: Optional[str] = None,
    org_context: OrgContext = Depends(RequirePermission(Permission.VM_READ)),
    db: AsyncSession = Depends(get_db),
):
    """
    List available ISO images.

    Returns organization-specific ISOs and optionally public ISOs.

    **Permissions Required:** VM_READ
    """
    # Build query conditions
    conditions = [ISOImage.deleted_at.is_(None)]

    # Filter by organization or public
    if include_public:
        conditions.append(
            or_(
                ISOImage.organization_id == org_context.org_id,
                ISOImage.is_public == True
            )
        )
    else:
        conditions.append(ISOImage.organization_id == org_context.org_id)

    # Filter by OS type if provided
    if os_type:
        conditions.append(ISOImage.os_type == os_type)

    # Query with pagination
    query = select(ISOImage).where(*conditions).order_by(ISOImage.created_at.desc())

    # Get total count
    count_result = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.scalar_one()

    # Get paginated results
    offset = (page - 1) * per_page
    result = await db.execute(query.offset(offset).limit(per_page))
    isos = list(result.scalars().all())

    return ISOListResponse(
        data=isos,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=(total + per_page - 1) // per_page
    )


@router.get("/{iso_id}", response_model=ISOResponse)
async def get_iso(
    iso_id: str,
    org_context: OrgContext = Depends(RequirePermission(Permission.VM_READ)),
    db: AsyncSession = Depends(get_db),
):
    """
    Get ISO image details.

    **Permissions Required:** VM_READ
    """
    result = await db.execute(
        select(ISOImage).where(
            ISOImage.id == iso_id,
            ISOImage.deleted_at.is_(None)
        )
    )
    iso = result.scalar_one_or_none()

    if not iso:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ISO image not found"
        )

    # Check access permissions
    if not iso.is_public and iso.organization_id != org_context.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this ISO image"
        )

    return iso


@router.patch("/{iso_id}", response_model=ISOResponse)
async def update_iso(
    iso_id: str,
    iso_update: ISOUpdate,
    org_context: OrgContext = Depends(RequirePermission(Permission.ORG_UPDATE)),
    db: AsyncSession = Depends(get_db),
):
    """
    Update ISO image metadata.

    Only the organization that owns the ISO can update it.
    Superadmins can update any ISO.

    **Permissions Required:** ORG_UPDATE
    """
    result = await db.execute(
        select(ISOImage).where(
            ISOImage.id == iso_id,
            ISOImage.deleted_at.is_(None)
        )
    )
    iso = result.scalar_one_or_none()

    if not iso:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ISO image not found"
        )

    # Check ownership (only org that owns the ISO can update it)
    if iso.organization_id != org_context.org_id and not org_context.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owning organization can update this ISO"
        )

    # Update fields
    update_data = iso_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(iso, field, value)

    await db.commit()
    await db.refresh(iso)

    return iso


@router.delete("/{iso_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_iso(
    iso_id: str,
    org_context: OrgContext = Depends(RequirePermission(Permission.ORG_UPDATE)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete an ISO image.

    Soft deletes the ISO record and queues cleanup of storage.

    **Permissions Required:** ORG_UPDATE
    """
    result = await db.execute(
        select(ISOImage).where(
            ISOImage.id == iso_id,
            ISOImage.deleted_at.is_(None)
        )
    )
    iso = result.scalar_one_or_none()

    if not iso:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ISO image not found"
        )

    # Check ownership
    if iso.organization_id != org_context.org_id and not org_context.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owning organization can delete this ISO"
        )

    # Soft delete
    from datetime import datetime
    iso.deleted_at = datetime.utcnow()

    # TODO: Queue background task to clean up ISO from Proxmox and local storage
    # from app.tasks.iso_tasks import cleanup_iso_storage
    # cleanup_iso_storage.delay(iso_id)

    await db.commit()

    return None
