#!/usr/bin/env python3
"""
Example: Ore Distribution Analysis

This example analyzes the distribution of all Ore_* blocks within a 3x3 area
of chunks around specified world coordinates. It displays statistics about
ore occurrence by type and Y-level.

Install requirements with:
pip install numpy plotly
"""

import json
import math
from collections import defaultdict
import os
from pathlib import Path
import argparse

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import Dict, List, Tuple, Any
from hytale_region_parser import RegionFileParser

INDIVIDUAL_PLOT_HEIGHT = 900
COMBINED_PLOT_HEIGHT = 1260

# Default colors for ore types
ORE_COLORS = {
    "Ore_Adamantite": "#DC143C",   # Red
    "Ore_Thorium": "#228B22",      # Green
    "Ore_Cobalt": "#1E90FF",       # Blue
    "Ore_Iron": "#F5DEB3",         # Beige
    "Ore_Copper": "#FF8C00",       # Orange
    "Ore_Silver": "#C0C0C0",       # Light grey
    "Ore_Gold": "#FFD700"          # Gold
}


def get_ore_color(ore_name: str, index: int = 0, total: int = 1) -> str:
    """Get color for an ore type, falling back to HSL-based color if not defined."""
    if ore_name in ORE_COLORS:
        return ORE_COLORS[ore_name]
    # Fallback to HSL-based color for unknown ores
    return f"hsl({(index * 360 // max(total, 1)) % 360}, 70%, 50%)"

def sanitize_filename(filename: str) -> str:
    """Sanitize a string to be safe for use as a filename."""
    ret = ""
    for c in filename:
        ret += c if c.isalnum() or c in (" ", ".", "_", "-") else "_"
    return ret.strip()

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
        "all_positions": ore_positions,  # All positions for 3D plotting
        "sample_positions": ore_positions[:100]  # Limited for text output
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
    print()

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
                marker_color=get_ore_color(ore_name, idx, num_ores)
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
        height=400 * num_ores,
        showlegend=False
    )
    
    # Save to HTML
    fig.write_html(output_path)
    print(f"Plot saved to: {output_path}")


