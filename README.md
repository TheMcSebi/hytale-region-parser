# Hytale Region Parser

[![PyPI version](https://badge.fury.io/py/hytale-region-parser.svg)](https://badge.fury.io/py/hytale-region-parser)
[![Python versions](https://img.shields.io/pypi/pyversions/hytale-region-parser.svg)](https://pypi.org/project/hytale-region-parser/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Python library for parsing Hytale `.region.bin` files (IndexedStorageFile format).

## Overview

This library allows parsing Hytale world region files (.region.bin-Format) to extract and analyze chunk data, including block information, components, containers, and other entities. It implements a parser compatible with Hytale's codec system and handles zstandard-compressed data blobs.

The code is mostly written by letting Claude Sonnet and Opus analyze the HytaleServer.jar's decompiled code and reimplementing the relevant parts in Python. I mainly created this because I wanted to learn about ore distribution, but it quickly evolved into a library.

Explore the [examples](examples/README.md) for common use cases and report bugs or request features on the [GitHub Issues page](https://github.com/TheMcSebi/hytale-region-parser/issues).

## Features

- Parse IndexedStorageFile format (`.region.bin` files)
- **JSON output to file by default** with position-keyed block data
- Parse single .region.bin files or entire worlds
- Extract chunk data with block palettes and component information
- Decode BSON documents using Hytale's codec format
- Extract block components and entity data
- Type hints and dataclasses for clean API
- Simple command-line interface and Python API

## Examples

[Examples](examples/README.md) contain a few simple and some more advanced examples on how to use this library and what to use it for.

## Installation

### From PyPI

```bash
pip install hytale-region-parser
```

### From Source

```bash
git clone https://github.com/TheMcSebi/hytale-region-parser.git
cd hytale-region-parser
pip install -e .
```

### Development Installation

```bash
pip install -e ".[dev]"
```

## Quick Start

### Command Line

```bash
# Parse single file (writes -2.-3.region.json in current directory)
hytale-region-parser chunks/-2.-3.region.bin --summary-only

# Parse a "chunks" folder (writes <worldname>.json in current directory)
hytale-region-parser path/to/worldname/chunks/

# Parse a universe folder (writes <worldname>.json for each world in current directory)
hytale-region-parser path/to/universe/worlds/

# Parse a flat folder of region files (writes regions.json in current directory)
hytale-region-parser path/to/region_files/

# Output to stdout instead of file
hytale-region-parser path/to/0.0.region.bin --stdout

# Specify custom output file
hytale-region-parser path/to/0.0.region.bin -o output.json

# Compact JSON (no indentation)
hytale-region-parser path/to/0.0.region.bin --compact

# Suppress progress messages
hytale-region-parser path/to/chunks/ -q
```

### Python API

```python
from pathlib import Path
from hytale_region_parser import RegionFileParser

# Get JSON output (recommended)
with RegionFileParser(Path("0.0.region.bin")) as parser:
    # Get as dictionary
    data = parser.to_dict()
    
    # Or as JSON string
    json_str = parser.to_json(indent=2)
    print(json_str)

# Iterate over chunks for custom processing
with RegionFileParser(Path("0.0.region.bin")) as parser:
    for chunk in parser.iter_chunks():
        print(f"Chunk ({chunk.chunk_x}, {chunk.chunk_z})")
        print(f"  Block types: {len(chunk.block_names)}")
        print(f"  Containers: {len(chunk.containers)}")

# Get a summary of the entire region
with RegionFileParser(Path("0.0.region.bin")) as parser:
    summary = parser.get_summary()
    print(f"Unique block types: {summary['unique_blocks']}")
```

## Data Models

### ParsedChunkData

The main result type containing all parsed chunk information:

```python
@dataclass
class ParsedChunkData:
    chunk_x: int                              # Chunk X coordinate
    chunk_z: int                              # Chunk Z coordinate
    version: int                              # Data format version
    sections: List[ChunkSectionData]          # 32x32x32 block sections
    block_components: List[BlockComponent]    # Block component data
    containers: List[ItemContainerData]       # Item containers (chests, etc.)
    entities: List[Dict[str, Any]]            # Entity data
    block_names: Set[str]                     # Unique block type names
    raw_components: Dict[str, Any]            # Raw BSON component data
```

### ItemContainerData

Represents storage blocks like chests:

```python
@dataclass
class ItemContainerData:
    position: Tuple[int, int, int]    # Block position
    capacity: int                      # Number of slots
    items: List[Dict[str, Any]]       # Item data in slots
    custom_name: Optional[str]        # Custom container name
```

## About Hytale's File Format

### Region File Structure (`.region.bin`)

Hytale stores world data in **IndexedStorageFile** format, a custom binary container:

```
┌─────────────────────────────────────────────────────────────┐
│ HEADER (32 bytes)                                           │
│   ├─ Magic: "HytaleIndexedStorage" (20 bytes)               │
│   ├─ Version: uint32 BE (0 or 1)                            │
│   ├─ Blob Count: uint32 BE (1024 for 32×32 chunks)          │
│   └─ Segment Size: uint32 BE                                │
├─────────────────────────────────────────────────────────────┤
│ BLOB INDEX TABLE (blob_count × 4 bytes)                     │
│   └─ Segment index for each chunk (uint32 BE, 0 = empty)    │
├─────────────────────────────────────────────────────────────┤
│ SEGMENTS (variable size)                                    │
│   └─ Zstandard-compressed chunk data blobs                  │
└─────────────────────────────────────────────────────────────┘
```

Each region file contains up to **1024 chunks** (32×32 grid). The filename `X.Z.region.bin` indicates region coordinates, where each chunk's world position is calculated as `(region_x * 32 + local_x, region_z * 32 + local_z)`.

### Blob/Chunk Data Structure

Each compressed blob contains a **BSON document** with the following hierarchy:

```
Root
├─ Version: int
└─ Components
   ├─ ChunkColumn
   │  └─ Sections[] (up to 10 vertical sections, 32 blocks each = 320 height)
   │     └─ Components
   │        └─ Block
   │           └─ Data: hex-encoded block section data
   ├─ BlockComponentChunk
   │  └─ BlockComponents{} (keyed by block index)
   │     └─ Components (container, sign, farming, etc.)
   └─ EntityChunk
      └─ Entities[]
```

### Block Section Data Format

The hex-encoded `Block.Data` field contains:

| Offset | Size | Field |
|--------|------|-------|
| 0 | 4 | Block migration version (uint32 BE) |
| 4 | 1 | Palette type: 0=Empty, 1=HalfByte, 2=Byte, 3=Short |
| 5 | 2 | Palette entry count (uint16 BE) |
| 7+ | var | Palette entries (ID + name + count per entry) |
| var | var | Block indices (32×32×32 = 32768 blocks per section) |

**Palette Entry Format:**
- 1 byte: Internal ID
- 2 bytes: String length (uint16 BE)
- N bytes: Block name (UTF-8, e.g., `Rock_Stone_Mossy`)
- 2 bytes: Block count (int16 BE)

**Block Index Encoding** (based on palette type):
- **HalfByte (1):** 4 bits per block (16 max palette entries)
- **Byte (2):** 8 bits per block (256 max palette entries)
- **Short (3):** 16 bits per block (65536 max palette entries)

Block index formula: `index = x + z*32 + y*32*32`

### How the Parser Works

1. **Open & Validate:** Read header, verify magic string `HytaleIndexedStorage`
2. **Index Table:** Load segment pointers for all 1024 chunk slots
3. **Iterate Chunks:** For each non-empty slot:
   - Seek to segment position
   - Read blob header (source length + compressed length)
   - Decompress with **zstandard**
   - Parse as BSON document
4. **Extract Block Data:** For each section in `ChunkColumn.Sections`:
   - Decode hex block data
   - Parse palette (block names + counts)
   - Optionally decode full block indices for position mapping
5. **Extract Components:** Parse containers, signs, farming blocks, etc. from `BlockComponentChunk`



## Development

### Running Tests

```bash
python -m pytest tests/ -v
```

### Type Checking

```bash
python -m mypy src/hytale_region_parser --ignore-missing-imports
```

### Linting

```bash
python -m ruff check src/hytale_region_parser
```

### Building for PyPI

```bash
python -m pytest tests/ -q; python -m mypy src/hytale_region_parser; python -m ruff check src/hytale_region_parser
pip install build twine
python -m build
twine upload dist/*
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
