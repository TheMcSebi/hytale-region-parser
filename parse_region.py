#!/usr/bin/env python3
"""
Parser for Hytale .region.bin files (IndexedStorageFile format)

Based on the IndexedStorageFile Java implementation from Hytale server.
Supports parsing of:
- Chunk data (block sections, heightmaps, etc.)
- Block components (BlockComponentChunk)
- Item containers (chests, etc.)
- Block physics data
- Fluid data
"""

import struct
import zstandard as zstd
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any, Set
import io
import re
from dataclasses import dataclass, field
from enum import IntEnum


# ============================================================================
# BSON Parser for Hytale's Codec Format
# ============================================================================

class BsonType(IntEnum):
    """BSON element types"""
    DOUBLE = 0x01
    STRING = 0x02
    DOCUMENT = 0x03
    ARRAY = 0x04
    BINARY = 0x05
    UNDEFINED = 0x06  # Deprecated
    OBJECT_ID = 0x07
    BOOLEAN = 0x08
    DATETIME = 0x09
    NULL = 0x0A
    REGEX = 0x0B
    DBPOINTER = 0x0C  # Deprecated
    JAVASCRIPT = 0x0D
    SYMBOL = 0x0E  # Deprecated
    CODE_W_SCOPE = 0x0F
    INT32 = 0x10
    TIMESTAMP = 0x11
    INT64 = 0x12
    DECIMAL128 = 0x13
    MIN_KEY = 0xFF
    MAX_KEY = 0x7F


class BsonParser:
    """Parser for BSON documents used by Hytale's codec system"""
    
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0
        
    def remaining(self) -> int:
        return len(self.data) - self.pos
    
    def read_byte(self) -> int:
        if self.pos >= len(self.data):
            raise ValueError("Unexpected end of data")
        value = self.data[self.pos]
        self.pos += 1
        return value
    
    def read_bytes(self, n: int) -> bytes:
        if self.pos + n > len(self.data):
            raise ValueError(f"Not enough data: need {n}, have {self.remaining()}")
        value = self.data[self.pos:self.pos + n]
        self.pos += n
        return value
    
    def read_int32(self) -> int:
        """Read little-endian 32-bit signed integer"""
        data = self.read_bytes(4)
        return struct.unpack('<i', data)[0]
    
    def read_int32_be(self) -> int:
        """Read big-endian 32-bit signed integer"""
        data = self.read_bytes(4)
        return struct.unpack('>i', data)[0]
    
    def read_uint32(self) -> int:
        """Read little-endian 32-bit unsigned integer"""
        data = self.read_bytes(4)
        return struct.unpack('<I', data)[0]
    
    def read_int64(self) -> int:
        """Read little-endian 64-bit signed integer"""
        data = self.read_bytes(8)
        return struct.unpack('<q', data)[0]
    
    def read_double(self) -> float:
        """Read 64-bit IEEE 754 floating point"""
        data = self.read_bytes(8)
        return struct.unpack('<d', data)[0]
    
    def read_cstring(self) -> str:
        """Read null-terminated string"""
        end = self.data.find(b'\x00', self.pos)
        if end == -1:
            raise ValueError("Unterminated cstring")
        value = self.data[self.pos:end].decode('utf-8', errors='replace')
        self.pos = end + 1
        return value
    
    def read_string(self) -> str:
        """Read BSON string (length-prefixed)"""
        length = self.read_int32()
        if length < 1:
            raise ValueError(f"Invalid string length: {length}")
        data = self.read_bytes(length)
        if data[-1] != 0:
            raise ValueError("String not null-terminated")
        return data[:-1].decode('utf-8', errors='replace')
    
    def read_binary(self) -> Tuple[int, bytes]:
        """Read BSON binary data"""
        length = self.read_int32()
        subtype = self.read_byte()
        data = self.read_bytes(length)
        return subtype, data
    
    def read_document(self) -> Dict[str, Any]:
        """Read a BSON document"""
        start_pos = self.pos
        doc_size = self.read_int32()
        
        result = {}
        while self.pos < start_pos + doc_size - 1:
            element_type = self.read_byte()
            if element_type == 0:
                break
                
            name = self.read_cstring()
            value = self.read_element(element_type)
            result[name] = value
        
        # Read final null byte
        if self.pos < start_pos + doc_size:
            self.pos = start_pos + doc_size
            
        return result
    
    def read_array(self) -> List[Any]:
        """Read a BSON array"""
        doc = self.read_document()
        # BSON arrays are documents with string indices "0", "1", "2", ...
        return [doc[str(i)] for i in range(len(doc))]
    
    def read_element(self, element_type: int) -> Any:
        """Read a BSON element value"""
        if element_type == BsonType.DOUBLE:
            return self.read_double()
        elif element_type == BsonType.STRING:
            return self.read_string()
        elif element_type == BsonType.DOCUMENT:
            return self.read_document()
        elif element_type == BsonType.ARRAY:
            return self.read_array()
        elif element_type == BsonType.BINARY:
            return self.read_binary()
        elif element_type == BsonType.BOOLEAN:
            return self.read_byte() != 0
        elif element_type == BsonType.NULL:
            return None
        elif element_type == BsonType.INT32:
            return self.read_int32()
        elif element_type == BsonType.INT64:
            return self.read_int64()
        elif element_type == BsonType.DATETIME:
            return self.read_int64()  # milliseconds since epoch
        elif element_type == BsonType.TIMESTAMP:
            return self.read_int64()
        elif element_type == BsonType.OBJECT_ID:
            return self.read_bytes(12).hex()
        elif element_type == BsonType.UNDEFINED:
            return None
        elif element_type == BsonType.REGEX:
            pattern = self.read_cstring()
            options = self.read_cstring()
            return {'pattern': pattern, 'options': options}
        else:
            raise ValueError(f"Unknown BSON type: {element_type:#x}")
    
    def parse(self) -> Dict[str, Any]:
        """Parse the entire BSON document"""
        return self.read_document()