def plot_ore_distribution_3d(
    results: Dict[str, Any], 
    output_path: Path,
    resolution: int = 8
) -> None:
    """
    Create 3D histogram plots of ore distribution.
    
    Args:
        results: Analysis results from analyze_ore_distribution
        output_path: Path to save the HTML file
        resolution: Coordinate divisor for binning (e.g., 8 means /8 resolution)
    """
    ore_counts = results["ore_counts"]
    sample_positions = results.get("all_positions", results["sample_positions"])
    
    if not ore_counts or not sample_positions:
        print("No ore data to plot in 3D.")
        return
    
    # Group positions by ore type
    positions_by_ore: Dict[str, List[Tuple[int, int, int]]] = defaultdict(list)
    for ore_name, x, y, z in sample_positions:
        positions_by_ore[ore_name].append((x, y, z))
    
    # Sort ores by total count (descending)
    sorted_ores = sorted(ore_counts.items(), key=lambda x: -x[1])
    num_ores = len(sorted_ores)
    
    # Create combined 3D scatter plot with all ores (togglable)
    combined_fig = go.Figure()
    
    for idx, (ore_name, total_count) in enumerate(sorted_ores):
        if ore_name not in positions_by_ore:
            continue
        
        positions = positions_by_ore[ore_name]
        if not positions:
            continue
        
        # Bin positions by resolution
        binned_counts: Dict[Tuple[int, int, int], int] = defaultdict(int)
        for x, y, z in positions:
            bin_x = (x // resolution) * resolution
            bin_y = (y // resolution) * resolution
            bin_z = (z // resolution) * resolution
            binned_counts[(bin_x, bin_y, bin_z)] += 1
        
        # Extract coordinates and sizes
        xs = [pos[0] for pos in binned_counts.keys()]
        ys = [pos[1] for pos in binned_counts.keys()]
        zs = [pos[2] for pos in binned_counts.keys()]
        sizes = list(binned_counts.values())
        
        # Normalize sizes for display
        max_size = max(sizes) if sizes else 1
        normalized_sizes = [5 + (s / max_size) * 25 for s in sizes]
        
        color = get_ore_color(ore_name, idx, num_ores)
        
        combined_fig.add_trace(
            go.Scatter3d(
                x=xs,
                y=zs,  # World Z on plotly Y axis
                z=ys,  # World Y (height) on plotly Z axis (vertical)
                mode='markers',
                name=f"{ore_name} ({total_count:,})",
                marker=dict(
                    size=normalized_sizes,
                    color=color,
                    opacity=0.7,
                    line=dict(width=0.5, color='white')
                ),
                hovertemplate=(
                    f"{ore_name}<br>"
                    "X: %{x}<br>"
                    "Y (Height): %{z}<br>"
                    "Z: %{y}<br>"
                    "Count: %{text}<extra></extra>"
                ),
                text=[str(s) for s in sizes]
            )
        )
    
    combined_fig.update_layout(
        title=f"3D Ore Distribution (Resolution: /{resolution}) - Click legend to toggle",
        scene=dict(
            xaxis_title="X (World)",
            yaxis_title="Z (World)",
            zaxis_title="Y (Height)",
            aspectmode='data'
        ),
        height=1260,
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01
        )
    )
    
    # Create individual 3D plots for each ore
    individual_figs = []
    
    for idx, (ore_name, total_count) in enumerate(sorted_ores):
        if ore_name not in positions_by_ore:
            continue
        
        positions = positions_by_ore[ore_name]
        if not positions:
            continue
        
        # Bin positions by resolution
        binned_counts: Dict[Tuple[int, int, int], int] = defaultdict(int)
        for x, y, z in positions:
            bin_x = (x // resolution) * resolution
            bin_y = (y // resolution) * resolution
            bin_z = (z // resolution) * resolution
            binned_counts[(bin_x, bin_y, bin_z)] += 1
        
        xs = [pos[0] for pos in binned_counts.keys()]
        ys = [pos[1] for pos in binned_counts.keys()]
        zs = [pos[2] for pos in binned_counts.keys()]
        sizes = list(binned_counts.values())
        
        max_size = max(sizes) if sizes else 1
        normalized_sizes = [5 + (s / max_size) * 25 for s in sizes]
        
        color = get_ore_color(ore_name, idx, num_ores)
        
        fig = go.Figure()
        fig.add_trace(
            go.Scatter3d(
                x=xs,
                y=zs,  # World Z on plotly Y axis
                z=ys,  # World Y (height) on plotly Z axis (vertical)
                mode='markers',
                name=ore_name,
                marker=dict(
                    size=normalized_sizes,
                    color=color,
                    opacity=0.7,
                    line=dict(width=0.5, color='white')
                ),
                hovertemplate=(
                    f"{ore_name}<br>"
                    "X: %{x}<br>"
                    "Y (Height): %{z}<br>"
                    "Z: %{y}<br>"
                    "Count: %{text}<extra></extra>"
                ),
                text=[str(s) for s in sizes]
            )
        )
        
        fig.update_layout(
            title=f"{ore_name} Distribution (Total: {total_count:,}, Resolution: /{resolution})",
            scene=dict(
                xaxis_title="X (World)",
                yaxis_title="Z (World)",
                zaxis_title="Y (Height)",
                aspectmode='data'
            ),
            height=INDIVIDUAL_PLOT_HEIGHT
        )
        
        individual_figs.append(fig)
    
    # Combine all figures into a single HTML
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>3D Ore Distribution</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1, h2 {{ color: #333; }}
        .plot-container {{ margin-bottom: 40px; }}
        hr {{ margin: 40px 0; border: 1px solid #ddd; }}
    </style>
</head>
<body>
    <h1>3D Ore Distribution Analysis</h1>
    <p>Center: {results['center']}, Area: {results['area_size']}x{results['area_size']} chunks, Resolution: /{resolution}</p>
    
    <h2>Combined View (Click legend to toggle ores)</h2>
    <div class="plot-container" id="combined-plot"></div>
    
    <hr>
    <h2>Individual Ore Distributions</h2>
"""
    
    # Add combined plot
    html_content += f"<script>Plotly.newPlot('combined-plot', {combined_fig.to_json()}.data, {combined_fig.to_json()}.layout);</script>\n"
    
    # Add individual plots
    for i, (fig, (ore_name, _)) in enumerate(zip(individual_figs, sorted_ores)):
        html_content += f"""
    <div class="plot-container" id="plot-{i}"></div>
    <script>Plotly.newPlot('plot-{i}', {fig.to_json()}.data, {fig.to_json()}.layout);</script>
"""
    
    html_content += """
</body>
</html>
"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"3D plot saved to: {output_path}")


def main():
    
    parser = argparse.ArgumentParser()
    # Configuration - update these paths!
    appdata = os.getenv('APPDATA')
    chunks_folder = Path(appdata + r"\Hytale\UserData\Saves\Server\universe\worlds\default\chunks")
    parser.add_argument("--chunks_folder", type=Path, default=chunks_folder, help="Path to the Hytale chunks directory")
    parser.add_argument("--center_x", type=int, default=0, help="Center X coordinate for the analysis")
    parser.add_argument("--center_z", type=int, default=0, help="Center Z coordinate for the analysis")
    parser.add_argument("--area_size", type=int, default=3, help="Area size in chunks (e.g., 3 for 3x3 chunks)")
    parser.add_argument("--plot3d_resolution", type=int, default=8, help="Resolution for the 3D plot")
    parser.add_argument("--output_filename", type=str, default="ore_distribution", help="Output filename for the plots")
    args = parser.parse_args()
    
    chunks_folder = args.chunks_folder
    
    # Center coordinates for the analysis
    center_x = args.center_x
    center_z = args.center_z
    
    # Area size in chunks (3 = 3x3 = 9 chunks = 96x96 blocks area, 9 = 9x9 = 81 chunks = 288x288 blocks area)
    area_size = args.area_size
    
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
    
    output_filename = sanitize_filename(args.output_filename)
    
    # Run analysis
    results = analyze_ore_distribution(chunks_folder, center_x, center_z, area_size, sanitize_names)
    
    # Print report
    print_ore_report(results)
    
    # Write json file
    output_json = Path(__file__).parent / f"{output_filename}.json"
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4)
        print(f"JSON data saved to: {output_json}")
    
    # Generate interactive plot
    output_html = Path(__file__).parent / f"{output_filename}.html"
    plot_ore_distribution(results, output_html)
    
    # Generate 3D distribution plot
    output_3d_html = Path(__file__).parent / f"{output_filename}_3d.html"
    plot_ore_distribution_3d(results, output_3d_html, resolution=args.plot3d_resolution)
    
    print()
    print("Done!")


if __name__ == "__main__":
    main()
