"""Tests for the region parser."""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from hytale_region_parser.region_parser import RegionFileParser
from hytale_region_parser.models import (
    BlockComponent,
    ItemContainerData,
    ParsedChunkData,
)


class TestRegionFileParserFilename:
    """Tests for filename parsing."""

    def test_parse_valid_filename(self, tmp_path):
        """Test parsing a valid region filename."""
        # Create a dummy file
        region_file = tmp_path / "0.0.region.bin"
        region_file.write_bytes(b"")
        
        parser = RegionFileParser(region_file)
        assert parser.parse_filename() is True
        assert parser.region_x == 0
        assert parser.region_z == 0

    def test_parse_negative_coordinates(self, tmp_path):
        """Test parsing negative region coordinates."""
        region_file = tmp_path / "-2.-3.region.bin"
        region_file.write_bytes(b"")
        
        parser = RegionFileParser(region_file)
        assert parser.parse_filename() is True
        assert parser.region_x == -2
        assert parser.region_z == -3

    def test_parse_invalid_filename(self, tmp_path):
        """Test parsing an invalid filename."""
        region_file = tmp_path / "invalid.bin"
        region_file.write_bytes(b"")
        
        parser = RegionFileParser(region_file)
        assert parser.parse_filename() is False

    def test_coordinates_property(self, tmp_path):
        """Test the coordinates property."""
        region_file = tmp_path / "5.10.region.bin"
        region_file.write_bytes(b"")
        
        parser = RegionFileParser(region_file)
        assert parser.coordinates is None  # Not parsed yet
        
        parser.parse_filename()
        assert parser.coordinates == (5, 10)