# ============================================================================
# Data Classes for Parsed Chunk Data
# ============================================================================

@dataclass
class BlockComponent:
    """Represents a block component at a specific position"""
    index: int  # Block index within chunk (0-32767 per section)
    position: Tuple[int, int, int]  # Local x, y, z within chunk
    component_type: str
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass 
class ItemContainerData:
    """Represents an item container (chest, etc.)"""
    position: Tuple[int, int, int]
    capacity: int = 0
    items: List[Dict[str, Any]] = field(default_factory=list)
    allow_viewing: bool = True
    custom_name: Optional[str] = None
    who_placed_uuid: Optional[str] = None
    placed_by_interaction: bool = False


@dataclass
class ChunkSectionData:
    """Represents a 32x32x32 chunk section"""
    section_y: int
    block_palette: List[str] = field(default_factory=list)
    block_data: Optional[bytes] = None
    filler_data: Optional[bytes] = None
    rotation_data: Optional[bytes] = None
    physics_data: Optional[bytes] = None
    fluid_data: Optional[bytes] = None
    has_light_data: bool = False


@dataclass
class ParsedChunkData:
    """Complete parsed chunk data"""
    chunk_x: int = 0
    chunk_z: int = 0
    version: int = 0
    sections: List[ChunkSectionData] = field(default_factory=list)
    block_components: List[BlockComponent] = field(default_factory=list)
    containers: List[ItemContainerData] = field(default_factory=list)
    entities: List[Dict[str, Any]] = field(default_factory=list)
    block_names: Set[str] = field(default_factory=set)
    heightmap: Optional[bytes] = None
    tintmap: Optional[bytes] = None
    raw_components: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# IndexedStorageFile Parser
# ============================================================================

