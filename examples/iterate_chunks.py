#!/usr/bin/env python3
"""
Example: Iterating Over Chunks

This example demonstrates how to iterate over individual chunks in a region file
for custom processing, without loading all data into memory at once.
"""

import os
from pathlib import Path
from hytale_region_parser import RegionFileParser


def main():
    # Update this path to point to your region file
    appdata = os.getenv('APPDATA')
    region_path = Path(appdata + r'\Hytale\UserData\Saves\Server\universe\worlds\default\chunks\0.0.region.bin')
    
    if not region_path.exists():
        print(f"Error: Region file not found at {region_path}")
        print("Please update the 'region_path' variable to point to a valid .region.bin file")
        return
    
    # Using context manager (recommended)
    with RegionFileParser(region_path) as parser:
        print("=" * 60)
        print("CHUNK ITERATION EXAMPLE")
        print("=" * 60)
        print(f"Region: ({parser.region_x}, {parser.region_z})")
        print(f"Total chunk slots: {len(parser.storage.blob_indexes)}")
        print(f"Chunks with data: {parser.get_chunk_count()}")
        print()
        
        # Iterate over all chunks
        for chunk_num, chunk in enumerate(parser.iter_chunks(), 1):
            # Calculate world coordinates
            world_x_start = chunk.chunk_x * 32
            world_z_start = chunk.chunk_z * 32
            world_x_end = world_x_start + 31
            world_z_end = world_z_start + 31
            
            print(f"Chunk {chunk_num}: ({chunk.chunk_x}, {chunk.chunk_z})")
            print(f"  World X: {world_x_start} to {world_x_end}")
            print(f"  World Z: {world_z_start} to {world_z_end}")
            print(f"  Sections: {len(chunk.sections)}")
            print(f"  Unique block types: {len(chunk.block_names)}")
            print(f"  Containers: {len(chunk.containers)}")
            print(f"  Block components: {len(chunk.block_components)}")
            
            # Show some block types
            if chunk.block_names:
                block_list = sorted(chunk.block_names)[:5]
                print(f"  Sample blocks: {', '.join(block_list)}")
            
            print()
            
            # Limit output for large regions
            if chunk_num >= 10:
                remaining = parser.get_chunk_count() - chunk_num
                if remaining > 0:
                    print(f"... and {remaining} more chunks")
                break
    
    print("Done!")


if __name__ == "__main__":
    main()
