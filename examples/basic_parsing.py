#!/usr/bin/env python3
"""
Example: Basic Region File Parsing

This example demonstrates how to open a region file and print basic metadata
and a summary of all blocks found.
"""

import os
from pathlib import Path
from hytale_region_parser import RegionFileParser


def main():
    # Update this path to point to your region file
    appdata = os.getenv('APPDATA')
    region_path = Path(appdata + r"\Hytale\UserData\Saves\Server\universe\worlds\default\chunks\0.0.region.bin")
    
    if not region_path.exists():
        print(f"Error: Region file not found at {region_path}")
        print("Please update the 'region_path' variable to point to a valid .region.bin file")
        return
    
    # Open the region file
    parser = RegionFileParser(region_path)
    parser.open()
    
    try:
        # Get summary only (fast - doesn't decode individual block positions)
        result = parser.to_dict_summary_only()
        
        # Print metadata
        print("=" * 60)
        print("REGION FILE SUMMARY")
        print("=" * 60)
        meta = result['metadata']
        print(f"Region Coordinates: ({meta['region_x']}, {meta['region_z']})")
        print(f"Chunks with data: {meta['chunk_count']}")
        
        # Print block summary sorted by count
        print()
        print("BLOCK DISTRIBUTION (top 30 by count):")
        print("-" * 40)
        block_summary = result['block_summary']
        sorted_blocks = sorted(block_summary.items(), key=lambda x: -x[1])
        
        total_blocks = sum(count for _, count in sorted_blocks)
        
        for name, count in sorted_blocks[:30]:
            percentage = (count / total_blocks) * 100
            print(f"  {name:40} {count:>10,} ({percentage:5.2f}%)")
        
        if len(sorted_blocks) > 30:
            remaining = len(sorted_blocks) - 30
            print(f"  ... and {remaining} more block types")
        
        print("-" * 40)
        print(f"Total unique block types: {len(block_summary)}")
        print(f"Total non-empty blocks: {total_blocks:,}")
        
        # Print container info
        print()
        print(f"CONTAINERS FOUND: {len(result['containers'])}")
        if result['containers']:
            print("-" * 40)
            for i, container in enumerate(result['containers'][:10], 1):
                pos = container['position']
                name = container.get('custom_name') or 'Unnamed'
                items = container['items_count']
                print(f"  {i}. [{pos[0]:>6}, {pos[1]:>3}, {pos[2]:>6}] - {name} ({items} items)")
            
            if len(result['containers']) > 10:
                print(f"  ... and {len(result['containers']) - 10} more containers")
    
    finally:
        parser.close()
        print()
        print("Done!")


if __name__ == "__main__":
    main()
