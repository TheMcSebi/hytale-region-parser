# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1] - 2026-01-22

### Changed
- Updated README documentation

## [0.1.0] - 2026-01-22

### Added

#### Core Features
- **IndexedStorageFile parser** for reading Hytale's `.region.bin` format
  - Magic string validation ("HytaleIndexedStorage")
  - Support for version 0 and 1 of the file format
  - Segment-based blob storage with index table
  - Zstandard (zstd) decompression support
- **RegionFileParser** class with full Python API
  - Context manager support (`with` statement)
  - Iterator interface for chunk traversal (`iter_chunks()`)
  - JSON export (`to_dict()`, `to_json()`)
  - Summary generation (`get_summary()`, `to_dict_summary_only()`)
  - Detailed debugging output (`parse_detailed()`)
- **ChunkDataParser** for parsing individual chunk data
  - BSON document parsing using Hytale's codec format
  - Block section parsing with palette support
  - Multiple palette types: Empty, HalfByte (nibble), Byte, Short
  - Block name extraction via pattern matching
- **BsonParser** for Hytale's BSON codec
  - All standard BSON types (int32, int64, double, string, document, array, binary, etc.)
  - Automatic type conversion for JSON serialization

#### Data Models
- `ParsedChunkData` - Complete parsed chunk data container
- `ChunkSectionData` - 32x32x32 block sections with palettes
- `BlockPaletteEntry` - Block palette entry with internal ID, name, and count
- `BlockComponent` - Block component data with position and type
- `ItemContainerData` - Container data (chests, barrels, etc.)
- `RegionData` - Region-level data aggregation

#### Command-Line Interface
- Single file processing with automatic JSON output naming
- Folder processing modes:
  - **Chunks folder** - Parse a world's chunks directory
  - **Universe folder** - Parse multiple worlds at once
  - **Flat folder** - Parse any directory containing region files
- Output options:
  - `--stdout` - Output to stdout instead of file
  - `-o/--output` - Specify custom output file
  - `--compact` - Compact JSON without indentation
  - `-q/--quiet` - Suppress progress messages
  - `-s/--summary-only` - Fast summary mode without individual block positions
  - `--no-blocks` - Only include containers and components

#### JSON Output Format
- World coordinate keys (`"x,y,z"`) for all block data
- Metadata section with region coordinates, chunk count, and block summary
- Container data with capacity, items, custom names, and placement info
- Block component data with component type and properties

#### Developer Features
- Full type hints throughout the codebase
- `py.typed` marker for PEP 561 compliance
- Comprehensive test suite (69 tests)
- Support for Python 3.8, 3.9, 3.10, 3.11, 3.12, and 3.13
- Example scripts demonstrating common use cases
- MIT License

[0.1.1]: https://github.com/TheMcSebi/hytale-region-parser/releases/tag/v0.1.1
[0.1.0]: https://github.com/TheMcSebi/hytale-region-parser/releases/tag/v0.1.0
