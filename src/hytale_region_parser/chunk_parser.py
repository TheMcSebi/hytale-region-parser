"""
Chunk Data Parser

Parser for chunk data in Hytale's region format (BSON-based).
"""

import struct
from typing import Any, Dict, List, Optional, Set

from .bson_parser import BsonParser
from .models import (
    BlockComponent,
    BlockPaletteEntry,
    ChunkSectionData,
    ItemContainerData,
    ParsedChunkData,
)


class ChunkDataParser:
    """Parser for chunk data in Hytale's region format (BSON-based)"""

    def __init__(self, data: bytes):
        """
        Initialize the chunk data parser.
        
        Args:
            data: Raw chunk data bytes
        """
        self.data = data
        self.pos = 0

    def read_int(self) -> int:
        """Read a 4-byte big-endian integer"""
        if self.pos + 4 > len(self.data):
            raise ValueError("Not enough data to read int")
        value = struct.unpack('>I', self.data[self.pos:self.pos+4])[0]
        self.pos += 4
        return value

    def read_int_le(self) -> int:
        """Read a 4-byte little-endian integer"""
        if self.pos + 4 > len(self.data):
            raise ValueError("Not enough data to read int")
        value = struct.unpack('<i', self.data[self.pos:self.pos+4])[0]
        self.pos += 4
        return value

    def read_string(self) -> str:
        """Read a length-prefixed string (big-endian length)"""
        length = self.read_int()
        if length < 0 or length > 1000000:  # Sanity check
            raise ValueError(f"Invalid string length: {length}")
        if self.pos + length > len(self.data):
            raise ValueError("Not enough data to read string")

        string = self.data[self.pos:self.pos+length].decode('utf-8', errors='replace')
        self.pos += length
        return string

    def read_byte(self) -> int:
        """Read a single byte"""
        if self.pos >= len(self.data):
            raise ValueError("Not enough data to read byte")
        value = self.data[self.pos]
        self.pos += 1
        return value

    def read_bytes(self, count: int) -> bytes:
        """Read a specified number of bytes"""
        if self.pos + count > len(self.data):
            raise ValueError("Not enough data to read bytes")
        value = self.data[self.pos:self.pos+count]
        self.pos += count
        return value

    def read_short(self) -> int:
        """Read a 2-byte big-endian short"""
        if self.pos + 2 > len(self.data):
            raise ValueError("Not enough data to read short")
        value = struct.unpack('>H', self.data[self.pos:self.pos+2])[0]
        self.pos += 2
        return value

    def read_short_le(self) -> int:
        """Read a 2-byte little-endian short"""
        if self.pos + 2 > len(self.data):
            raise ValueError("Not enough data to read short")
        value = struct.unpack('<h', self.data[self.pos:self.pos+2])[0]
        self.pos += 2
        return value

    def skip_bytes(self, count: int) -> None:
        """Skip a specified number of bytes"""
        self.pos += count

    def remaining(self) -> int:
        """Return number of bytes remaining"""
        return len(self.data) - self.pos

    def try_parse_bson(self) -> Optional[Dict[str, Any]]:
        """Try to parse the data as a BSON document"""
        try:
            parser = BsonParser(self.data)
            return parser.parse()
        except Exception:
            return None

    @staticmethod
    def parse_block_section_data(data_hex: str, section_y: int = 0) -> ChunkSectionData:
        """
        Parse block section data from hex string.
        
        Block Section Data Format (version 6):
        - 4 bytes: Block migration version (int32 BE)
        - 1 byte: Palette type (0=Empty, 1=HalfByte, 2=Byte, 3=Short)
        - 2 bytes: Palette entry count (unsigned short BE)
        - For each palette entry:
            - 1 byte: internal ID
            - 2 bytes: string length (unsigned short BE)
            - N bytes: UTF-8 string (block name)
            - 2 bytes: block count (signed short BE)
        - Remaining bytes: block indices
        
        Args:
            data_hex: Hex-encoded block data string
            section_y: Y index of the section
            
        Returns:
            ChunkSectionData with parsed palette and block counts
        """
        section = ChunkSectionData(section_y=section_y)

        if not data_hex:
            return section

        try:
            data = bytes.fromhex(data_hex)
        except ValueError:
            return section

        if len(data) < 7:  # Minimum: 4 + 1 + 2 = 7 bytes
            return section

        pos = 0

        # 4 bytes: Block migration version
        # migration_version = struct.unpack('>I', data[pos:pos+4])[0]
        pos += 4

        # 1 byte: Palette type (0=Empty, 1=HalfByte, 2=Byte, 3=Short)
        palette_type = data[pos]
        pos += 1
        section.palette_type = palette_type

        if palette_type == 0:  # Empty section
            return section

        # 2 bytes: Palette entry count
        if pos + 2 > len(data):
            return section
        palette_count = struct.unpack('>H', data[pos:pos+2])[0]
        pos += 2

        # Parse palette entries
        palette: List[BlockPaletteEntry] = []
        block_counts: Dict[str, int] = {}

        for _ in range(palette_count):
            if pos >= len(data):
                break

            # 1 byte: internal ID
            internal_id = data[pos]
            pos += 1

            # 2 bytes: string length
            if pos + 2 > len(data):
                break
            str_len = struct.unpack('>H', data[pos:pos+2])[0]
            pos += 2

            if str_len > 500:  # Sanity check
                break

            # N bytes: block name
            if pos + str_len > len(data):
                break
            name = data[pos:pos+str_len].decode('utf-8', errors='replace')
            pos += str_len

            # 2 bytes: block count (signed short)
            if pos + 2 > len(data):
                # Still add the entry without count
                entry = BlockPaletteEntry(internal_id=internal_id, name=name, count=0)
                palette.append(entry)
                break
            count = struct.unpack('>h', data[pos:pos+2])[0]
            pos += 2

            entry = BlockPaletteEntry(internal_id=internal_id, name=name, count=count)
            palette.append(entry)

            # Aggregate counts by block name (skip Empty blocks)
            if name and name != "Empty":
                block_counts[name] = block_counts.get(name, 0) + max(0, count)

        section.block_palette = palette
        section.block_counts = block_counts

        # Store remaining block indices
        if pos < len(data):
            section.block_indices = data[pos:]

        return section

    def parse(self) -> ParsedChunkData:
        """
        Parse chunk data and extract all components.
        
        Returns:
            ParsedChunkData object containing all parsed information
        """
        result = ParsedChunkData()

        # First try BSON parsing
        bson_doc = self.try_parse_bson()

        if bson_doc:
            result.raw_components = bson_doc

            # Extract version if present
            result.version = bson_doc.get('Version', 0)

            # Navigate to the Components section
            components = bson_doc.get('Components', {})

            # Parse block components from BlockComponentChunk
            block_comp_chunk = components.get('BlockComponentChunk', {})
            block_components = block_comp_chunk.get('BlockComponents', {})

            for index_str, component_data in block_components.items():
                try:
                    index = int(index_str)

                    # Calculate position from index (within a 32x32 column)
                    x = index % 32
                    y = (index // 32) % 320  # Height can be up to 320
                    z = (index // (32 * 320))

                    # Get the inner Components dict
                    inner_comps = component_data.get('Components', {}) if isinstance(component_data, dict) else {}

                    # Check for container
                    container_data = inner_comps.get('container')
                    if container_data and isinstance(container_data, dict):
                        pos = container_data.get('Position', {})
                        if isinstance(pos, dict):
                            position = (pos.get('X', 0), pos.get('Y', 0), pos.get('Z', 0))
                        else:
                            position = (x, y, z)

                        item_container = container_data.get('ItemContainer', {})
                        capacity = item_container.get('Capacity', 0) if isinstance(item_container, dict) else 0

                        container = ItemContainerData(
                            position=position,
                            capacity=capacity,
                            allow_viewing=container_data.get('AllowViewing', True),
                            custom_name=container_data.get('Custom_Name'),
                            who_placed_uuid=container_data.get('WhoPlacedUuid'),
                            placed_by_interaction=container_data.get('PlacedByInteraction', False)
                        )

                        # Parse items if present
                        if isinstance(item_container, dict):
                            items = item_container.get('Items', {})
                            if isinstance(items, dict):
                                container.items = list(items.values())
                            elif isinstance(items, list):
                                container.items = items

                        result.containers.append(container)

                    # Check for other component types
                    for comp_name, comp_data in inner_comps.items():
                        component = BlockComponent(
                            index=index,
                            position=(x, y, z),
                            component_type=comp_name,
                            data=comp_data if isinstance(comp_data, dict) else {}
                        )
                        result.block_components.append(component)

                except (ValueError, TypeError):
                    continue

            # Extract entities if present
            entity_chunk = components.get('EntityChunk', {})
            if isinstance(entity_chunk, dict):
                entities = entity_chunk.get('Entities', [])
                if isinstance(entities, list):
                    result.entities = entities

            # Parse ChunkColumn sections for block data
            chunk_column = components.get('ChunkColumn', {})
            if isinstance(chunk_column, dict):
                sections_list = chunk_column.get('Sections', [])
                if isinstance(sections_list, list):
                    for section_idx, section_data in enumerate(sections_list):
                        if not isinstance(section_data, dict):
                            continue

                        section_comps = section_data.get('Components', {})
                        if not isinstance(section_comps, dict):
                            continue

                        # Get Block component
                        block_comp = section_comps.get('Block', {})
                        if isinstance(block_comp, dict):
                            data_hex = block_comp.get('Data', '')
                            if data_hex and isinstance(data_hex, str):
                                # Parse the block section data
                                section = self.parse_block_section_data(data_hex, section_y=section_idx)
                                result.sections.append(section)

                                # Aggregate block names from palette
                                for entry in section.block_palette:
                                    if entry.name and entry.name != "Empty":
                                        result.block_names.add(entry.name)

        return result

    def parse_block_section(self, section_index: int) -> Optional[ChunkSectionData]:
        """
        Parse a single block section.
        
        Args:
            section_index: Y index of the section
            
        Returns:
            ChunkSectionData if successful, None otherwise
        """
        section = ChunkSectionData(section_y=section_index)

        try:
            # Read palette type
            palette_type = self.read_byte()

            # Read block palette based on type
            if palette_type == 0:  # Empty
                pass
            elif palette_type == 1:  # Single value
                block_id = self.read_int()
                section.block_palette = [str(block_id)]
            elif palette_type == 2:  # Indexed palette
                palette_size = self.read_short()
                for _ in range(palette_size):
                    # Read UTF string for block name
                    str_len = self.read_short()
                    block_name = self.read_bytes(str_len).decode('utf-8', errors='replace')
                    section.block_palette.append(block_name)

        except Exception:
            pass

        return section
