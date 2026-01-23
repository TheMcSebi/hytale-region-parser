#!/usr/bin/env python3
"""
Example: Ore Distribution Analysis

This example analyzes the distribution of all Ore_* blocks within a 3x3 area
of chunks around specified world coordinates. It displays statistics about
ore occurrence by type and Y-level.

Install requirements with:
pip install numpy plotly
"""

import math
from collections import defaultdict
import os
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import Dict, List, Tuple, Any
from hytale_region_parser import RegionFileParser


def sanitize_ore_name(name: str) -> str:
    """Strip rock type suffix: Ore_Gold_Volcanic -> Ore_Gold"""
    parts = name.split("_")
    return f"{parts[0]}_{parts[1]}" if len(parts) >= 2 else name


def world_to_chunk_coords(world_x: int, world_z: int) -> Tuple[int, int]:
    """Convert world coordinates to chunk coordinates."""
    chunk_x = world_x // 32
    chunk_z = world_z // 32
    return chunk_x, chunk_z


def chunk_to_region_coords(chunk_x: int, chunk_z: int) -> Tuple[int, int]:
    """Convert chunk coordinates to region coordinates."""
    # Assuming 32 chunks per region (32x32 = 1024 blocks per region axis)
    region_x = chunk_x // 32
    region_z = chunk_z // 32
    return region_x, region_z


def get_region_filename(region_x: int, region_z: int) -> str:
    """Get the filename for a region at given coordinates."""
    return f"{region_x}.{region_z}.region.bin"


