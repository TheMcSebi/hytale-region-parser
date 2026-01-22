#!/usr/bin/env python3
"""
Example: Container Contents Summary

This example parses all containers (chests, barrels, etc.) from region files
and prints a comprehensive summary of all items found across all containers.
"""

from collections import defaultdict
import os
from pathlib import Path
from typing import Dict, List, Any
from hytale_region_parser import RegionFileParser


def parse_region_containers(region_path: Path) -> List[Dict[str, Any]]:
    """Parse all containers from a single region file."""
    containers = []
    
    with RegionFileParser(region_path) as parser:
        for chunk in parser.iter_chunks():
            chunk_base_x = chunk.chunk_x * 32
            chunk_base_z = chunk.chunk_z * 32
            
            for container in chunk.containers:
                local_x, y, local_z = container.position
                world_x = chunk_base_x + local_x
                world_z = chunk_base_z + local_z
                
                containers.append({
                    "position": (world_x, y, world_z),
                    "capacity": container.capacity,
                    "items": container.items,
                    "custom_name": container.custom_name,
                    "who_placed_uuid": container.who_placed_uuid,
                    "region": (parser.region_x, parser.region_z)
                })
    
    return containers


def summarize_containers(containers: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate a summary of all container contents."""
    # Item statistics
    item_counts: Dict[str, int] = defaultdict(int)
    item_total_amounts: Dict[str, int] = defaultdict(int)
    
    # Container statistics
    total_containers = len(containers)
    empty_containers = 0
    named_containers = 0
    items_by_container: Dict[str, int] = defaultdict(int)
    
    for container in containers:
        items = container["items"]
        
        if not items:
            empty_containers += 1
            continue
        
        if container["custom_name"]:
            named_containers += 1
        
        for item in items:
            # Extract item name - structure may vary
            item_name = item.get("item", item.get("name", item.get("type", "Unknown")))
            if isinstance(item_name, dict):
                item_name = item_name.get("name", str(item_name))
            
            # Extract amount
            amount = item.get("amount", item.get("count", 1))
            
            item_counts[item_name] += 1  # Count of stacks
            item_total_amounts[item_name] += amount  # Total quantity
            items_by_container[item_name] += 1
    
    return {
        "total_containers": total_containers,
        "empty_containers": empty_containers,
        "containers_with_items": total_containers - empty_containers,
        "named_containers": named_containers,
        "unique_item_types": len(item_counts),
        "item_counts": dict(item_counts),
        "item_total_amounts": dict(item_total_amounts)
    }


def main():
    # Option 1: Parse a single region file
    appdata = os.getenv('APPDATA')
    region_path = Path(appdata + r'\Hytale\UserData\Saves\Server\universe\worlds\default\chunks\0.0.region.bin')
    
    # Option 2: Parse all region files in a chunks folder
    # chunks_folder = Path(appdata + r"\Hytale\UserData\Saves\Server\universe\worlds\default\chunks")
    # region_files = list(chunks_folder.glob("*.region.bin"))
    
    print("=" * 70)
    print("CONTAINER CONTENTS SUMMARY")
    print("=" * 70)
    
    all_containers = []
    
    # Parse single file
    if region_path.exists():
        print(f"\nParsing: {region_path.name}")
        containers = parse_region_containers(region_path)
        all_containers.extend(containers)
        print(f"  Found {len(containers)} containers")
    else:
        print(f"Error: Region file not found at {region_path}")
        print("Please update the 'region_path' variable to point to a valid .region.bin file")
        print()
        print("Alternatively, uncomment the chunks_folder option to parse all region files.")
        return
    
    # Uncomment this to parse multiple region files:
    # for region_file in region_files:
    #     print(f"\nParsing: {region_file.name}")
    #     containers = parse_region_containers(region_file)
    #     all_containers.extend(containers)
    #     print(f"  Found {len(containers)} containers")
    
    if not all_containers:
        print("\nNo containers found in the parsed region(s).")
        return
    
    # Generate and print summary
    summary = summarize_containers(all_containers)
    
    print()
    print("-" * 70)
    print("CONTAINER STATISTICS")
    print("-" * 70)
    print(f"  Total containers found:     {summary['total_containers']:>8}")
    print(f"  Containers with items:      {summary['containers_with_items']:>8}")
    print(f"  Empty containers:           {summary['empty_containers']:>8}")
    print(f"  Named containers:           {summary['named_containers']:>8}")
    print(f"  Unique item types:          {summary['unique_item_types']:>8}")
    
    print()
    print("-" * 70)
    print("ITEM SUMMARY (sorted by total quantity)")
    print("-" * 70)
    print(f"{'Item Name':<40} {'Stacks':>10} {'Total Qty':>12}")
    print("-" * 70)
    
    # Sort by total amount
    sorted_items = sorted(
        summary['item_total_amounts'].items(),
        key=lambda x: -x[1]
    )
    
    for item_name, total in sorted_items[:30]:
        stacks = summary['item_counts'][item_name]
        print(f"  {item_name:<38} {stacks:>10} {total:>12,}")
    
    if len(sorted_items) > 30:
        print(f"  ... and {len(sorted_items) - 30} more item types")
    
    # Print detailed container list
    print()
    print("-" * 70)
    print("CONTAINER DETAILS (first 15)")
    print("-" * 70)
    
    for i, container in enumerate(all_containers[:15], 1):
        pos = container["position"]
        region = container["region"]
        name = container["custom_name"] or "Unnamed"
        item_count = len(container["items"])
        capacity = container["capacity"]
        
        print(f"\n{i}. {name}")
        print(f"   Position: ({pos[0]}, {pos[1]}, {pos[2]}) in region ({region[0]}, {region[1]})")
        print(f"   Capacity: {capacity} slots, {item_count} item stacks")
        
        if container["items"]:
            print("   Contents:")
            for item in container["items"][:5]:
                item_name = item.get("item", item.get("name", "Unknown"))
                if isinstance(item_name, dict):
                    item_name = item_name.get("name", str(item_name))
                amount = item.get("amount", item.get("count", 1))
                print(f"     - {item_name}: {amount}")
            
            if len(container["items"]) > 5:
                print(f"     ... and {len(container['items']) - 5} more items")
    
    if len(all_containers) > 15:
        print(f"\n... and {len(all_containers) - 15} more containers")
    
    print()
    print("Done!")


if __name__ == "__main__":
    main()
