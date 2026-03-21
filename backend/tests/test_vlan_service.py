"""Unit tests for VLAN service."""
import pytest
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.vlan_pool import VLANPool
from app.services.vlan_service import VLANService


# Test database setup
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def db_session():
    """Create test database session."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def vlan_service(db_session):
    """Create VLAN service instance."""
    return VLANService(db_session)


@pytest.mark.asyncio
async def test_initialize_vlan_pool(vlan_service):
    """Test VLAN pool initialization."""
    # Initialize pool
    count = await vlan_service.initialize_vlan_pool()

    # Should create 3,995 VLANs (100-4094)
    assert count == 3995

    # Verify pool was created correctly
    stats = await vlan_service.get_pool_stats()
    assert stats["total"] == 3995
    assert stats["available"] == 3995
    assert stats["allocated"] == 0


@pytest.mark.asyncio
async def test_initialize_vlan_pool_idempotent(vlan_service):
    """Test that initializing pool multiple times is safe."""
    # Initialize first time
    count1 = await vlan_service.initialize_vlan_pool()
    assert count1 == 3995

    # Initialize second time (should skip)
    count2 = await vlan_service.initialize_vlan_pool()
    assert count2 == 0

    # Pool should still have 3,995 VLANs
    stats = await vlan_service.get_pool_stats()
    assert stats["total"] == 3995


@pytest.mark.asyncio
async def test_allocate_vlan(vlan_service):
    """Test VLAN allocation."""
    # Initialize pool
    await vlan_service.initialize_vlan_pool()

    # Allocate VLAN
    vlan_id = await vlan_service.allocate_vlan("network-123")

    # Should allocate VLAN 100 (first in pool)
    assert vlan_id == 100

    # Verify VLAN status
    vlan_status = await vlan_service.get_vlan_status(100)
    assert vlan_status is not None
    assert vlan_status.status == "allocated"
    assert vlan_status.allocated_to_network_id == "network-123"
    assert vlan_status.allocated_at is not None


@pytest.mark.asyncio
async def test_allocate_multiple_vlans(vlan_service):
    """Test allocating multiple VLANs sequentially."""
    # Initialize pool
    await vlan_service.initialize_vlan_pool()

    # Allocate 5 VLANs
    vlan_ids = []
    for i in range(5):
        vlan_id = await vlan_service.allocate_vlan(f"network-{i}")
        vlan_ids.append(vlan_id)

    # Should allocate VLANs 100-104 in sequence
    assert vlan_ids == [100, 101, 102, 103, 104]

    # Verify stats
    stats = await vlan_service.get_pool_stats()
    assert stats["available"] == 3990
    assert stats["allocated"] == 5


@pytest.mark.asyncio
async def test_release_vlan(vlan_service):
    """Test VLAN release."""
    # Initialize and allocate
    await vlan_service.initialize_vlan_pool()
    vlan_id = await vlan_service.allocate_vlan("network-123")

    # Release VLAN
    await vlan_service.release_vlan(vlan_id)

    # Verify status
    vlan_status = await vlan_service.get_vlan_status(vlan_id)
    assert vlan_status.status == "available"
    assert vlan_status.allocated_to_network_id is None
    assert vlan_status.allocated_at is None


@pytest.mark.asyncio
async def test_allocate_after_release(vlan_service):
    """Test that released VLANs can be reallocated."""
    # Initialize pool
    await vlan_service.initialize_vlan_pool()

    # Allocate VLANs 100, 101, 102
    vlan1 = await vlan_service.allocate_vlan("network-1")
    vlan2 = await vlan_service.allocate_vlan("network-2")
    vlan3 = await vlan_service.allocate_vlan("network-3")

    assert vlan1 == 100
    assert vlan2 == 101
    assert vlan3 == 102

    # Release VLAN 101
    await vlan_service.release_vlan(101)

    # Next allocation should get VLAN 101 (first available)
    vlan4 = await vlan_service.allocate_vlan("network-4")
    assert vlan4 == 101


@pytest.mark.asyncio
async def test_update_allocation(vlan_service):
    """Test updating VLAN allocation."""
    # Initialize and allocate
    await vlan_service.initialize_vlan_pool()
    vlan_id = await vlan_service.allocate_vlan("pending")

    # Update allocation
    await vlan_service.update_allocation(vlan_id, "network-123")

    # Verify update
    vlan_status = await vlan_service.get_vlan_status(vlan_id)
    assert vlan_status.allocated_to_network_id == "network-123"


@pytest.mark.asyncio
async def test_get_available_vlan_count(vlan_service):
    """Test getting available VLAN count."""
    # Initialize pool
    await vlan_service.initialize_vlan_pool()

    # Initial count
    count = await vlan_service.get_available_vlan_count()
    assert count == 3995

    # Allocate 10 VLANs
    for i in range(10):
        await vlan_service.allocate_vlan(f"network-{i}")

    # Count should decrease
    count = await vlan_service.get_available_vlan_count()
    assert count == 3985


@pytest.mark.asyncio
async def test_get_pool_stats(vlan_service):
    """Test getting pool statistics."""
    # Initialize pool
    await vlan_service.initialize_vlan_pool()

    # Allocate some VLANs
    for i in range(100):
        await vlan_service.allocate_vlan(f"network-{i}")

    # Get stats
    stats = await vlan_service.get_pool_stats()

    assert stats["total"] == 3995
    assert stats["available"] == 3895
    assert stats["allocated"] == 100
    assert stats["reserved"] == 0
    assert abs(stats["utilization_percent"] - 2.5) < 0.1  # ~2.5%
    assert stats["vlan_range"] == "100-4094"


@pytest.mark.asyncio
async def test_vlan_exhaustion(vlan_service):
    """Test handling when VLANs are exhausted."""
    # Create small pool for testing (only 5 VLANs)
    for vlan_id in range(100, 105):
        vlan_entry = VLANPool(vlan_id=vlan_id, status="available")
        vlan_service.db.add(vlan_entry)
    await vlan_service.db.commit()

    # Allocate all VLANs
    for i in range(5):
        await vlan_service.allocate_vlan(f"network-{i}")

    # Next allocation should fail
    with pytest.raises(RuntimeError, match="No available VLANs"):
        await vlan_service.allocate_vlan("network-overflow")


@pytest.mark.asyncio
async def test_release_nonexistent_vlan(vlan_service):
    """Test releasing VLAN that doesn't exist."""
    with pytest.raises(ValueError, match="VLAN .* not found"):
        await vlan_service.release_vlan(9999)