class IndexedStorageFile:
    """Parser for IndexedStorageFile format used by Hytale"""
    
    MAGIC_STRING = b"HytaleIndexedStorage"
    MAGIC_LENGTH = 20
    VERSION_OFFSET = 20
    BLOB_COUNT_OFFSET = 24
    SEGMENT_SIZE_OFFSET = 28
    HEADER_LENGTH = 32
    
    BLOB_HEADER_LENGTH = 8
    SRC_LENGTH_OFFSET = 0
    COMPRESSED_LENGTH_OFFSET = 4
    
    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.version = None
        self.blob_count = None
        self.segment_size = None
        self.blob_indexes = []
        
    def read_header(self, f: io.BufferedReader) -> bool:
        """Read and validate the file header"""
        f.seek(0)
        header = f.read(self.HEADER_LENGTH)
        
        if len(header) < self.HEADER_LENGTH:
            print(f"Error: File too small, expected at least {self.HEADER_LENGTH} bytes")
            return False
        
        # Check magic
        magic = header[:self.MAGIC_LENGTH]
        if magic != self.MAGIC_STRING:
            print(f"Error: Invalid magic string. Expected {self.MAGIC_STRING}, got {magic}")
            return False
        
        # Read version
        self.version = struct.unpack('>I', header[self.VERSION_OFFSET:self.VERSION_OFFSET+4])[0]
        if self.version < 0 or self.version > 1:
            print(f"Error: Unsupported version {self.version}")
            return False
        
        # Read blob count and segment size
        self.blob_count = struct.unpack('>I', header[self.BLOB_COUNT_OFFSET:self.BLOB_COUNT_OFFSET+4])[0]
        self.segment_size = struct.unpack('>I', header[self.SEGMENT_SIZE_OFFSET:self.SEGMENT_SIZE_OFFSET+4])[0]
        
        print(f"File: {self.filepath.name}")
        print(f"  Version: {self.version}")
        print(f"  Blob count: {self.blob_count}")
        print(f"  Segment size: {self.segment_size}")
        
        return True
    
    def read_blob_indexes(self, f: io.BufferedReader):
        """Read the blob index table"""
        f.seek(self.HEADER_LENGTH)
        index_data = f.read(self.blob_count * 4)
        
        self.blob_indexes = []
        for i in range(self.blob_count):
            offset = i * 4
            segment_index = struct.unpack('>I', index_data[offset:offset+4])[0]
            self.blob_indexes.append(segment_index)
    
    def segments_base(self) -> int:
        """Get the file position where segments start"""
        return self.HEADER_LENGTH + self.blob_count * 4
    
    def segment_position(self, segment_index: int) -> int:
        """Convert segment index to file position"""
        if segment_index == 0:
            raise ValueError("Invalid segment index 0")
        segment_offset = (segment_index - 1) * self.segment_size
        return segment_offset + self.segments_base()
    
    def read_blob(self, f: io.BufferedReader, blob_index: int) -> Optional[bytes]:
        """Read and decompress a blob"""
        if blob_index < 0 or blob_index >= self.blob_count:
            raise IndexError(f"Blob index {blob_index} out of range")
        
        first_segment_index = self.blob_indexes[blob_index]
        if first_segment_index == 0:
            return None  # No data for this blob
        
        # Read blob header
        pos = self.segment_position(first_segment_index)
        f.seek(pos)
        blob_header = f.read(self.BLOB_HEADER_LENGTH)
        
        src_length = struct.unpack('>I', blob_header[self.SRC_LENGTH_OFFSET:self.SRC_LENGTH_OFFSET+4])[0]
        compressed_length = struct.unpack('>I', blob_header[self.COMPRESSED_LENGTH_OFFSET:self.COMPRESSED_LENGTH_OFFSET+4])[0]
        
        # Read compressed data
        compressed_data = f.read(compressed_length)
        
        if len(compressed_data) != compressed_length:
            print(f"Warning: Expected {compressed_length} bytes, got {len(compressed_data)}")
            return None
        
        # Decompress
        try:
            dctx = zstd.ZstdDecompressor()
            decompressed = dctx.decompress(compressed_data, max_output_size=src_length)
            return decompressed
        except Exception as e:
            print(f"Error decompressing blob {blob_index}: {e}")
            return None
    
    def get_chunk_coordinates(self, blob_index: int, region_x: int, region_z: int) -> Tuple[int, int]:
        """Convert blob index to chunk coordinates"""
        # Each region is 32x32 chunks (1024 total)
        local_x = blob_index % 32
        local_z = blob_index // 32
        
        chunk_x = (region_x << 5) | local_x
        chunk_z = (region_z << 5) | local_z
        
        return chunk_x, chunk_z


