"""
WebSocket proxy for VM console access.

This module provides a WebSocket proxy that allows browser clients to connect
to Proxmox VNC websockets while our backend handles authentication.
"""
import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models.virtual_machine import VirtualMachine
from app.core.deps import get_organization_context, OrgContext, RequirePermission
from app.core.rbac import Role, Permission
from app.services.proxmox_service import ProxmoxService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/console", tags=["Console Proxy"])


@router.get("/{vm_id}", response_class=HTMLResponse)
async def get_console_page(
    vm_id: str,
    org_context: OrgContext = Depends(RequirePermission(Permission.VM_READ)),
    db: AsyncSession = Depends(get_db)
) -> str:
    """
    Serve an HTML page with integrated noVNC console.

    This page uses a WebSocket connection proxied through our backend,
    avoiding cross-domain authentication issues.

    Requires: VM_READ permission
    """
    # Get VM with org check
    query = select(VirtualMachine).where(
        VirtualMachine.id == vm_id,
        VirtualMachine.organization_id == org_context.org_id,
        VirtualMachine.deleted_at.is_(None)
    )

    # Members can only access their own VMs
    if org_context.role == Role.ORG_MEMBER:
        query = query.where(VirtualMachine.owner_id == org_context.user.id)

    result = await db.execute(query)
    vm = result.scalar_one_or_none()

    if not vm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VM not found or access denied"
        )

    # For now, redirect to Proxmox directly with tickets in URL
    # TODO: Implement full WebSocket proxy in future update
    try:
        proxmox_service = ProxmoxService(vm.proxmox_cluster)
        console_info = proxmox_service.get_console_url(vm.proxmox_node, vm.proxmox_vmid)
        proxmox_url = console_info["console_url"]

        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>VM Console - {vm.name}</title>
    <meta http-equiv="refresh" content="0; url={proxmox_url}">
    <style>
        body {{
            font-family: Arial, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            background: #f5f5f5;
        }}
        .message {{
            text-align: center;
            background: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .spinner {{
            border: 4px solid #f3f3f3;
            border-top: 4px solid #3498db;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px;
        }}
        @keyframes spin {{
            0% {{ transform: rotate(0deg); }}
            100% {{ transform: rotate(360deg); }}
        }}
        .note {{
            color: #666;
            margin-top: 20px;
            padding: 15px;
            background: #fff3cd;
            border-radius: 4px;
            border-left: 4px solid #ffc107;
        }}
    </style>
</head>
<body>
    <div class="message">
        <div class="spinner"></div>
        <h2>Connecting to Console...</h2>
        <p>Redirecting to VM console...</p>
        <div class="note">
            <strong>Note:</strong> If the console shows "Error 401: No ticket", please ensure you are logged into
            the Proxmox web interface in another tab first, then try again.
        </div>
        <p style="margin-top: 20px;">
            <a href="{proxmox_url}">Click here if not redirected automatically</a>
        </p>
    </div>
</body>
</html>
        """
        return html_content

    except Exception as e:
        logger.error(f"Failed to get console for VM {vm_id}: {e}")
        error_html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Console Error</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            padding: 40px;
            background: #f5f5f5;
        }}
        .error {{
            background: #fff;
            padding: 30px;
            border-radius: 8px;
            max-width: 600px;
            margin: 0 auto;
            border-left: 4px solid #f44336;
        }}
        h1 {{
            color: #f44336;
        }}
    </style>
</head>
<body>
    <div class="error">
        <h1>Console Access Error</h1>
        <p>Failed to access VM console: {str(e)}</p>
        <p><a href="javascript:window.close()">Close Window</a></p>
    </div>
</body>
</html>
        """
        return error_html