class TestRegionFileParserToDict:
    """Tests for to_dict and to_json methods."""

    def test_to_dict_empty(self, tmp_path):
        """Test to_dict with no chunks."""
        region_file = tmp_path / "0.0.region.bin"
        region_file.write_bytes(b"")
        
        parser = RegionFileParser(region_file)
        parser.region_x = 0
        parser.region_z = 0
        parser._file_handle = MagicMock()
        
        # Mock iter_chunks to return empty
        with patch.object(parser, 'iter_chunks', return_value=iter([])):
            result = parser.to_dict()
        
        assert "metadata" in result
        assert "blocks" in result
        assert result["blocks"] == {}
        assert result["metadata"]["chunk_count"] == 0

    def test_to_dict_with_container(self, tmp_path):
        """Test to_dict includes containers with world coordinates."""
        region_file = tmp_path / "0.0.region.bin"
        region_file.write_bytes(b"")
        
        parser = RegionFileParser(region_file)
        parser.region_x = 0
        parser.region_z = 0
        parser._file_handle = MagicMock()
        
        # Create a mock chunk with a container
        chunk = ParsedChunkData(chunk_x=1, chunk_z=2)
        chunk.containers.append(
            ItemContainerData(
                position=(5, 64, 10),  # Local position within chunk
                capacity=18,
                items=[{"Id": "Diamond", "Quantity": 1}]
            )
        )
        
        with patch.object(parser, 'iter_chunks', return_value=iter([chunk])):
            result = parser.to_dict()
        
        # World position: chunk_x * 32 + local_x = 1*32 + 5 = 37
        # World position: chunk_z * 32 + local_z = 2*32 + 10 = 74
        blocks = result["blocks"]
        assert "37,64,74" in blocks
        assert blocks["37,64,74"]["name"] == "Container"
        assert blocks["37,64,74"]["components"]["container"]["capacity"] == 18

    def test_to_dict_with_block_component(self, tmp_path):
        """Test to_dict includes block components with world coordinates."""
        region_file = tmp_path / "0.0.region.bin"
        region_file.write_bytes(b"")
        
        parser = RegionFileParser(region_file)
        parser.region_x = 0
        parser.region_z = 0
        parser._file_handle = MagicMock()
        
        # Create a mock chunk with a block component
        chunk = ParsedChunkData(chunk_x=0, chunk_z=0)
        chunk.block_components.append(
            BlockComponent(
                index=100,
                position=(10, 32, 15),
                component_type="FarmingBlock",
                data={"SpreadRate": 0.0}
            )
        )
        
        with patch.object(parser, 'iter_chunks', return_value=iter([chunk])):
            result = parser.to_dict()
        
        blocks = result["blocks"]
        assert "10,32,15" in blocks
        assert blocks["10,32,15"]["name"] == "FarmingBlock"
        assert "FarmingBlock" in blocks["10,32,15"]["components"]

    def test_to_json(self, tmp_path):
        """Test to_json produces valid JSON."""
        region_file = tmp_path / "0.0.region.bin"
        region_file.write_bytes(b"")
        
        parser = RegionFileParser(region_file)
        parser.region_x = 0
        parser.region_z = 0
        parser._file_handle = MagicMock()
        
        chunk = ParsedChunkData(chunk_x=0, chunk_z=0)
        chunk.containers.append(
            ItemContainerData(position=(1, 2, 3), capacity=10)
        )
        
        with patch.object(parser, 'iter_chunks', return_value=iter([chunk])):
            json_str = parser.to_json()
        
        # Should be valid JSON
        parsed = json.loads(json_str)
        assert "1,2,3" in parsed["blocks"]

    def test_to_json_compact(self, tmp_path):
        """Test to_json with compact output."""
        region_file = tmp_path / "0.0.region.bin"
        region_file.write_bytes(b"")
        
        parser = RegionFileParser(region_file)
        parser.region_x = 0
        parser.region_z = 0
        parser._file_handle = MagicMock()
        
        chunk = ParsedChunkData(chunk_x=0, chunk_z=0)
        chunk.containers.append(
            ItemContainerData(position=(1, 2, 3), capacity=10)
        )
        
        # Need separate patches for each call since iter() is consumed
        with patch.object(parser, 'iter_chunks', return_value=iter([chunk])):
            json_compact = parser.to_json(indent=None)
        
        chunk2 = ParsedChunkData(chunk_x=0, chunk_z=0)
        chunk2.containers.append(
            ItemContainerData(position=(1, 2, 3), capacity=10)
        )
        
        with patch.object(parser, 'iter_chunks', return_value=iter([chunk2])):
            json_pretty = parser.to_json(indent=2)
        
        # Compact should be shorter (no whitespace)
        assert len(json_compact) < len(json_pretty)

    def test_to_dict_multiple_chunks(self, tmp_path):
        """Test to_dict combines data from multiple chunks."""
        region_file = tmp_path / "0.0.region.bin"
        region_file.write_bytes(b"")
        
        parser = RegionFileParser(region_file)
        parser.region_x = 0
        parser.region_z = 0
        parser._file_handle = MagicMock()
        
        chunk1 = ParsedChunkData(chunk_x=0, chunk_z=0)
        chunk1.containers.append(
            ItemContainerData(position=(0, 10, 0), capacity=18)
        )
        
        chunk2 = ParsedChunkData(chunk_x=1, chunk_z=0)
        chunk2.containers.append(
            ItemContainerData(position=(0, 20, 0), capacity=27)
        )
        
        with patch.object(parser, 'iter_chunks', return_value=iter([chunk1, chunk2])):
            result = parser.to_dict()
        
        # Both containers should be in result
        blocks = result["blocks"]
        assert "0,10,0" in blocks  # From chunk (0, 0)
        assert "32,20,0" in blocks  # From chunk (1, 0): 1*32 + 0 = 32

    def test_to_dict_negative_region(self, tmp_path):
        """Test to_dict with negative region coordinates."""
        region_file = tmp_path / "-1.-1.region.bin"
        region_file.write_bytes(b"")
        
        parser = RegionFileParser(region_file)
        parser.region_x = -1
        parser.region_z = -1
        parser._file_handle = MagicMock()
        
        # Chunk at (-32, -32) world chunk coords
        chunk = ParsedChunkData(chunk_x=-32, chunk_z=-32)
        chunk.containers.append(
            ItemContainerData(position=(5, 64, 10), capacity=18)
        )
        
        with patch.object(parser, 'iter_chunks', return_value=iter([chunk])):
            result = parser.to_dict()
        
        # World coords: -32*32 + 5 = -1024 + 5 = -1019
        # World coords: -32*32 + 10 = -1024 + 10 = -1014
        blocks = result["blocks"]
        assert "-1019,64,-1014" in blocks
