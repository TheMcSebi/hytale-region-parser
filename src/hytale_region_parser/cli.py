"""
Command-line interface for Hytale Region Parser
"""

import argparse
import sys
from pathlib import Path

from .region_parser import RegionFileParser


def main() -> int:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        prog='hytale-region-parser',
        description='Parser for Hytale .region.bin files (IndexedStorageFile format)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  hytale-region-parser chunks/0.0.region.bin
  hytale-region-parser chunks/0.0.region.bin --summary
  hytale-region-parser chunks/0.0.region.bin --detailed
  hytale-region-parser chunks/0.0.region.bin --detailed --max-chunks 10
        """
    )
    
    parser.add_argument(
        'region_file',
        type=Path,
        help='Path to the .region.bin file to parse'
    )
    
    parser.add_argument(
        '--summary',
        action='store_true',
        help='Show summary of all unique blocks, containers, and components'
    )
    
    parser.add_argument(
        '--detailed',
        action='store_true',
        help='Show detailed BSON structure of first few chunks'
    )
    
    parser.add_argument(
        '--max-chunks',
        type=int,
        default=5,
        metavar='N',
        help='Maximum number of chunks to show in detailed mode (default: 5)'
    )
    
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Suppress output (useful with --json)'
    )
    
    parser.add_argument(
        '--version', '-V',
        action='version',
        version='%(prog)s 0.1.0'
    )
    
    args = parser.parse_args()
    
    # Validate file exists
    if not args.region_file.exists():
        print(f"Error: File not found: {args.region_file}", file=sys.stderr)
        return 1
    
    # Create parser and run appropriate method
    region_parser = RegionFileParser(args.region_file)
    
    try:
        if args.summary:
            region_parser.parse_summary(verbose=not args.quiet)
        elif args.detailed:
            region_parser.parse_detailed(max_chunks=args.max_chunks, verbose=not args.quiet)
        else:
            region_parser.parse(verbose=not args.quiet)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
