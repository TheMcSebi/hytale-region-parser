"""Tests for data models."""

import pytest
from hytale_region_parser.models import (
    BlockComponent,
    BlockPaletteEntry,
    ChunkSectionData,
    ItemContainerData,
    ParsedChunkData,
)


class TestBlockComponent:
    """Tests for BlockComponent dataclass."""

    def test_creation(self):
        """Test creating a BlockComponent."""
        comp = BlockComponent(
            index=100,
            position=(5, 10, 15),
            component_type="container"
        )
        assert comp.index == 100
        assert comp.position == (5, 10, 15)
        assert comp.component_type == "container"
        assert comp.data == {}

    def test_with_data(self):
        """Test creating BlockComponent with data."""
        comp = BlockComponent(
            index=50,
            position=(1, 2, 3),
            component_type="sign",
            data={"text": "Hello", "color": "blue"}
        )
        assert comp.data == {"text": "Hello", "color": "blue"}


class TestItemContainerData:
    """Tests for ItemContainerData dataclass."""

    def test_default_values(self):
        """Test default values for ItemContainerData."""
        container = ItemContainerData(position=(0, 64, 0))
        assert container.position == (0, 64, 0)
        assert container.capacity == 0
        assert container.items == []
        assert container.allow_viewing is True
        assert container.custom_name is None
        assert container.who_placed_uuid is None
        assert container.placed_by_interaction is False

    def test_full_container(self):
        """Test fully populated ItemContainerData."""
        container = ItemContainerData(
            position=(100, 65, 200),
            capacity=27,
            items=[{"slot": 0, "item": "diamond"}],
            allow_viewing=False,
            custom_name="My Chest",
            who_placed_uuid="abc-123",
            placed_by_interaction=True
        )
        assert container.capacity == 27
        assert len(container.items) == 1
        assert container.custom_name == "My Chest"


class TestChunkSectionData:
    """Tests for ChunkSectionData dataclass."""

    def test_creation(self):
        """Test creating ChunkSectionData."""
        section = ChunkSectionData(section_y=5)
        assert section.section_y == 5
        assert section.block_palette == []
        assert section.block_counts == {}
        assert section.block_indices is None
        assert section.palette_type == 0

    def test_with_palette(self):
        """Test ChunkSectionData with block palette."""
        palette = [
            BlockPaletteEntry(internal_id=0, name="Empty", count=1000),
            BlockPaletteEntry(internal_id=1, name="Rock_Stone", count=500),
            BlockPaletteEntry(internal_id=2, name="Soil_Dirt", count=200),
            BlockPaletteEntry(internal_id=3, name="Plant_Grass", count=100),
        ]
        section = ChunkSectionData(
            section_y=3,
            block_palette=palette,
            block_counts={"Rock_Stone": 500, "Soil_Dirt": 200, "Plant_Grass": 100}
        )
        assert len(section.block_palette) == 4
        assert section.block_palette[1].name == "Rock_Stone"
        assert section.block_counts["Rock_Stone"] == 500


class TestParsedChunkData:
    """Tests for ParsedChunkData dataclass."""

    def test_default_values(self):
        """Test default values for ParsedChunkData."""
        chunk = ParsedChunkData()
        assert chunk.chunk_x == 0
        assert chunk.chunk_z == 0
        assert chunk.version == 0
        assert chunk.sections == []
        assert chunk.block_components == []
        assert chunk.containers == []
        assert chunk.entities == []
        assert chunk.block_names == set()
        assert chunk.heightmap is None
        assert chunk.raw_components == {}

    def test_with_data(self):
        """Test ParsedChunkData with populated fields."""
        chunk = ParsedChunkData(
            chunk_x=10,
            chunk_z=20,
            version=1,
            block_names={"Rock_Stone", "Soil_Dirt"}
        )
        assert chunk.chunk_x == 10
        assert chunk.chunk_z == 20
        assert len(chunk.block_names) == 2

    def test_add_components(self):
        """Test adding components to ParsedChunkData."""
        chunk = ParsedChunkData()
        chunk.block_components.append(
            BlockComponent(index=1, position=(0, 0, 0), component_type="test")
        )
        chunk.containers.append(
            ItemContainerData(position=(5, 5, 5), capacity=27)
        )
        
        assert len(chunk.block_components) == 1
        assert len(chunk.containers) == 1

    def test_to_dict_empty(self):
        """Test to_dict with empty chunk."""
        chunk = ParsedChunkData()
        result = chunk.to_dict()
        assert result == {}

    def test_to_dict_with_container(self):
        """Test to_dict with container data."""
        chunk = ParsedChunkData()
        chunk.containers.append(
            ItemContainerData(
                position=(10, 64, 20),
                capacity=18,
                items=[{"Id": "Diamond", "Quantity": 5}],
                custom_name="My Chest"
            )
        )
        
        result = chunk.to_dict()
        assert "10,64,20" in result
        assert result["10,64,20"]["type"] == "container"
        assert result["10,64,20"]["capacity"] == 18
        assert result["10,64,20"]["custom_name"] == "My Chest"

    def test_to_dict_with_block_component(self):
        """Test to_dict with block component data."""
        chunk = ParsedChunkData()
        chunk.block_components.append(
            BlockComponent(
                index=100,
                position=(5, 32, 10),
                component_type="FarmingBlock",
                data={"SpreadRate": 0.5}
            )
        )
        
        result = chunk.to_dict()
        assert "5,32,10" in result
        assert result["5,32,10"]["type"] == "block_component"
        assert "FarmingBlock" in result["5,32,10"]["components"]
        assert result["5,32,10"]["components"]["FarmingBlock"]["SpreadRate"] == 0.5

    def test_to_dict_merge_components(self):
        """Test that multiple components at same position are merged."""
        chunk = ParsedChunkData()
        chunk.block_components.append(
            BlockComponent(
                index=100,
                position=(5, 32, 10),
                component_type="TypeA",
                data={"value": 1}
            )
        )
        chunk.block_components.append(
            BlockComponent(
                index=100,
                position=(5, 32, 10),
                component_type="TypeB",
                data={"value": 2}
            )
        )
        
        result = chunk.to_dict()
        assert "5,32,10" in result
        assert "TypeA" in result["5,32,10"]["components"]
        assert "TypeB" in result["5,32,10"]["components"]
