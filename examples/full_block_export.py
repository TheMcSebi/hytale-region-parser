#!/usr/bin/env python3
"""
Example: Full Block Export with Positions

This example demonstrates how to export all block positions from a region file
to a JSON file. This includes the exact world coordinates of every block.

WARNING: This can generate very large files for densely populated regions! For a 30MB binary file the json output in my test was over 2.1GB of json and took about 10 minutes to finish. Use with caution.
"""

import json
import os
from pathlib import Path
from uuid import UUID
from hytale_region_parser import RegionFileParser


class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle UUIDs and bytes."""
    def default(self, obj):
        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, bytes):
            return obj.hex()
        return super().default(obj)


def main():
    appdata = os.getenv('APPDATA')
    region_path = Path(appdata + r'\Hytale\UserData\Saves\Server\universe\worlds\default\chunks\0.0.region.bin')
    
    if not region_path.exists():
        print(f"Error: Region file not found at {region_path}")
        print("Please update the 'region_path' variable to point to a valid .region.bin file")
        return
    
    # Open the region file
    parser = RegionFileParser(region_path)
    parser.open()
    
    try:
        # Get full data with all block positions
        print("Extracting all blocks with positions...")
        print("This may take a while for large regions...")
        result = parser.to_dict(include_all_blocks=True)
        
        # Print metadata
        print()
        print("=" * 60)
        print("EXPORT SUMMARY")
        print("=" * 60)
        meta = result['metadata']
        print(f"Region: ({meta['region_x']}, {meta['region_z']})")
        print(f"Chunks: {meta['chunk_count']}")
        
        # Print block summary
        print()
        print("BLOCK TYPES (top 20):")
        print("-" * 40)
        block_summary = meta['block_summary']
        sorted_blocks = sorted(block_summary.items(), key=lambda x: -x[1])
        for name, count in sorted_blocks[:20]:
            print(f"  {name:35} {count:>12,}")
        
        print(f"Total unique block types: {len(block_summary)}")
        print(f"Total block positions exported: {len(result['blocks']):,}")
        
        # Save to JSON files
        output_pretty = "full_export.json"
        output_compact = "full_export_compact.json"
        
        print()
        print(f"Saving formatted JSON to {output_pretty}...")
        with open(output_pretty, "w") as f:
            json.dump(result, f, indent=2, cls=CustomJSONEncoder)
        
        print(f"Saving compact JSON to {output_compact}...")
        with open(output_compact, "w") as f:
            json.dump(result, f, cls=CustomJSONEncoder)
        
        # Print file sizes
        size_pretty = os.path.getsize(output_pretty) / (1024 * 1024)
        size_compact = os.path.getsize(output_compact) / (1024 * 1024)
        
        print()
        print("OUTPUT FILES:")
        print(f"  {output_pretty}: {size_pretty:.1f} MB")
        print(f"  {output_compact}: {size_compact:.1f} MB")
    
    finally:
        parser.close()
        print()
        print("Done!")


if __name__ == "__main__":
    main()
