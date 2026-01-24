"""Command-line interface for Hytale Region Parser"""

import argparse
import fnmatch
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import __version__
from .region_parser import RegionFileParser


def matches_filter(name: str, pattern: str) -> bool:
    """Check if name matches fnmatch pattern."""
    return fnmatch.fnmatch(name, pattern)


def filter_block_summary(summary: Dict[str, int], pattern: str) -> Dict[str, int]:
    """Filter block summary to only include matching blocks."""
    return {k: v for k, v in summary.items() if matches_filter(k, pattern)}


def filter_blocks_data(data: Dict[str, Any], pattern: str) -> Dict[str, Any]:
    """Filter full data dictionary to only include matching blocks."""
    if "metadata" in data and "block_summary" in data["metadata"]:
        data["metadata"]["block_summary"] = filter_block_summary(
            data["metadata"]["block_summary"], pattern
        )
    if "blocks" in data:
        data["blocks"] = {
            pos: block for pos, block in data["blocks"].items()
            if "name" in block and matches_filter(block["name"], pattern)
        }
    return data


def find_region_files(folder: Path) -> List[Path]:
    """Find all .region.bin files in a folder."""
    return list(folder.glob("*.region.bin"))


def detect_folder_structure(input_path: Path) -> tuple[str, Dict[str, List[Path]]]:
    """
    Detect folder structure and categorize region files.

    Returns:
        (structure_type, files_dict) where structure_type is:
        "universe", "chunks", "flat", or "empty"
    """
    # Check if input is a "chunks" folder directly
    if input_path.name == "chunks":
        files = find_region_files(input_path)
        if files:
            world_name = input_path.parent.name if input_path.parent != input_path else "world"
            return "chunks", {world_name: files}

    # Check for universe structure (world folders with chunks subfolders)
    worlds: Dict[str, List[Path]] = {}
    for item in input_path.iterdir():
        if item.is_dir():
            chunks_folder = item / "chunks"
            if chunks_folder.is_dir():
                files = find_region_files(chunks_folder)
                if files:
                    worlds[item.name] = files
    if worlds:
        return "universe", worlds

    # Check for flat structure (region files directly in folder)
    files = find_region_files(input_path)
    if files:
        return "flat", {"": files}

    return "empty", {}


def parse_files(
    filepaths: List[Path],
    quiet: bool = False,
    include_all_blocks: bool = True,
    summary_only: bool = False,
    block_filter: Optional[str] = None
) -> Dict[str, Any]:
    """Parse one or more region files and return merged data."""
    if summary_only:
        combined_summary: Dict[str, int] = {}
        combined_containers: List[Dict[str, Any]] = []
        total_chunks = 0

        for filepath in filepaths:
            if not quiet and len(filepaths) > 1:
                print(f"Parsing {filepath.name}...", file=sys.stderr)
            try:
                with RegionFileParser(filepath) as parser:
                    data = parser.to_dict_summary_only()
                    total_chunks += data["metadata"]["chunk_count"]
                    for name, count in data["block_summary"].items():
                        if not block_filter or matches_filter(name, block_filter):
                            combined_summary[name] = combined_summary.get(name, 0) + count
                    combined_containers.extend(data.get("containers", []))
            except Exception as e:
                print(f"Warning: Failed to parse {filepath}: {e}", file=sys.stderr)

        return {
            "metadata": {"total_chunks": total_chunks, "total_region_files": len(filepaths)},
            "block_summary": combined_summary,
            "containers": combined_containers
        }

    # Full mode
    result: Dict[str, Any] = {
        "metadata": {"total_chunks": 0, "total_region_files": len(filepaths), "block_summary": {}},
        "blocks": {}
    }

    for filepath in filepaths:
        if not quiet and len(filepaths) > 1:
            print(f"Parsing {filepath.name}...", file=sys.stderr)
        try:
            with RegionFileParser(filepath) as parser:
                data = parser.to_dict(include_all_blocks=include_all_blocks)
                if block_filter:
                    data = filter_blocks_data(data, block_filter)

                result["metadata"]["total_chunks"] += data["metadata"]["chunk_count"]
                for name, count in data["metadata"]["block_summary"].items():
                    result["metadata"]["block_summary"][name] = \
                        result["metadata"]["block_summary"].get(name, 0) + count
                result["blocks"].update(data["blocks"])
        except Exception as e:
            print(f"Warning: Failed to parse {filepath}: {e}", file=sys.stderr)

    return result