# ============================================================================
# Chunk Data Parser
# ============================================================================

class ChunkDataParser:
    """Parser for chunk data in Hytale's custom codec format (BSON-based)"""
    
    # Known component types in chunk data
    KNOWN_COMPONENTS = {
        'WorldChunk', 'BlockChunk', 'BlockComponentChunk', 'BlockComponents',
        'ChunkColumn', 'ChunkSection', 'EntityChunk', 'EnvironmentChunk',
        'Block', 'BlockPhysics', 'FluidSection', 'Fluid'
    }
    
    # Known block state types
    KNOWN_BLOCK_STATES = {
        'ItemContainerState', 'SignState', 'BedState', 'DoorState',
        'TrapDoorState', 'FenceGateState', 'LeverState', 'ButtonState',
        'PressurePlateState', 'TorchState', 'LampState', 'BellState'
    }
    
    # Block name pattern: Category_SubCategory_Details (e.g., Rock_Stone_Mossy)
    BLOCK_NAME_PATTERN = re.compile(
        r'^([A-Z][a-z]+)_([A-Z][a-z][a-z0-9]*)(?:_[A-Z][a-z][a-z0-9]*)*$'
    )
    
    def __init__(self, data: bytes):
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
    
    def skip_bytes(self, count: int):
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
        except Exception as e:
            return None
    
    def extract_block_names_from_bytes(self) -> Set[str]:
        """Extract block names using pattern matching on binary data"""
        block_names = set()
        
        # Decode with replacement character for invalid sequences
        try:
            text = self.data.decode('utf-8', errors='replace')
        except:
            return block_names
        
        # Block name categories - these are validated prefixes
        VALID_PREFIXES = {
            'Rock_', 'Soil_', 'Plant_', 'Wood_', 'Ore_', 'Furniture_', 
            'Rubble_', 'Metal_', 'Stone_', 'Grass_', 'Tree_', 'Water_', 
            'Lava_', 'Ice_', 'Sand_', 'Brick_', 'Glass_', 'Cloth_', 
            'Roof_', 'Survival_', 'Structure_', 'Decor_', 'Light_',
            'Fence_', 'Wall_', 'Floor_', 'Stair_', 'Door_', 'Window_',
            'Chest_', 'Barrel_', 'Crate_', 'Tool_', 'Weapon_',
            'Crystal_', 'Coral_', 'Seaweed_', 'Shell_', 'Kelp_'
        }
        
        # Pattern: Capital + lowercase letters, then (_Capital + lowercase/digits)+
        pattern = r'(?<![A-Za-z0-9_])([A-Z][a-z]+(?:_[A-Z][a-z][a-z0-9]*)+)(?![a-z])'
        
        for match in re.finditer(pattern, text):
            name = match.group(1)
            
            # Skip if contains replacement character
            if '\ufffd' in name:
                continue
                
            # Check if starts with valid prefix
            has_valid_prefix = any(name.startswith(prefix) for prefix in VALID_PREFIXES)
            if not has_valid_prefix:
                continue
            
            # Verify each segment is properly formed
            segments = name.split('_')
            valid = True
            for seg in segments:
                if len(seg) < 2 or not seg[0].isupper():
                    valid = False
                    break
                rest = seg[1:]
                if not rest or not all(c.islower() or c.isdigit() for c in rest):
                    valid = False
                    break
                if not any(c.islower() for c in rest):
                    valid = False
                    break
            
            if valid and len(name) <= 80:
                block_names.add(name)
        
        return block_names
    
    def parse_block_components(self, doc: Dict[str, Any]) -> List[BlockComponent]:
        """Parse BlockComponentChunk/BlockComponents from BSON document"""
        components = []
        
        # Look for BlockComponents in the document
        block_components = doc.get('BlockComponents', {})
        
        if isinstance(block_components, dict):
            for index_str, component_data in block_components.items():
                try:
                    index = int(index_str)
                    
                    # Calculate position from index
                    # Index = x + y*32 + z*32*32 for a section
                    x = index % 32
                    y = (index // 32) % 32
                    z = index // (32 * 32)
                    
                    # Determine component type
                    comp_type = "Unknown"
                    if isinstance(component_data, dict):
                        comp_type = component_data.get('Type', 'Unknown')
                        
                    component = BlockComponent(
                        index=index,
                        position=(x, y, z),
                        component_type=comp_type,
                        data=component_data if isinstance(component_data, dict) else {}
                    )
                    components.append(component)
                except (ValueError, TypeError):
                    continue
        
        return components
    
    def parse_item_containers(self, doc: Dict[str, Any]) -> List[ItemContainerData]:
        """Parse ItemContainer data from BSON document"""
        containers = []
        
        # Search recursively for ItemContainer data
        def find_containers(obj: Any, path: str = "") -> List[ItemContainerData]:
            result = []
            
            if isinstance(obj, dict):
                # Check for container component (nested in Components > container)
                inner_container = None
                if 'Components' in obj and isinstance(obj['Components'], dict):
                    inner_container = obj['Components'].get('container')
                
                # Check if this is an ItemContainerState or has ItemContainer directly
                container_obj = inner_container or obj
                
                if container_obj and isinstance(container_obj, dict):
                    if (container_obj.get('Type') == 'ItemContainerState' or 
                        'ItemContainer' in container_obj):
                        
                        pos = container_obj.get('Position', {})
                        if isinstance(pos, dict):
                            position = (pos.get('X', 0), pos.get('Y', 0), pos.get('Z', 0))
                        else:
                            position = (0, 0, 0)
                        
                        item_container = container_obj.get('ItemContainer', {})
                        capacity = item_container.get('Capacity', 0) if isinstance(item_container, dict) else 0
                        
                        container = ItemContainerData(
                            position=position,
                            capacity=capacity,
                            allow_viewing=container_obj.get('AllowViewing', True),
                            custom_name=container_obj.get('Custom_Name'),
                            who_placed_uuid=container_obj.get('WhoPlacedUuid'),
                            placed_by_interaction=container_obj.get('PlacedByInteraction', False)
                        )
                        
                        # Parse items if present
                        if isinstance(item_container, dict):
                            items = item_container.get('Items', {})
                            # Items can be a dict with slot numbers as keys
                            if isinstance(items, dict):
                                container.items = list(items.values())
                            elif isinstance(items, list):
                                container.items = items
                        
                        result.append(container)
                
                # Recurse into dict values (but avoid double-counting)
                for key, value in obj.items():
                    if key not in ('Components',):  # Don't recurse into nested components we already handled
                        result.extend(find_containers(value, f"{path}.{key}"))
                    
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    result.extend(find_containers(item, f"{path}[{i}]"))
            
            return result
        
        return find_containers(doc)
    
    def parse(self) -> ParsedChunkData:
        """Parse chunk data and extract all components"""
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
        
        # Also extract block names from raw bytes (for palette data)
        result.block_names = self.extract_block_names_from_bytes()
        
        return result
    
    def parse_block_section(self, section_index: int) -> Optional[ChunkSectionData]:
        """Parse a single block section"""
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
            
        except Exception as e:
            pass
        
        return section
# ============================================================================
# Region File Parser
# ============================================================================

class RegionFileParser:
    """Parser for .region.bin files"""
    
    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.storage = IndexedStorageFile(filepath)
        self.region_x = None
        self.region_z = None
        
    def parse_filename(self) -> bool:
        """Extract region coordinates from filename"""
        filename = self.filepath.stem  # Remove .bin extension
        parts = filename.split('.')
        
        if len(parts) != 3 or parts[2] != 'region':
            print(f"Error: Invalid filename format. Expected X.Z.region.bin")
            return False
        
        try:
            self.region_x = int(parts[0])
            self.region_z = int(parts[1])
            print(f"\nRegion coordinates: ({self.region_x}, {self.region_z})")
            return True
        except ValueError:
            print(f"Error: Could not parse region coordinates from filename")
            return False
    
    def parse(self):
        """Parse the region file and list all chunks"""
        if not self.parse_filename():
            return
        
        with open(self.filepath, 'rb') as f:
            if not self.storage.read_header(f):
                return
            
            self.storage.read_blob_indexes(f)
            
            # Find all chunks with data
            chunks_with_data = []
            for blob_index in range(self.storage.blob_count):
                if self.storage.blob_indexes[blob_index] != 0:
                    chunks_with_data.append(blob_index)
            
            print(f"\nChunks with data: {len(chunks_with_data)}/{self.storage.blob_count}")
            print("\nChunk list:")
            print("-" * 80)
            
            for blob_index in chunks_with_data:
                chunk_x, chunk_z = self.storage.get_chunk_coordinates(blob_index, self.region_x, self.region_z)
                
                # Read the chunk data
                chunk_data = self.storage.read_blob(f, blob_index)
                
                if chunk_data:
                    print(f"Chunk ({chunk_x:4d}, {chunk_z:4d}) - Blob {blob_index:4d} - Size: {len(chunk_data):8d} bytes")
                    
                    # Try to analyze the chunk data
                    self.analyze_chunk_data(chunk_data, chunk_x, chunk_z)
                else:
                    print(f"Chunk ({chunk_x:4d}, {chunk_z:4d}) - Blob {blob_index:4d} - Failed to read")
    
    def parse_summary(self):
        """Parse the region file and show a summary of all blocks"""
        if not self.parse_filename():
            return
        
        all_blocks = {}
        all_containers = []
        all_components = []
        
        with open(self.filepath, 'rb') as f:
            if not self.storage.read_header(f):
                return
            
            self.storage.read_blob_indexes(f)
            
            # Find all chunks with data
            chunks_with_data = []
            for blob_index in range(self.storage.blob_count):
                if self.storage.blob_indexes[blob_index] != 0:
                    chunks_with_data.append(blob_index)
            
            print(f"\nRegion ({self.region_x}, {self.region_z})")
            print(f"Chunks with data: {len(chunks_with_data)}/{self.storage.blob_count}")
            print("\nProcessing chunks...")
            
            for i, blob_index in enumerate(chunks_with_data):
                if i % 100 == 0:
                    print(f"  Progress: {i}/{len(chunks_with_data)} chunks processed")
                
                chunk_data = self.storage.read_blob(f, blob_index)
                chunk_x, chunk_z = self.storage.get_chunk_coordinates(blob_index, self.region_x, self.region_z)
                
                if chunk_data:
                    parser = ChunkDataParser(chunk_data)
                    try:
                        result = parser.parse()
                        
                        # Collect block names
                        for block_name in result.block_names:
                            all_blocks[block_name] = all_blocks.get(block_name, 0) + 1
                        
                        # Collect containers
                        for container in result.containers:
                            container_info = {
                                'chunk': (chunk_x, chunk_z),
                                'position': container.position,
                                'capacity': container.capacity,
                                'items_count': len(container.items)
                            }
                            all_containers.append(container_info)
                        
                        # Collect block components
                        for component in result.block_components:
                            comp_info = {
                                'chunk': (chunk_x, chunk_z),
                                'position': component.position,
                                'type': component.component_type,
                                'index': component.index
                            }
                            all_components.append(comp_info)
                            
                    except Exception as e:
                        pass
        
        # Print summary
        print(f"\n{'='*80}")
        print(f"SUMMARY - Region ({self.region_x}, {self.region_z})")
        print(f"{'='*80}")
        
        # Block types
        print(f"\nTotal unique block types: {len(all_blocks)}")
        print("\nAll blocks (sorted by occurrence count):")
        print("-" * 80)
        
        sorted_blocks = sorted(all_blocks.items(), key=lambda x: -x[1])
        
        for block_type, count in sorted_blocks:
            print(f"  {block_type}: {count} occurrences")
        
        # Group by category
        print(f"\n{'='*80}")
        print("Blocks by Category:")
        print(f"{'='*80}")
        
        categories = {}
        for block_type in all_blocks.keys():
            if '_' in block_type:
                category = block_type.split('_')[0]
                if category not in categories:
                    categories[category] = []
                categories[category].append(block_type)
        
        for category in sorted(categories.keys()):
            blocks_in_category = sorted(categories[category])
            print(f"\n{category} ({len(blocks_in_category)} types):")
            for block_type in blocks_in_category:
                print(f"  - {block_type} ({all_blocks[block_type]} occurrences)")
        
        # Print containers if any
        if all_containers:
            print(f"\n{'='*80}")
            print(f"ITEM CONTAINERS ({len(all_containers)} total):")
            print(f"{'='*80}")
            for container in all_containers[:50]:  # Limit output
                print(f"  Chunk {container['chunk']}, Position {container['position']}, "
                      f"Capacity: {container['capacity']}, Items: {container['items_count']}")
            if len(all_containers) > 50:
                print(f"  ... and {len(all_containers) - 50} more containers")
        
        # Print block components if any
        if all_components:
            print(f"\n{'='*80}")
            print(f"BLOCK COMPONENTS ({len(all_components)} total):")
            print(f"{'='*80}")
            
            # Group by type
            comp_by_type = {}
            for comp in all_components:
                comp_type = comp['type']
                if comp_type not in comp_by_type:
                    comp_by_type[comp_type] = []
                comp_by_type[comp_type].append(comp)
            
            for comp_type, comps in sorted(comp_by_type.items()):
                print(f"\n  {comp_type}: {len(comps)} instances")
                for comp in comps[:10]:
                    print(f"    - Chunk {comp['chunk']}, Position {comp['position']}")
                if len(comps) > 10:
                    print(f"    ... and {len(comps) - 10} more")

    def parse_detailed(self, max_chunks: int = 5):
        """Parse with detailed BSON structure output for debugging"""
        if not self.parse_filename():
            return
        
        with open(self.filepath, 'rb') as f:
            if not self.storage.read_header(f):
                return
            
            self.storage.read_blob_indexes(f)
            
            # Find all chunks with data
            chunks_with_data = []
            for blob_index in range(self.storage.blob_count):
                if self.storage.blob_indexes[blob_index] != 0:
                    chunks_with_data.append(blob_index)
            
            print(f"\nAnalyzing first {max_chunks} chunks in detail...")
            print("-" * 80)
            
            for i, blob_index in enumerate(chunks_with_data[:max_chunks]):
                chunk_x, chunk_z = self.storage.get_chunk_coordinates(blob_index, self.region_x, self.region_z)
                chunk_data = self.storage.read_blob(f, blob_index)
                
                if chunk_data:
                    print(f"\n{'='*80}")
                    print(f"CHUNK ({chunk_x}, {chunk_z}) - Blob {blob_index}")
                    print(f"Data size: {len(chunk_data)} bytes")
                    print(f"{'='*80}")
                    
                    parser = ChunkDataParser(chunk_data)
                    result = parser.parse()
                    
                    # Print raw BSON structure if available
                    if result.raw_components:
                        print("\nBSON Document Structure:")
                        self._print_bson_structure(result.raw_components, indent=2)
                    
                    # Print block names found
                    if result.block_names:
                        print(f"\nBlock names found: {len(result.block_names)}")
                        for name in sorted(result.block_names)[:20]:
                            print(f"  - {name}")
                        if len(result.block_names) > 20:
                            print(f"  ... and {len(result.block_names) - 20} more")
                    
                    # Print components
                    if result.block_components:
                        print(f"\nBlock components: {len(result.block_components)}")
                        for comp in result.block_components[:5]:
                            print(f"  - {comp.component_type} at {comp.position}")
                    
                    # Print containers
                    if result.containers:
                        print(f"\nContainers: {len(result.containers)}")
                        for cont in result.containers[:5]:
                            print(f"  - Position {cont.position}, Capacity: {cont.capacity}")
    
    def _print_bson_structure(self, obj: Any, indent: int = 0):
        """Print BSON structure recursively"""
        prefix = " " * indent
        
        if isinstance(obj, dict):
            for key, value in list(obj.items())[:20]:  # Limit keys shown
                if isinstance(value, dict):
                    print(f"{prefix}{key}: {{")
                    self._print_bson_structure(value, indent + 2)
                    print(f"{prefix}}}")
                elif isinstance(value, list):
                    print(f"{prefix}{key}: [{len(value)} items]")
                    if value and len(value) <= 3:
                        for item in value:
                            self._print_bson_structure(item, indent + 2)
                elif isinstance(value, bytes):
                    print(f"{prefix}{key}: <binary {len(value)} bytes>")
                elif isinstance(value, tuple) and len(value) == 2:
                    # Binary with subtype
                    print(f"{prefix}{key}: <binary subtype={value[0]}, {len(value[1])} bytes>")
                else:
                    val_str = str(value)
                    if len(val_str) > 50:
                        val_str = val_str[:50] + "..."
                    print(f"{prefix}{key}: {val_str}")
            
            if len(obj) > 20:
                print(f"{prefix}... and {len(obj) - 20} more keys")
                
        elif isinstance(obj, list):
            for i, item in enumerate(obj[:5]):
                print(f"{prefix}[{i}]:")
                self._print_bson_structure(item, indent + 2)
            if len(obj) > 5:
                print(f"{prefix}... and {len(obj) - 5} more items")
        else:
            print(f"{prefix}{obj}")
    
    def analyze_chunk_data(self, data: bytes, chunk_x: int, chunk_z: int):
        """Attempt to analyze chunk data structure"""
        parser = ChunkDataParser(data)
        
        try:
            result = parser.parse()
            
            # Display blocks
            if result.block_names:
                print(f"  Blocks found: {len(result.block_names)} unique types")
                
                # Show top blocks
                blocks_sorted = sorted(result.block_names)
                for block in blocks_sorted[:20]:
                    print(f"    - {block}")
                
                if len(result.block_names) > 20:
                    print(f"    ... and {len(result.block_names) - 20} more block types")
            
            # Display components
            if result.block_components:
                print(f"  Block components: {len(result.block_components)}")
                for comp in result.block_components[:5]:
                    print(f"    - {comp.component_type} at position {comp.position}")
            
            # Display containers
            if result.containers:
                print(f"  Containers: {len(result.containers)}")
                for container in result.containers[:5]:
                    print(f"    - Position {container.position}, Capacity: {container.capacity}")
        
        except Exception as e:
            print(f"  Error parsing chunk data: {e}")
            import traceback
            traceback.print_exc()
        
        print()
    
    def find_printable_strings(self, data: bytes, min_length: int = 4) -> List[str]:
        """Find printable ASCII strings in binary data"""
        strings = []
        current = []
        
        for byte in data:
            if 32 <= byte <= 126:  # Printable ASCII
                current.append(chr(byte))
            else:
                if len(current) >= min_length:
                    strings.append(''.join(current))
                current = []
        
        if len(current) >= min_length:
            strings.append(''.join(current))
        
        return strings


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python parse_region.py <region_file.bin> [options]")
        print("\nExample: python parse_region.py chunks/0.0.region.bin")
        print("         python parse_region.py chunks/0.0.region.bin --summary")
        print("         python parse_region.py chunks/0.0.region.bin --detailed")
        print("\nOptions:")
        print("  --summary    Show summary of all unique blocks, containers, and components")
        print("  --detailed   Show detailed BSON structure of first few chunks")
        sys.exit(1)
    
    filepath = Path(sys.argv[1])
    
    if not filepath.exists():
        print(f"Error: File not found: {filepath}")
        sys.exit(1)
    
    parser = RegionFileParser(filepath)
    
    if '--summary' in sys.argv:
        parser.parse_summary()
    elif '--detailed' in sys.argv:
        parser.parse_detailed()
    else:
        parser.parse()


if __name__ == '__main__':
    main()
