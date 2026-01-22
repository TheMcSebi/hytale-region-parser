"""
Region File Parser

High-level parser for Hytale .region.bin files.
"""

import json
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from .chunk_parser import ChunkDataParser
from .models import ChunkSectionData, ParsedChunkData
from .storage import IndexedStorageFile


class RegionFileParser:
    """
    Parser for .region.bin files.
    
    This class provides methods to read and parse Hytale region files,
    extracting chunk data, block information, and other game data.
    
    Example:
        >>> parser = RegionFileParser(Path("0.0.region.bin"))
        >>> for chunk in parser.iter_chunks():
        ...     print(f"Chunk at ({chunk.chunk_x}, {chunk.chunk_z})")
    """

    def __init__(self, filepath: Path):
        """
        Initialize the region file parser.
        
        Args:
            filepath: Path to the .region.bin file
        """
        self.filepath = Path(filepath)
        self.storage = IndexedStorageFile(self.filepath)
        self.region_x: Optional[int] = None
        self.region_z: Optional[int] = None
        self._file_handle = None

    def parse_filename(self) -> bool:
        """
        Extract region coordinates from filename.
        
        Returns:
            True if coordinates were successfully parsed, False otherwise
        """
        filename = self.filepath.stem  # Remove .bin extension
        parts = filename.split('.')

        if len(parts) != 3 or parts[2] != 'region':
            return False

        try:
            self.region_x = int(parts[0])
            self.region_z = int(parts[1])
            return True
        except ValueError:
            return False

    @property
    def coordinates(self) -> Optional[Tuple[int, int]]:
        """Get the region coordinates as a tuple, or None if not parsed."""
        if self.region_x is not None and self.region_z is not None:
            return (self.region_x, self.region_z)
        return None

    def open(self) -> bool:
        """
        Open the region file and read headers.
        
        Returns:
            True if file was opened successfully, False otherwise
        """
        if not self.parse_filename():
            return False

        try:
            self._file_handle = open(self.filepath, 'rb')
            if not self.storage.read_header(self._file_handle, verbose=False):
                self.close()
                return False
            self.storage.read_blob_indexes(self._file_handle)
            return True
        except Exception:
            self.close()
            return False

    def close(self) -> None:
        """Close the region file."""
        if self._file_handle:
            self._file_handle.close()
            self._file_handle = None

    def __enter__(self):
        """Context manager entry."""
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False

    def get_chunk_count(self) -> int:
        """
        Get the total number of chunks that have data.
        
        Returns:
            Number of chunks with data
        """
        return sum(1 for idx in self.storage.blob_indexes if idx != 0)

    def get_chunk_indexes(self) -> List[int]:
        """
        Get list of blob indexes that have chunk data.
        
        Returns:
            List of blob indexes with data
        """
        return [i for i, idx in enumerate(self.storage.blob_indexes) if idx != 0]

    def read_chunk(self, blob_index: int) -> Optional[ParsedChunkData]:
        """
        Read and parse a single chunk by blob index.
        
        Args:
            blob_index: The blob index within the region file
            
        Returns:
            ParsedChunkData if successful, None otherwise
        """
        if not self._file_handle:
            raise RuntimeError("File not open. Call open() first or use context manager.")

        chunk_data = self.storage.read_blob(self._file_handle, blob_index)
        if not chunk_data:
            return None

        chunk_x, chunk_z = self.storage.get_chunk_coordinates(
            blob_index, self.region_x, self.region_z
        )

        parser = ChunkDataParser(chunk_data)
        result = parser.parse()
        result.chunk_x = chunk_x
        result.chunk_z = chunk_z

        return result

    def iter_chunks(self) -> Iterator[ParsedChunkData]:
        """
        Iterate over all chunks in the region file.
        
        Yields:
            ParsedChunkData for each chunk with data
        """
        if not self._file_handle:
            raise RuntimeError("File not open. Call open() first or use context manager.")

        for blob_index in self.get_chunk_indexes():
            chunk = self.read_chunk(blob_index)
            if chunk:
                yield chunk

    def to_dict(self, include_all_blocks: bool = True) -> Dict[str, Any]:
        """
        Convert all region data to a JSON-serializable dictionary.
        
        Args:
            include_all_blocks: If True, includes all terrain blocks from sections.
                               If False, only includes containers and block components.
        
        Format:
            {
                "metadata": {
                    "region_x": int,
                    "region_z": int,
                    "chunk_count": int,
                    "block_summary": {"Block_Name": count, ...}
                },
                "blocks": {
                    "x,y,z": {
                        "name": "Block_Name",
                        "components": {...},
                        ...
                    },
                    ...
                }
            }
        
        Returns:
            Dictionary with metadata and blocks
        """
        blocks: Dict[str, Any] = {}
        block_summary: Dict[str, int] = {}
        chunk_count = 0

        for chunk in self.iter_chunks():
            chunk_count += 1
            chunk_base_x = chunk.chunk_x * 32
            chunk_base_z = chunk.chunk_z * 32

            # Add containers with world positions
            for container in chunk.containers:
                local_x, y, local_z = container.position
                world_x = chunk_base_x + local_x
                world_z = chunk_base_z + local_z
                key = f"{world_x},{y},{world_z}"

                blocks[key] = {
                    "name": "Container",
                    "components": {
                        "container": {
                            "capacity": container.capacity,
                            "items": container.items,
                            "allow_viewing": container.allow_viewing,
                            "custom_name": container.custom_name,
                            "who_placed_uuid": container.who_placed_uuid,
                            "placed_by_interaction": container.placed_by_interaction,
                        }
                    }
                }
                block_summary["Container"] = block_summary.get("Container", 0) + 1

            # Add block components with world positions
            for component in chunk.block_components:
                local_x, y, local_z = component.position
                world_x = chunk_base_x + local_x
                world_z = chunk_base_z + local_z
                key = f"{world_x},{y},{world_z}"

                if key in blocks:
                    # Merge with existing entry
                    if "components" not in blocks[key]:
                        blocks[key]["components"] = {}
                    blocks[key]["components"][component.component_type] = component.data
                else:
                    blocks[key] = {
                        "name": component.component_type,
                        "components": {
                            component.component_type: component.data
                        }
                    }

            # Add all blocks from sections if requested
            if include_all_blocks:
                for section in chunk.sections:
                    section_base_y = section.section_y * 32

                    # Aggregate block counts from section
                    for block_name, count in section.block_counts.items():
                        if block_name and block_name != "Empty":
                            block_summary[block_name] = block_summary.get(block_name, 0) + count

                    # If we have block indices, we can compute positions
                    if section.block_indices and section.block_palette:
                        self._extract_block_positions(
                            section, chunk_base_x, section_base_y, chunk_base_z, blocks
                        )

        return {
            "metadata": {
                "region_x": self.region_x,
                "region_z": self.region_z,
                "chunk_count": chunk_count,
                "block_summary": block_summary
            },
            "blocks": blocks
        }

    def _extract_block_positions(
        self,
        section: 'ChunkSectionData',
        chunk_base_x: int,
        section_base_y: int,
        chunk_base_z: int,
        blocks: Dict[str, Any]
    ) -> None:
        """
        Extract individual block positions from section indices.
        
        This method decodes the block indices to get exact positions.
        Only non-Empty blocks are added to the output.
        """
        if not section.block_indices or not section.block_palette:
            return

        # Build internal ID -> block name lookup
        id_to_name: Dict[int, str] = {}
        for entry in section.block_palette:
            id_to_name[entry.internal_id] = entry.name

        indices = section.block_indices
        palette_type = section.palette_type

        # Section size is 32x32x32 = 32768 blocks
        # Index = x + z*32 + y*32*32

        if palette_type == 1:  # HalfByte (nibble) storage
            # Each byte contains 2 block indices (4 bits each)
            for byte_idx, byte_val in enumerate(indices):
                block_idx_low = byte_idx * 2
                block_idx_high = byte_idx * 2 + 1

                low_nibble = byte_val & 0x0F
                high_nibble = (byte_val >> 4) & 0x0F

                # Process low nibble
                if block_idx_low < 32768:
                    name = id_to_name.get(low_nibble, "Unknown")
                    if name and name != "Empty":
                        local_x = block_idx_low % 32
                        local_z = (block_idx_low // 32) % 32
                        local_y = block_idx_low // (32 * 32)

                        world_x = chunk_base_x + local_x
                        world_y = section_base_y + local_y
                        world_z = chunk_base_z + local_z
                        key = f"{world_x},{world_y},{world_z}"

                        if key not in blocks:
                            blocks[key] = {"name": name}

                # Process high nibble
                if block_idx_high < 32768:
                    name = id_to_name.get(high_nibble, "Unknown")
                    if name and name != "Empty":
                        local_x = block_idx_high % 32
                        local_z = (block_idx_high // 32) % 32
                        local_y = block_idx_high // (32 * 32)

                        world_x = chunk_base_x + local_x
                        world_y = section_base_y + local_y
                        world_z = chunk_base_z + local_z
                        key = f"{world_x},{world_y},{world_z}"

                        if key not in blocks:
                            blocks[key] = {"name": name}

        elif palette_type == 2:  # Byte storage
            for block_idx, internal_id in enumerate(indices):
                if block_idx >= 32768:
                    break
                name = id_to_name.get(internal_id, "Unknown")
                if name and name != "Empty":
                    local_x = block_idx % 32
                    local_z = (block_idx // 32) % 32
                    local_y = block_idx // (32 * 32)

                    world_x = chunk_base_x + local_x
                    world_y = section_base_y + local_y
                    world_z = chunk_base_z + local_z
                    key = f"{world_x},{world_y},{world_z}"

                    if key not in blocks:
                        blocks[key] = {"name": name}

        elif palette_type == 3:  # Short storage
            import struct
            for i in range(0, min(len(indices), 32768 * 2), 2):
                block_idx = i // 2
                if block_idx >= 32768:
                    break
                internal_id = struct.unpack('>H', indices[i:i+2])[0]
                name = id_to_name.get(internal_id, "Unknown")
                if name and name != "Empty":
                    local_x = block_idx % 32
                    local_z = (block_idx // 32) % 32
                    local_y = block_idx // (32 * 32)

                    world_x = chunk_base_x + local_x
                    world_y = section_base_y + local_y
                    world_z = chunk_base_z + local_z
                    key = f"{world_x},{world_y},{world_z}"

                    if key not in blocks:
                        blocks[key] = {"name": name}

    def to_dict_summary_only(self) -> Dict[str, Any]:
        """
        Convert region data to a summary dictionary (without individual block positions).
        
        This is much faster for large regions as it doesn't decode block positions.
        
        Returns:
            Dictionary with metadata and block counts
        """
        block_summary: Dict[str, int] = {}
        chunk_count = 0
        containers: List[Dict] = []

        for chunk in self.iter_chunks():
            chunk_count += 1
            chunk_base_x = chunk.chunk_x * 32
            chunk_base_z = chunk.chunk_z * 32

            # Collect containers
            for container in chunk.containers:
                local_x, y, local_z = container.position
                world_x = chunk_base_x + local_x
                world_z = chunk_base_z + local_z
                containers.append({
                    "position": [world_x, y, world_z],
                    "capacity": container.capacity,
                    "items_count": len(container.items),
                    "custom_name": container.custom_name
                })
                block_summary["Container"] = block_summary.get("Container", 0) + 1

            # Aggregate block counts from sections
            for section in chunk.sections:
                for block_name, count in section.block_counts.items():
                    if block_name and block_name != "Empty":
                        block_summary[block_name] = block_summary.get(block_name, 0) + count

        return {
            "metadata": {
                "region_x": self.region_x,
                "region_z": self.region_z,
                "chunk_count": chunk_count
            },
            "block_summary": block_summary,
            "containers": containers
        }

    def to_json(self, indent: Optional[int] = 2) -> str:
        """
        Convert all region data to a JSON string.
        
        Args:
            indent: JSON indentation level (None for compact output)
        
        Returns:
            JSON string representation of the region data
        """
        return json.dumps(self.to_dict(), indent=indent, default=str)

    def get_all_blocks(self) -> Dict[str, int]:
        """
        Get a dictionary of all unique block types and their occurrence counts.
        
        Returns:
            Dictionary mapping block names to occurrence counts
        """
        all_blocks: Dict[str, int] = {}

        for chunk in self.iter_chunks():
            for block_name in chunk.block_names:
                all_blocks[block_name] = all_blocks.get(block_name, 0) + 1

        return all_blocks

    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the region file contents.
        
        Returns:
            Dictionary containing summary information
        """
        all_blocks: Dict[str, int] = {}
        all_containers: List[Dict] = []
        all_components: List[Dict] = []
        chunk_count = 0

        for chunk in self.iter_chunks():
            chunk_count += 1

            # Collect block names
            for block_name in chunk.block_names:
                all_blocks[block_name] = all_blocks.get(block_name, 0) + 1

            # Collect containers
            for container in chunk.containers:
                container_info = {
                    'chunk': (chunk.chunk_x, chunk.chunk_z),
                    'position': container.position,
                    'capacity': container.capacity,
                    'items_count': len(container.items)
                }
                all_containers.append(container_info)

            # Collect block components
            for component in chunk.block_components:
                comp_info = {
                    'chunk': (chunk.chunk_x, chunk.chunk_z),
                    'position': component.position,
                    'type': component.component_type,
                    'index': component.index
                }
                all_components.append(comp_info)

        # Group blocks by category
        categories: Dict[str, List[str]] = {}
        for block_type in all_blocks:
            if '_' in block_type:
                category = block_type.split('_')[0]
                if category not in categories:
                    categories[category] = []
                categories[category].append(block_type)

        return {
            'region_x': self.region_x,
            'region_z': self.region_z,
            'chunk_count': chunk_count,
            'total_chunks': self.storage.blob_count,
            'unique_blocks': len(all_blocks),
            'blocks': all_blocks,
            'block_categories': categories,
            'containers': all_containers,
            'components': all_components
        }

    def parse(self, verbose: bool = True) -> None:
        """
        Parse the region file and print all chunks (legacy method).
        
        Args:
            verbose: Whether to print detailed output
        """
        if not self.parse_filename():
            if verbose:
                print("Error: Invalid filename format. Expected X.Z.region.bin")
            return

        with open(self.filepath, 'rb') as f:
            if not self.storage.read_header(f, verbose=verbose):
                return

            self.storage.read_blob_indexes(f)

            # Find all chunks with data
            chunks_with_data = []
            for blob_index in range(self.storage.blob_count):
                if self.storage.blob_indexes[blob_index] != 0:
                    chunks_with_data.append(blob_index)

            if verbose:
                print(f"\nRegion coordinates: ({self.region_x}, {self.region_z})")
                print(f"\nChunks with data: {len(chunks_with_data)}/{self.storage.blob_count}")
                print("\nChunk list:")
                print("-" * 80)

            for blob_index in chunks_with_data:
                chunk_x, chunk_z = self.storage.get_chunk_coordinates(
                    blob_index, self.region_x, self.region_z
                )

                # Read the chunk data
                chunk_data = self.storage.read_blob(f, blob_index)

                if verbose:
                    if chunk_data:
                        print(f"Chunk ({chunk_x:4d}, {chunk_z:4d}) - Blob {blob_index:4d} - Size: {len(chunk_data):8d} bytes")
                        self._analyze_chunk_data(chunk_data, chunk_x, chunk_z)
                    else:
                        print(f"Chunk ({chunk_x:4d}, {chunk_z:4d}) - Blob {blob_index:4d} - Failed to read")

    def parse_summary(self, verbose: bool = True) -> Dict[str, Any]:
        """
        Parse the region file and return/print a summary.
        
        Args:
            verbose: Whether to print detailed output
            
        Returns:
            Summary dictionary
        """
        if not self.parse_filename():
            if verbose:
                print("Error: Invalid filename format. Expected X.Z.region.bin")
            return {}

        all_blocks: Dict[str, int] = {}
        all_containers: List[Dict] = []
        all_components: List[Dict] = []

        with open(self.filepath, 'rb') as f:
            if not self.storage.read_header(f, verbose=verbose):
                return {}

            self.storage.read_blob_indexes(f)

            # Find all chunks with data
            chunks_with_data = []
            for blob_index in range(self.storage.blob_count):
                if self.storage.blob_indexes[blob_index] != 0:
                    chunks_with_data.append(blob_index)

            if verbose:
                print(f"\nRegion ({self.region_x}, {self.region_z})")
                print(f"Chunks with data: {len(chunks_with_data)}/{self.storage.blob_count}")
                print("\nProcessing chunks...")

            for i, blob_index in enumerate(chunks_with_data):
                if verbose and i % 100 == 0:
                    print(f"  Progress: {i}/{len(chunks_with_data)} chunks processed")

                chunk_data = self.storage.read_blob(f, blob_index)
                chunk_x, chunk_z = self.storage.get_chunk_coordinates(
                    blob_index, self.region_x, self.region_z
                )

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

                    except Exception:
                        pass

        if verbose:
            self._print_summary(all_blocks, all_containers, all_components)

        # Group by category
        categories: Dict[str, List[str]] = {}
        for block_type in all_blocks:
            if '_' in block_type:
                category = block_type.split('_')[0]
                if category not in categories:
                    categories[category] = []
                categories[category].append(block_type)

        return {
            'region_x': self.region_x,
            'region_z': self.region_z,
            'blocks': all_blocks,
            'block_categories': categories,
            'containers': all_containers,
            'components': all_components
        }

    def _print_summary(
        self,
        all_blocks: Dict[str, int],
        all_containers: List[Dict],
        all_components: List[Dict]
    ) -> None:
        """Print summary information."""
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

        categories: Dict[str, List[str]] = {}
        for block_type in all_blocks:
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
            for container in all_containers[:50]:
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
            comp_by_type: Dict[str, List[Dict]] = {}
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

    def parse_detailed(self, max_chunks: int = 5, verbose: bool = True) -> None:
        """
        Parse with detailed BSON structure output for debugging.
        
        Args:
            max_chunks: Maximum number of chunks to analyze in detail
            verbose: Whether to print output
        """
        if not self.parse_filename():
            if verbose:
                print("Error: Invalid filename format")
            return

        with open(self.filepath, 'rb') as f:
            if not self.storage.read_header(f, verbose=verbose):
                return

            self.storage.read_blob_indexes(f)

            # Find all chunks with data
            chunks_with_data = [
                i for i, idx in enumerate(self.storage.blob_indexes) if idx != 0
            ]

            if verbose:
                print(f"\nAnalyzing first {max_chunks} chunks in detail...")
                print("-" * 80)

            for blob_index in chunks_with_data[:max_chunks]:
                chunk_x, chunk_z = self.storage.get_chunk_coordinates(
                    blob_index, self.region_x, self.region_z
                )
                chunk_data = self.storage.read_blob(f, blob_index)

                if chunk_data and verbose:
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

    def _print_bson_structure(self, obj: Any, indent: int = 0) -> None:
        """Print BSON structure recursively."""
        prefix = " " * indent

        if isinstance(obj, dict):
            for key, value in list(obj.items())[:20]:
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

    def _analyze_chunk_data(self, data: bytes, chunk_x: int, chunk_z: int) -> None:
        """Attempt to analyze chunk data structure."""
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

        print()
