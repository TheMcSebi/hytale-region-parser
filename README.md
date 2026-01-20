# Hytale Region Parser

A Python parser for Hytale `.region.bin` files, implementing support for the IndexedStorageFile format used by the Hytale server.

## Overview

This tool parses Hytale world region files to extract and analyze chunk data, including block information, components, containers, and entities. It implements a custom BSON parser compatible with Hytale's codec system and handles zstandard-compressed data blobs.  
The code is mostly written by letting Claude Sonnet and Opus analyze the HytaleServer.jar's decompiled code and reimplementing the relevant parts in Python. I mainly wrote this because I wanted to learn about ore distribution, but this might serve others as a starter, too.

## Features

- Parse IndexedStorageFile format (`.region.bin` files)
- Extract chunk data with block palettes and component information
- Decode BSON documents using Hytale's codec format
- Identify and list unique block types across regions
- Parse item containers (chests, barrels, etc.) with position and capacity
- Extract block components and entity data
- Support for zstandard decompression
- Multiple output modes: basic list, summary, and detailed analysis

## Requirements

- Python 3.7 or higher (Written on 3.13)
- zstandard

## Installation

Install the required dependency:

```bash
pip install zstandard
```

## Usage

### Basic Chunk Listing

Display all chunks with data in a region file:

```bash
python parse_region.py chunks/0.0.region.bin
```

### Summary Mode

Generate a comprehensive summary of all blocks, containers, and components:

```bash
python parse_region.py chunks/0.0.region.bin --summary
```

This mode outputs:
- Total unique block types with occurrence counts
- Blocks grouped by category
- Item container locations and contents
- Block component types and positions

### Detailed Analysis

Show detailed BSON structure for the first few chunks:

```bash
python parse_region.py chunks/0.0.region.bin --detailed
```

## File Format

The parser handles the following Hytale data structures:

- **IndexedStorageFile**: Container format for region files
- **Chunk Data**: 32x32 column sections containing blocks and metadata
- **Block Components**: Special block data (containers, signs, doors, etc.)
- **BSON Documents**: Hytale's serialization format for game data

## Output

The parser identifies various block categories including:
- Rock, Soil, Plant, Wood, Ore
- Furniture, Metal, Stone, Grass, Tree
- Water, Lava, Ice, Sand, Brick, Glass
- Structural elements (Roof, Floor, Stair, Door, Window)
- Interactive blocks (Chest, Barrel, Crate)
- And more

## License

See [LICENSE](LICENSE) file for details.
