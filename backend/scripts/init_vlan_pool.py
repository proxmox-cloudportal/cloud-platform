#!/usr/bin/env python3
"""Initialize VLAN pool with VLANs 100-4094.

Run this script after running the Phase 3 database migration.

Usage:
    python scripts/init_vlan_pool.py
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.session import AsyncSessionLocal
from app.services.vlan_service import VLANService


async def initialize_vlan_pool():
    """Initialize VLAN pool."""
    print("Initializing VLAN pool...")
    print(f"Creating VLANs 100-4094 (3,995 total)")

    async with AsyncSessionLocal() as db:
        vlan_service = VLANService(db)

        try:
            count = await vlan_service.initialize_vlan_pool()

            if count > 0:
                print(f"✓ Successfully created {count} VLAN entries")

                # Get pool stats
                stats = await vlan_service.get_pool_stats()
                print(f"\nVLAN Pool Statistics:")
                print(f"  Total VLANs:     {stats['total']}")
                print(f"  Available:       {stats['available']}")
                print(f"  Allocated:       {stats['allocated']}")
                print(f"  VLAN Range:      {stats['vlan_range']}")
                print(f"  Utilization:     {stats['utilization_percent']:.2f}%")
            else:
                print("VLAN pool already initialized")

                # Show current stats
                stats = await vlan_service.get_pool_stats()
                print(f"\nCurrent VLAN Pool Statistics:")
                print(f"  Total VLANs:     {stats['total']}")
                print(f"  Available:       {stats['available']}")
                print(f"  Allocated:       {stats['allocated']}")
                print(f"  VLAN Range:      {stats['vlan_range']}")
                print(f"  Utilization:     {stats['utilization_percent']:.2f}%")

        except Exception as e:
            print(f"✗ Error initializing VLAN pool: {e}")
            raise


def main():
    """Main entry point."""
    try:
        asyncio.run(initialize_vlan_pool())
        print("\n✓ VLAN pool initialization complete")
        return 0
    except KeyboardInterrupt:
        print("\n✗ Interrupted by user")
        return 1
    except Exception as e:
        print(f"\n✗ Failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