@pytest.mark.asyncio
async def test_update_nonexistent_vlan(vlan_service):
    """Test updating VLAN that doesn't exist."""
    with pytest.raises(ValueError, match="VLAN .* not found"):
        await vlan_service.update_allocation(9999, "network-123")


@pytest.mark.asyncio
async def test_update_unallocated_vlan(vlan_service):
    """Test updating VLAN that is not allocated."""
    # Initialize pool
    await vlan_service.initialize_vlan_pool()

    # Try to update unallocated VLAN
    with pytest.raises(ValueError, match="is not allocated"):
        await vlan_service.update_allocation(100, "network-123")


@pytest.mark.asyncio
async def test_get_vlan_status_nonexistent(vlan_service):
    """Test getting status of nonexistent VLAN."""
    status = await vlan_service.get_vlan_status(9999)
    assert status is None


@pytest.mark.asyncio
async def test_sequential_allocation_order(vlan_service):
    """Test that VLANs are allocated in sequential order."""
    # Initialize pool
    await vlan_service.initialize_vlan_pool()

    # Allocate 100 VLANs
    vlan_ids = []
    for i in range(100):
        vlan_id = await vlan_service.allocate_vlan(f"network-{i}")
        vlan_ids.append(vlan_id)

    # Should be sequential from 100 to 199
    expected = list(range(100, 200))
    assert vlan_ids == expected


@pytest.mark.asyncio
async def test_vlan_range_boundaries(vlan_service):
    """Test VLAN pool respects 100-4094 range."""
    # Initialize pool
    await vlan_service.initialize_vlan_pool()

    # First VLAN should be 100
    first_vlan = await vlan_service.allocate_vlan("network-first")
    assert first_vlan == 100

    # Get VLAN 4094 status (last in range)
    last_vlan_status = await vlan_service.get_vlan_status(4094)
    assert last_vlan_status is not None
    assert last_vlan_status.vlan_id == 4094

    # VLAN 99 should not exist
    vlan_99_status = await vlan_service.get_vlan_status(99)
    assert vlan_99_status is None

    # VLAN 4095 should not exist
    vlan_4095_status = await vlan_service.get_vlan_status(4095)
    assert vlan_4095_status is None