def analyze_ore_distribution(
    chunks_folder: Path,
    center_x: int,
    center_z: int,
    area_size: int = 3,
    sanitize_names: bool = False
) -> Dict[str, Any]:
    """
    Analyze ore distribution in a square area of chunks around a center point.
    
    Args:
        chunks_folder: Path to the chunks folder containing region files
        center_x: World X coordinate of the center
        center_z: World Z coordinate of the center
        area_size: Size of the square area in chunks (e.g., 3 for 3x3)
        sanitize_names: Strip rock type from ore name
    
    Returns:
        Dictionary containing ore distribution statistics
    """
    # Calculate chunk range
    center_chunk_x, center_chunk_z = world_to_chunk_coords(center_x, center_z)
    half_size = area_size // 2
    
    chunk_range_x = range(center_chunk_x - half_size, center_chunk_x + half_size + 1)
    chunk_range_z = range(center_chunk_z - half_size, center_chunk_z + half_size + 1)
    
    # Group chunks by region
    region_chunks: Dict[Tuple[int, int], List[Tuple[int, int]]] = defaultdict(list)
    for cx in chunk_range_x:
        for cz in chunk_range_z:
            region = chunk_to_region_coords(cx, cz)
            region_chunks[region].append((cx, cz))
    
    # Ore statistics
    ore_counts: Dict[str, int] = defaultdict(int)
    ore_by_y_level: Dict[str, Dict[int, int]] = defaultdict(lambda: defaultdict(int))
    ore_positions: List[Tuple[str, int, int, int]] = []
    
    chunks_processed = 0
    chunks_found = 0
    
    print(f"\nAnalyzing {area_size}x{area_size} chunk area centered at ({center_x}, {center_z})")
    print(f"Chunk range: X=[{min(chunk_range_x)}, {max(chunk_range_x)}], Z=[{min(chunk_range_z)}, {max(chunk_range_z)}]")
    print(f"Regions to scan: {list(region_chunks.keys())}")
    print()
    
    for (region_x, region_z), target_chunks in region_chunks.items():
        region_file = chunks_folder / get_region_filename(region_x, region_z)
        
        if not region_file.exists():
            print(f"  Region ({region_x}, {region_z}): File not found, skipping")
            continue
        
        print(f"  Scanning region ({region_x}, {region_z})...")
        target_chunk_set = set(target_chunks)
        
        with RegionFileParser(region_file) as parser:
            for chunk in parser.iter_chunks():
                if (chunk.chunk_x, chunk.chunk_z) not in target_chunk_set:
                    continue
                
                chunks_found += 1
                chunk_base_x = chunk.chunk_x * 32
                chunk_base_z = chunk.chunk_z * 32
                
                # Process each section
                for section in chunk.sections:
                    section_base_y = section.section_y * 32
                    
                    # Check block counts for ores
                    for block_name, count in section.block_counts.items():
                        if block_name and block_name.startswith("Ore_"):
                            if sanitize_names:
                                block_name = sanitize_ore_name(block_name)
                            ore_counts[block_name] += count
                    
                    # If we have block indices, get exact positions
                    if section.block_indices and section.block_palette:
                        # Build internal ID -> block name lookup
                        id_to_name = {entry.internal_id: entry.name for entry in section.block_palette}
                        
                        indices = section.block_indices
                        palette_type = section.palette_type
                        
                        # Decode positions based on palette type
                        if palette_type == 1:  # HalfByte
                            for byte_idx, byte_val in enumerate(indices):
                                for nibble_offset in [0, 1]:
                                    block_idx = byte_idx * 2 + nibble_offset
                                    if block_idx >= 32768:
                                        break
                                    
                                    if nibble_offset == 0:
                                        internal_id = byte_val & 0x0F
                                    else:
                                        internal_id = (byte_val >> 4) & 0x0F
                                    
                                    name = id_to_name.get(internal_id, "")
                                    if name.startswith("Ore_"):
                                        if sanitize_names:
                                            name = sanitize_ore_name(name)
                                        local_x = block_idx % 32
                                        local_z = (block_idx // 32) % 32
                                        local_y = block_idx // (32 * 32)
                                        
                                        world_x = chunk_base_x + local_x
                                        world_y = section_base_y + local_y
                                        world_z = chunk_base_z + local_z
                                        
                                        ore_by_y_level[name][world_y] += 1
                                        ore_positions.append((name, world_x, world_y, world_z))
                        
                        elif palette_type == 2:  # Byte
                            for block_idx, internal_id in enumerate(indices):
                                if block_idx >= 32768:
                                    break
                                name = id_to_name.get(internal_id, "")
                                if name.startswith("Ore_"):
                                    if sanitize_names:
                                        name = sanitize_ore_name(name)
                                    local_x = block_idx % 32
                                    local_z = (block_idx // 32) % 32
                                    local_y = block_idx // (32 * 32)
                                    
                                    world_x = chunk_base_x + local_x
                                    world_y = section_base_y + local_y
                                    world_z = chunk_base_z + local_z
                                    
                                    ore_by_y_level[name][world_y] += 1
                                    ore_positions.append((name, world_x, world_y, world_z))
                        
                        elif palette_type == 3:  # Short
                            import struct
                            for i in range(0, min(len(indices), 32768 * 2), 2):
                                block_idx = i // 2
                                if block_idx >= 32768:
                                    break
                                internal_id = struct.unpack('>H', indices[i:i+2])[0]
                                name = id_to_name.get(internal_id, "")
                                if name.startswith("Ore_"):
                                    if sanitize_names:
                                        name = sanitize_ore_name(name)
                                    local_x = block_idx % 32
                                    local_z = (block_idx // 32) % 32
                                    local_y = block_idx // (32 * 32)
                                    
                                    world_x = chunk_base_x + local_x
                                    world_y = section_base_y + local_y
                                    world_z = chunk_base_z + local_z
                                    
                                    ore_by_y_level[name][world_y] += 1
                                    ore_positions.append((name, world_x, world_y, world_z))
        
        chunks_processed += len(target_chunks)
    
    return {
        "center": (center_x, center_z),
        "area_size": area_size,
        "chunks_processed": chunks_processed,
        "chunks_found": chunks_found,
        "ore_counts": dict(ore_counts),
        "ore_by_y_level": {k: dict(v) for k, v in ore_by_y_level.items()},
        "sample_positions": ore_positions[:100]  # Limit to avoid huge output
    }


def print_ore_report(results: Dict[str, Any]) -> None:
    """Print a formatted ore distribution report."""
    print()
    print("=" * 70)
    print("ORE DISTRIBUTION REPORT")
    print("=" * 70)
    print(f"Center coordinates: ({results['center'][0]}, {results['center'][1]})")
    print(f"Area size: {results['area_size']}x{results['area_size']} chunks")
    print(f"Chunks found: {results['chunks_found']} / {results['area_size'] ** 2}")
    
    ore_counts = results["ore_counts"]
    ore_by_y = results["ore_by_y_level"]
    
    if not ore_counts:
        print("\nNo ores found in this area!")
        return
    
    # Total ore counts
    print()
    print("-" * 70)
    print("ORE TOTALS")
    print("-" * 70)
    print(f"{'Ore Type':<35} {'Count':>15} {'Percentage':>12}")
    print("-" * 70)
    
    total_ores = sum(ore_counts.values())
    sorted_ores = sorted(ore_counts.items(), key=lambda x: -x[1])
    
    for ore_name, count in sorted_ores:
        percentage = (count / total_ores) * 100
        print(f"  {ore_name:<33} {count:>15,} {percentage:>10.2f}%")
    
    print("-" * 70)
    print(f"  {'TOTAL':<33} {total_ores:>15,}")
    
    # Y-level distribution for each ore
    print()
    print("-" * 70)
    print("Y-LEVEL DISTRIBUTION")
    print("-" * 70)
    
    for ore_name in sorted_ores:
        ore_name = ore_name[0]
        if ore_name not in ore_by_y:
            continue
        
        y_data = ore_by_y[ore_name]
        if not y_data:
            continue
        
        min_y = min(y_data.keys())
        max_y = max(y_data.keys())
        total = sum(y_data.values())
        
        # Calculate weighted average Y
        weighted_sum = sum(y * count for y, count in y_data.items())
        avg_y = weighted_sum / total if total > 0 else 0
        
        # Find peak Y level
        peak_y = max(y_data.items(), key=lambda x: x[1])[0]
        
        print(f"\n{ore_name}:")
        print(f"  Y range: {min_y} to {max_y}")
        print(f"  Average Y: {avg_y:.1f}")
        print(f"  Peak Y: {peak_y} (most common level)")

        # Create histogram using numpy
        # Expand y_data into array of Y values (weighted by count)
        y_values = np.repeat(list(y_data.keys()), list(y_data.values()))

        # Use numpy histogram with automatic bin detection (Freedman-Diaconis rule)
        counts, bin_edges = np.histogram(y_values, bins='fd')
        
        print("  Distribution by Y-range:")
        max_count = counts.max() if len(counts) > 0 else 1
        for i, count in enumerate(counts):
            if count == 0:
                continue
            range_start = int(bin_edges[i])
            range_end = int(bin_edges[i + 1]) - 1
            bar_length = int((count / max_count) * 30)
            bar = "█" * bar_length
            print(f"    Y {range_start:>4}-{range_end:<4}: {count:>6} {bar}")
    
    # Sample positions
    if results["sample_positions"]:
        print()
        print("-" * 70)
        print("SAMPLE ORE POSITIONS (first 20)")
        print("-" * 70)
        for i, (ore_name, x, y, z) in enumerate(results["sample_positions"][:20], 1):
            print(f"  {i:>2}. {ore_name:<25} at ({x:>6}, {y:>3}, {z:>6})")


def plot_ore_distribution(results: Dict[str, Any], output_path: Path) -> None:
    """Create an interactive plotly chart of ore distribution by Y-level."""
    ore_by_y = results["ore_by_y_level"]
    ore_counts = results["ore_counts"]
    
    if not ore_counts:
        print("No ore data to plot.")
        return
    
    # Sort ores by total count (descending)
    sorted_ores = sorted(ore_counts.items(), key=lambda x: -x[1])
    
    # Create figure with subplots - one row per ore type
    num_ores = len(sorted_ores)
    fig = make_subplots(
        rows=num_ores, 
        cols=1,
        subplot_titles=[f"{name} (total: {count:,})" for name, count in sorted_ores],
        vertical_spacing=0.05
    )
    
    for idx, (ore_name, _) in enumerate(sorted_ores, start=1):
        if ore_name not in ore_by_y:
            continue
        
        y_data = ore_by_y[ore_name]
        if not y_data:
            continue
        
        # Sort by Y level for proper plotting
        sorted_y_data = sorted(y_data.items())
        y_levels = [y for y, _ in sorted_y_data]
        counts = [c for _, c in sorted_y_data]
        
        # Add bar trace for this ore
        fig.add_trace(
            go.Bar(
                x=y_levels,
                y=counts,
                name=ore_name,
                marker_color=f"hsl({(idx * 360 // num_ores) % 360}, 70%, 50%)"
            ),
            row=idx,
            col=1
        )
        
        # Update axes labels
        fig.update_xaxes(title_text="Y Level", row=idx, col=1)
        fig.update_yaxes(title_text="Count", row=idx, col=1)
    
    # Update layout
    fig.update_layout(
        title_text=f"Ore Distribution by Y-Level (Center: {results['center']}, Area: {results['area_size']}x{results['area_size']} chunks)",
        height=300 * num_ores,
        showlegend=False
    )
    
    # Save to HTML
    fig.write_html(output_path)
    print(f"\nPlot saved to: {output_path}")


def main():
    # Configuration - update these paths!
    appdata = os.getenv('APPDATA')
    chunks_folder = Path(appdata + r"\Hytale\UserData\Saves\Server\universe\worlds\default\chunks")
    
    # Center coordinates for the analysis
    center_x = 860
    center_z = -1240
    
    # Area size in chunks (3 = 3x3 = 9 chunks = 96x96 blocks area, 9 = 9x9 = 81 chunks = 288x288 blocks area)
    area_size = 4
    
    # Sanitize names, removing the containing subtype. E.g. "Ore_Gold_Volcanic" becomes "Ore_Gold"
    sanitize_names = True
    
    if not chunks_folder.exists():
        print(f"Error: Chunks folder not found at {chunks_folder}")
        print("Please update the 'chunks_folder' variable to point to your Hytale chunks directory")
        return
    
    print("=" * 70)
    print("ORE DISTRIBUTION ANALYSIS")
    print("=" * 70)
    print(f"Chunks folder: {chunks_folder}")
    
    # Run analysis
    results = analyze_ore_distribution(chunks_folder, center_x, center_z, area_size, sanitize_names)
    
    # Print report
    print_ore_report(results)
    
    # Generate interactive plot
    output_html = Path(__file__).parent / "ore_distribution.html"
    plot_ore_distribution(results, output_html)
    
    print()
    print("Done!")


if __name__ == "__main__":
    main()
