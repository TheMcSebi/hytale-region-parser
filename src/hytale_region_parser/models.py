"""
Data Models for Hytale Region Parser

This module contains dataclasses representing the various data structures
found in Hytale region files.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


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
class BlockPaletteEntry:
    """Represents a single entry in the block palette"""
    internal_id: int
    name: str
    count: int


@dataclass
class ChunkSectionData:
    """Represents a 32x32x32 chunk section"""
    section_y: int
    block_palette: List[BlockPaletteEntry] = field(default_factory=list)
    block_counts: Dict[str, int] = field(default_factory=dict)  # Block name -> count
    block_indices: Optional[bytes] = None  # Raw block index data
    palette_type: int = 0  # 0=Empty, 1=HalfByte, 2=Byte, 3=Short


@dataclass
class ParsedChunkData:
    """Complete parsed chunk data from a region file"""
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

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert chunk data to a JSON-serializable dictionary.

        Returns:
            Dictionary with position keys "x,y,z" mapping to block data
        """
        result: Dict[str, Any] = {}

        # Add containers with their positions as keys
        for container in self.containers:
            x, y, z = container.position
            key = f"{x},{y},{z}"
            result[key] = {
                "type": "container",
                "capacity": container.capacity,
                "items": container.items,
                "allow_viewing": container.allow_viewing,
                "custom_name": container.custom_name,
                "who_placed_uuid": container.who_placed_uuid,
                "placed_by_interaction": container.placed_by_interaction,
            }

        # Add block components with their positions as keys
        for component in self.block_components:
            x, y, z = component.position
            key = f"{x},{y},{z}"
            if key in result:
                # Merge with existing entry
                if "components" not in result[key]:
                    result[key]["components"] = {}
                result[key]["components"][component.component_type] = component.data
            else:
                result[key] = {
                    "type": "block_component",
                    "components": {
                        component.component_type: component.data
                    }
                }

        return result
