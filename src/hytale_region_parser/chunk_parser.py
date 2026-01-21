"""
Chunk Data Parser

Parser for chunk data in Hytale's custom codec format (BSON-based).
"""

import re
import struct
from typing import Any, Dict, List, Optional, Set

from .bson_parser import BsonParser
from .models import (
    BlockComponent,
    ChunkSectionData,
    ItemContainerData,
    ParsedChunkData,
)


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
    
    # Valid block name prefixes
    VALID_PREFIXES = {
        'Rock_', 'Soil_', 'Plant_', 'Wood_', 'Ore_', 'Furniture_', 
        'Rubble_', 'Metal_', 'Stone_', 'Grass_', 'Tree_', 'Water_', 
        'Lava_', 'Ice_', 'Sand_', 'Brick_', 'Glass_', 'Cloth_', 
        'Roof_', 'Survival_', 'Structure_', 'Decor_', 'Light_',
        'Fence_', 'Wall_', 'Floor_', 'Stair_', 'Door_', 'Window_',
        'Chest_', 'Barrel_', 'Crate_', 'Tool_', 'Weapon_',
        'Crystal_', 'Coral_', 'Seaweed_', 'Shell_', 'Kelp_'
    }
    
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
    
    def extract_block_names_from_bytes(self) -> Set[str]:
        """Extract block names using pattern matching on binary data"""
        block_names: Set[str] = set()
        
        # Decode with replacement character for invalid sequences
        try:
            text = self.data.decode('utf-8', errors='replace')
        except Exception:
            return block_names
        
        # Pattern: Capital + lowercase letters, then (_Capital + lowercase/digits)+
        pattern = r'(?<![A-Za-z0-9_])([A-Z][a-z]+(?:_[A-Z][a-z][a-z0-9]*)+)(?![a-z])'
        
        for match in re.finditer(pattern, text):
            name = match.group(1)
            
            # Skip if contains replacement character
            if '\ufffd' in name:
                continue
                
            # Check if starts with valid prefix
            has_valid_prefix = any(name.startswith(prefix) for prefix in self.VALID_PREFIXES)
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
        containers: List[ItemContainerData] = []
        
        # Search recursively for ItemContainer data
        def find_containers(obj: Any, path: str = "") -> List[ItemContainerData]:
            result: List[ItemContainerData] = []
            
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
        
        # Also extract block names from raw bytes (for palette data)
        result.block_names = self.extract_block_names_from_bytes()
        
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
