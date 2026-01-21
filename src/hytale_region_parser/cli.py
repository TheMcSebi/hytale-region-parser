"""
Command-line interface for Hytale Region Parser
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .region_parser import RegionFileParser


def find_region_files(folder: Path) -> List[Path]:
    """Find all .region.bin files in a folder."""
    return list(folder.glob("*.region.bin"))


def detect_folder_structure(input_path: Path) -> Tuple[str, Dict[str, List[Path]]]:
    """
    Detect the folder structure and categorize region files.
    
    Returns:
        Tuple of (structure_type, files_dict) where:
        - structure_type: "universe", "chunks", or "flat"
        - files_dict: Dictionary mapping world names to lists of region files
          For "flat" structure, the key is empty string
    """
    # Check if input is a "chunks" folder directly
    if input_path.name == "chunks":
        region_files = find_region_files(input_path)
        if region_files:
            # Get world name from parent folder
            world_name = input_path.parent.name if input_path.parent != input_path else "world"
            return ("chunks", {world_name: region_files})
    
    # Check if input contains world folders with "chunks" subfolders (universe structure)
    worlds: Dict[str, List[Path]] = {}
    for item in input_path.iterdir():
        if item.is_dir():
            chunks_folder = item / "chunks"
            if chunks_folder.is_dir():
                region_files = find_region_files(chunks_folder)
                if region_files:
                    worlds[item.name] = region_files
    
    if worlds:
        return ("universe", worlds)
    
    # Check if input directly contains region files (flat structure)
    region_files = find_region_files(input_path)
    if region_files:
        return ("flat", {"": region_files})
    
    # No region files found
    return ("empty", {})


def parse_single_file(
    filepath: Path, 
    indent: Optional[int] = 2,
    include_all_blocks: bool = True,
    summary_only: bool = False
) -> Dict[str, Any]:
    """Parse a single region file and return the data dictionary."""
    with RegionFileParser(filepath) as parser:
        if summary_only:
            return parser.to_dict_summary_only()
        return parser.to_dict(include_all_blocks=include_all_blocks)


def parse_multiple_files(
    filepaths: List[Path], 
    indent: Optional[int] = 2, 
    quiet: bool = False,
    include_all_blocks: bool = True,
    summary_only: bool = False
) -> Dict[str, Any]:
    """Parse multiple region files and merge into a single dictionary."""
    if summary_only:
        # For summary mode, aggregate block summaries
        combined_summary: Dict[str, int] = {}
        combined_containers: List[Dict] = []
        total_chunks = 0
        
        for filepath in filepaths:
            if not quiet:
                print(f"Parsing {filepath.name}...", file=sys.stderr)
            try:
                with RegionFileParser(filepath) as parser:
                    data = parser.to_dict_summary_only()
                    total_chunks += data["metadata"]["chunk_count"]
                    for block_name, count in data["block_summary"].items():
                        combined_summary[block_name] = combined_summary.get(block_name, 0) + count
                    combined_containers.extend(data.get("containers", []))
            except Exception as e:
                print(f"Warning: Failed to parse {filepath}: {e}", file=sys.stderr)
        
        return {
            "metadata": {
                "total_chunks": total_chunks,
                "total_region_files": len(filepaths)
            },
            "block_summary": combined_summary,
            "containers": combined_containers
        }
    else:
        # For full mode, merge all blocks
        result: Dict[str, Any] = {
            "metadata": {
                "total_chunks": 0,
                "total_region_files": len(filepaths),
                "block_summary": {}
            },
            "blocks": {}
        }
        
        for filepath in filepaths:
            if not quiet:
                print(f"Parsing {filepath.name}...", file=sys.stderr)
            try:
                file_data = parse_single_file(filepath, indent, include_all_blocks, summary_only=False)
                result["metadata"]["total_chunks"] += file_data["metadata"]["chunk_count"]
                # Merge block summary
                for block_name, count in file_data["metadata"]["block_summary"].items():
                    result["metadata"]["block_summary"][block_name] = \
                        result["metadata"]["block_summary"].get(block_name, 0) + count
                # Merge blocks
                result["blocks"].update(file_data["blocks"])
            except Exception as e:
                print(f"Warning: Failed to parse {filepath}: {e}", file=sys.stderr)
        
        return result


def get_output_filename_for_single_file(input_path: Path) -> Path:
    """Get output filename for a single region file in current working directory."""
    stem = input_path.stem  # e.g., "-2.-3.region"
    return Path.cwd() / f"{stem}.json"


def main() -> int:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        prog='hytale-region-parser',
        description='Parser for Hytale .region.bin files (IndexedStorageFile format)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Parse single file (writes -2.-3.region.json in current directory)
  hytale-region-parser chunks/-2.-3.region.bin
  
  # Parse folder of region files
  hytale-region-parser path/to/chunks/
  
  # Parse universe folder (creates <worldname>.json for each world)
  hytale-region-parser path/to/universe/worlds/
  
  # Output to stdout instead of file
  hytale-region-parser chunks/0.0.region.bin --stdout
        """
    )
    
    parser.add_argument(
        'input_path',
        type=Path,
        help='Path to a .region.bin file or folder containing region files'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=Path,
        metavar='FILE',
        help='Output file path (overrides default naming)'
    )
    
    parser.add_argument(
        '--stdout',
        action=argparse.BooleanOptionalAction,
        default=False,
        help='Output to stdout instead of writing to file (default: off)'
    )
    
    parser.add_argument(
        '--compact',
        action='store_true',
        help='Output compact JSON without indentation'
    )
    
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Suppress progress and status messages'
    )
    
    parser.add_argument(
        '--summary-only', '-s',
        action='store_true',
        help='Output block counts summary only (no individual block positions - much faster)'
    )
    
    parser.add_argument(
        '--no-blocks',
        action='store_true',
        help='Exclude terrain blocks, only include containers and block components'
    )
    
    parser.add_argument(
        '--version', '-V',
        action='version',
        version='%(prog)s 0.1.0'
    )
    
    args = parser.parse_args()
    
    # Validate input exists
    if not args.input_path.exists():
        print(f"Error: Path not found: {args.input_path}", file=sys.stderr)
        return 1
    
    indent = None if args.compact else 2
    cwd = Path.cwd()
    include_all_blocks = not args.no_blocks
    summary_only = args.summary_only
    
    try:
        # Check if input is a file or directory
        if args.input_path.is_file():
            # Single file mode
            data = parse_single_file(args.input_path, indent, include_all_blocks, summary_only)
            json_output = json.dumps(data, indent=indent, default=str)
            
            if args.stdout:
                print(json_output)
            else:
                output_path = args.output or get_output_filename_for_single_file(args.input_path)
                output_path.write_text(json_output, encoding='utf-8')
                if not args.quiet:
                    print(f"Output written to {output_path}", file=sys.stderr)
        
        elif args.input_path.is_dir():
            # Directory mode
            structure_type, files_dict = detect_folder_structure(args.input_path)
            
            if structure_type == "empty":
                print(f"Error: No .region.bin files found in {args.input_path}", file=sys.stderr)
                return 1
            
            if not args.quiet:
                total_files = sum(len(f) for f in files_dict.values())
                print(f"Found {total_files} region file(s) in {len(files_dict)} location(s)", file=sys.stderr)
            
            if structure_type == "universe":
                # Universe mode: create one JSON per world in cwd
                for world_name, region_files in files_dict.items():
                    if not args.quiet:
                        print(f"\nProcessing world: {world_name} ({len(region_files)} files)", file=sys.stderr)
                    
                    data = parse_multiple_files(region_files, indent, args.quiet, include_all_blocks, summary_only)
                    json_output = json.dumps(data, indent=indent, default=str)
                    
                    if args.stdout:
                        if len(files_dict) > 1:
                            print(f"\n=== {world_name} ===")
                        print(json_output)
                    else:
                        output_path = args.output if (args.output and len(files_dict) == 1) else (cwd / f"{world_name}.json")
                        output_path.write_text(json_output, encoding='utf-8')
                        if not args.quiet:
                            print(f"Output written to {output_path}", file=sys.stderr)
            
            elif structure_type == "chunks":
                # Chunks folder: use parent folder name as world name
                world_name, region_files = next(iter(files_dict.items()))
                if not args.quiet:
                    print(f"Processing world: {world_name} ({len(region_files)} files)", file=sys.stderr)
                
                data = parse_multiple_files(region_files, indent, args.quiet, include_all_blocks, summary_only)
                json_output = json.dumps(data, indent=indent, default=str)
                
                if args.stdout:
                    print(json_output)
                else:
                    output_path = args.output or (cwd / f"{world_name}.json")
                    output_path.write_text(json_output, encoding='utf-8')
                    if not args.quiet:
                        print(f"Output written to {output_path}", file=sys.stderr)
            
            else:  # flat structure
                # Flat folder: combine all files into one JSON
                region_files = files_dict.get("", [])
                if not args.quiet:
                    print(f"Processing {len(region_files)} files from {args.input_path.name}", file=sys.stderr)
                
                data = parse_multiple_files(region_files, indent, args.quiet, include_all_blocks, summary_only)
                json_output = json.dumps(data, indent=indent, default=str)
                
                if args.stdout:
                    print(json_output)
                else:
                    output_path = args.output or (cwd / "regions.json")
                    output_path.write_text(json_output, encoding='utf-8')
                    if not args.quiet:
                        print(f"Output written to {output_path}", file=sys.stderr)
        
        else:
            print(f"Error: {args.input_path} is neither a file nor a directory", file=sys.stderr)
            return 1
            
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