def write_output(
    data: Dict[str, Any],
    output_path: Optional[Path],
    stdout: bool,
    quiet: bool,
    compact: bool,
    header: Optional[str] = None
) -> None:
    """Write parsed data to file or stdout."""
    indent = None if compact else 2
    json_output = json.dumps(data, indent=indent, default=str)

    if stdout:
        if header:
            print(f"\n=== {header} ===")
        print(json_output)
    else:
        assert output_path is not None
        output_path.write_text(json_output, encoding='utf-8')
        if not quiet:
            print(f"Output written to {output_path}", file=sys.stderr)


def main() -> int:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        prog='hytale-region-parser',
        description='Parser for Hytale .region.bin files',
        epilog="""
Examples:
  hytale-region-parser chunks/0.0.region.bin
  hytale-region-parser path/to/chunks/
  hytale-region-parser path/to/universe/worlds/
  hytale-region-parser chunks/0.0.region.bin --stdout
        """
    )

    parser.add_argument('input_path', type=Path, help='Path to .region.bin file or folder')
    parser.add_argument('--output', '-o', type=Path, help='Output file path')
    parser.add_argument('--stdout', action='store_true', help='Output to stdout')
    parser.add_argument('--compact', action='store_true', help='Compact JSON output')
    parser.add_argument('--quiet', '-q', action='store_true', help='Suppress progress messages')
    parser.add_argument('--summary-only', '-s', action='store_true', help='Block counts only (faster)')
    parser.add_argument('--no-blocks', action='store_true', help='Exclude terrain blocks')
    parser.add_argument('--filter', '-f', type=str, metavar='PATTERN',
                        help='Filter blocks by pattern (fnmatch: * and ?). Use ^* on Windows CMD.')
    parser.add_argument('--version', '-V', action='version', version=f'%(prog)s {__version__}')

    args = parser.parse_args()

    if not args.input_path.exists():
        print(f"Error: Path not found: {args.input_path}", file=sys.stderr)
        return 1

    block_filter = args.filter if args.filter else None
    cwd = Path.cwd()

    try:
        if args.input_path.is_file():
            data = parse_files(
                [args.input_path], args.quiet, not args.no_blocks, args.summary_only, block_filter
            )
            output_path = args.output or (cwd / f"{args.input_path.stem}.json")
            write_output(data, output_path, args.stdout, args.quiet, args.compact)

        elif args.input_path.is_dir():
            structure, files_dict = detect_folder_structure(args.input_path)

            if structure == "empty":
                print(f"Error: No .region.bin files found in {args.input_path}", file=sys.stderr)
                return 1

            if not args.quiet:
                total = sum(len(f) for f in files_dict.values())
                print(f"Found {total} region file(s) in {len(files_dict)} location(s)", file=sys.stderr)

            if structure == "universe":
                for world_name, files in files_dict.items():
                    if not args.quiet:
                        print(f"\nProcessing world: {world_name} ({len(files)} files)", file=sys.stderr)

                    data = parse_files(files, args.quiet, not args.no_blocks, args.summary_only, block_filter)
                    output_path = args.output if (args.output and len(files_dict) == 1) else (cwd / f"{world_name}.json")
                    header = world_name if args.stdout and len(files_dict) > 1 else None
                    write_output(data, output_path, args.stdout, args.quiet, args.compact, header)
            else:
                # chunks or flat structure
                world_name, files = next(iter(files_dict.items()))
                if not args.quiet:
                    label = f"world: {world_name}" if world_name else f"folder: {args.input_path.name}"
                    print(f"Processing {label} ({len(files)} files)", file=sys.stderr)

                data = parse_files(files, args.quiet, not args.no_blocks, args.summary_only, block_filter)
                default_name = f"{world_name}.json" if world_name else "regions.json"
                output_path = args.output or (cwd / default_name)
                write_output(data, output_path, args.stdout, args.quiet, args.compact)
        else:
            print(f"Error: {args.input_path} is neither a file nor a directory", file=sys.stderr)
            return 1

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
