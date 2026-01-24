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

    def test_parse_empty(self):
        """Test parsing empty/invalid data."""
        data = bytes([0, 0, 0, 0])
        parser = ChunkDataParser(data)
        result = parser.parse()
        # Should return a ParsedChunkData with default values
        assert result.version == 0
        assert result.block_names == set()
