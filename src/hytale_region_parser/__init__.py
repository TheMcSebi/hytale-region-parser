"""
Hytale Region Parser

A Python library for parsing Hytale .region.bin files (IndexedStorageFile format).

This library supports parsing of:
- Chunk data (block sections, heightmaps, etc.)
- Block components (BlockComponentChunk)
- Item containers (chests, etc.)
- Block physics data
- Fluid data

Example usage:
    >>> from hytale_region_parser import RegionFileParser
    >>>
    >>> # Using context manager
    >>> with RegionFileParser("0.0.region.bin") as parser:
    ...     for chunk in parser.iter_chunks():
    ...         print(f"Chunk ({chunk.chunk_x}, {chunk.chunk_z})")
    ...         print(f"  Blocks: {len(chunk.block_names)}")
    >>>
    >>> # Or manually
    >>> parser = RegionFileParser("0.0.region.bin")
    >>> summary = parser.parse_summary(verbose=False)
    >>> print(f"Found {summary['unique_blocks']} unique block types")
"""

from .chunk_parser import ChunkDataParser
from .models import (
    BlockComponent,
    BlockPaletteEntry,
    ChunkSectionData,
    ItemContainerData,
    ParsedChunkData,
)
from .region_parser import RegionFileParser
from .storage import IndexedStorageFile

__version__ = "0.1.1"
__author__ = "Hytale Region Parser Contributors"
__all__ = [
    # Main parser
    "RegionFileParser",
    # Supporting parsers
    "ChunkDataParser",
    "IndexedStorageFile",
    # Data models
    "ParsedChunkData",
    "ChunkSectionData",
    "BlockPaletteEntry",
    "BlockComponent",
    "ItemContainerData",
    # Version
    "__version__",
]
