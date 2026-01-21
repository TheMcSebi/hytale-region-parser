"""Tests for the chunk parser."""

import pytest
from hytale_region_parser.chunk_parser import ChunkDataParser


class TestChunkDataParser:
    """Tests for ChunkDataParser class."""

    def test_read_int(self):
        """Test reading big-endian integer."""
        import struct
        data = struct.pack('>I', 0x12345678)
        parser = ChunkDataParser(data)
        assert parser.read_int() == 0x12345678

    def test_read_int_le(self):
        """Test reading little-endian integer."""
        import struct
        data = struct.pack('<i', 12345)
        parser = ChunkDataParser(data)
        assert parser.read_int_le() == 12345

    def test_read_byte(self):
        """Test reading single byte."""
        data = bytes([0xFF])
        parser = ChunkDataParser(data)
        assert parser.read_byte() == 255

    def test_read_bytes(self):
        """Test reading multiple bytes."""
        data = bytes([1, 2, 3, 4, 5])
        parser = ChunkDataParser(data)
        assert parser.read_bytes(3) == bytes([1, 2, 3])

    def test_read_short(self):
        """Test reading big-endian short."""
        import struct
        data = struct.pack('>H', 1000)
        parser = ChunkDataParser(data)
        assert parser.read_short() == 1000

    def test_remaining(self):
        """Test remaining bytes."""
        data = bytes([1, 2, 3, 4, 5])
        parser = ChunkDataParser(data)
        assert parser.remaining() == 5
        parser.skip_bytes(2)
        assert parser.remaining() == 3

    def test_extract_block_names_simple(self):
        """Test extracting block names from text."""
        data = b'some data Rock_Stone more data Soil_Dirt end'
        parser = ChunkDataParser(data)
        names = parser.extract_block_names_from_bytes()
        assert 'Rock_Stone' in names
        assert 'Soil_Dirt' in names

    def test_extract_block_names_complex(self):
        """Test extracting complex block names."""
        data = b'Plant_Grass_Tall Wood_Oak_Plank'
        parser = ChunkDataParser(data)
        names = parser.extract_block_names_from_bytes()
        assert 'Plant_Grass_Tall' in names
        assert 'Wood_Oak_Plank' in names

    def test_extract_block_names_invalid(self):
        """Test that invalid patterns are not extracted."""
        data = b'NotValid lowercase_start UPPERCASE_ONLY'
        parser = ChunkDataParser(data)
        names = parser.extract_block_names_from_bytes()
        assert len(names) == 0

    def test_parse_empty(self):
        """Test parsing empty/invalid data."""
        data = bytes([0, 0, 0, 0])
        parser = ChunkDataParser(data)
        result = parser.parse()
        # Should return a ParsedChunkData with default values
        assert result.version == 0
        assert result.block_names == set()

    def test_valid_prefixes(self):
        """Test that only valid prefixes are accepted."""
        valid_data = b'Rock_Stone Soil_Dirt Plant_Flower'
        parser = ChunkDataParser(valid_data)
        names = parser.extract_block_names_from_bytes()
        assert 'Rock_Stone' in names
        assert 'Soil_Dirt' in names
        assert 'Plant_Flower' in names

        # Invalid prefix should not be extracted
        invalid_data = b'Invalid_Block Unknown_Type'
        parser2 = ChunkDataParser(invalid_data)
        names2 = parser2.extract_block_names_from_bytes()
        assert 'Invalid_Block' not in names2
        assert 'Unknown_Type' not in names2
