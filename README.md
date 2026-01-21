# Hytale Region Parser

[![PyPI version](https://badge.fury.io/py/hytale-region-parser.svg)](https://badge.fury.io/py/hytale-region-parser)
[![Python versions](https://img.shields.io/pypi/pyversions/hytale-region-parser.svg)](https://pypi.org/project/hytale-region-parser/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Python library for parsing Hytale `.region.bin` files (IndexedStorageFile format).

## Overview

This tool parses Hytale world region files to extract and analyze chunk data, including block information, components, containers, and entities. It implements a custom BSON parser compatible with Hytale's codec system and handles zstandard-compressed data blobs.

The code is mostly written by letting Claude Sonnet and Opus analyze the HytaleServer.jar's decompiled code and reimplementing the relevant parts in Python. I mainly wrote this because I wanted to learn about ore distribution, but this might serve others as a starter, too.

There is still a bug regarding parsed entity names, that I haven't been able to figure out.

## Features

- Parse IndexedStorageFile format (`.region.bin` files)
- **JSON output to file by default** with position-keyed block data
- **Folder processing** - parse entire directories or universe structures
- All output files written to current working directory
- Extract chunk data with block palettes and component information
- Decode BSON documents using Hytale's codec format
- Identify and list unique block types across regions
- Parse item containers (chests, barrels, etc.) with position and capacity
- Extract block components and entity data
- Support for zstandard decompression
- Type hints and dataclasses for clean API
- Command-line interface and Python API

## Installation

### From PyPI

```bash
pip install hytale-region-parser
```

### From Source

```bash
git clone https://github.com/yourusername/hytale-region-parser.git
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
hytale-region-parser chunks/-2.-3.region.bin

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

## JSON Output Format

The default output is JSON with world coordinates as keys:

```json
{
  "100,64,200": {
    "name": "Container",
    "components": {
      "container": {
        "capacity": 18,
        "items": [
          {"Id": "Ore_Copper", "Quantity": 4}
        ],
        "allow_viewing": true,
        "custom_name": null
      }
    }
  },
  "150,32,180": {
    "name": "FarmingBlock",
    "components": {
      "FarmingBlock": {
        "SpreadRate": 0.0
      }
    }
  }
}
```

The coordinates are in world space (`chunk_x * 32 + local_x`, etc.).

## Folder Processing

The CLI supports three folder structures:

All output files are written to the **current working directory** where the command is executed.

### Single File
```bash
hytale-region-parser chunks/-2.-3.region.bin
# Output: ./-2.-3.region.json
```

### Chunks Folder
When pointing to a folder named "chunks", the parent folder is used as the world name:
```bash
hytale-region-parser path/to/default/chunks/
# Output: ./default.json (merges all region files)
```

### Universe Folder
When pointing to a folder containing world subfolders with "chunks" directories:
```bash
hytale-region-parser path/to/universe/worlds/
# Output: ./world1.json
#         ./world2.json
#         (one JSON file per world)
```

### Flat Folder
Any other folder containing `.region.bin` files:
```bash
hytale-region-parser path/to/region_files/
# Output: ./regions.json (merges all region files)
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

## File Format

The parser handles the following Hytale data structures:

- **IndexedStorageFile**: Container format for region files (32-byte header + index table + segments)
- **Chunk Data**: 32x32 column sections containing blocks and metadata
- **Block Components**: Special block data (containers, signs, doors, etc.)
- **BSON Documents**: Hytale's serialization format for game data

Each region file contains up to 1024 chunks (32×32 grid), compressed with Zstandard.

## Development

### Running Tests

```bash
pytest
```

### Type Checking

```bash
mypy src/hytale_region_parser
```

### Linting

```bash
ruff check src/hytale_region_parser
```

### Building for PyPI

```bash
pip install build twine
python -m build
twine upload dist/*
```

## Output

The parser identifies various block categories including:
- Rock, Soil, Plant, Wood, Ore
- Furniture, Metal, Stone, Grass, Tree
- Water, Lava, Ice, Sand, Brick, Glass
- Structural elements (Roof, Floor, Stair, Door, Window)
- Interactive blocks (Chest, Barrel, Crate)
- And more

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
