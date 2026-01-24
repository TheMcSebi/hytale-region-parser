"""Tests for the BSON parser."""

import pytest
from hytale_region_parser.bson_parser import BsonParser


class TestBsonParser:
    """Tests for BsonParser class."""

    def test_read_int32(self):
        """Test reading little-endian 32-bit integer."""
        # 0x12345678 in little-endian
        data = bytes([0x78, 0x56, 0x34, 0x12])
        parser = BsonParser(data)
        assert parser.read_int32() == 0x12345678

    def test_read_int64(self):
        """Test reading little-endian 64-bit integer."""
        data = bytes([0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        parser = BsonParser(data)
        assert parser.read_int64() == 1

    def test_read_double(self):
        """Test reading 64-bit floating point."""
        import struct
        data = struct.pack('<d', 3.14159)
        parser = BsonParser(data)
        assert abs(parser.read_double() - 3.14159) < 0.00001

    def test_read_cstring(self):
        """Test reading null-terminated string."""
        data = b'hello\x00world'
        parser = BsonParser(data)
        assert parser.read_cstring() == 'hello'
        assert parser.pos == 6

    def test_read_cstring_unterminated(self):
        """Test that unterminated cstring raises error."""
        data = b'hello'  # No null terminator
        parser = BsonParser(data)
        with pytest.raises(ValueError, match="Unterminated cstring"):
            parser.read_cstring()

    def test_read_string(self):
        """Test reading length-prefixed BSON string."""
        # Length (6 including null), then "hello" + null
        data = bytes([0x06, 0x00, 0x00, 0x00]) + b'hello\x00'
        parser = BsonParser(data)
        assert parser.read_string() == 'hello'

    def test_read_byte(self):
        """Test reading single byte."""
        data = bytes([0x42])
        parser = BsonParser(data)
        assert parser.read_byte() == 0x42

    def test_read_bytes(self):
        """Test reading multiple bytes."""
        data = bytes([1, 2, 3, 4, 5])
        parser = BsonParser(data)
        assert parser.read_bytes(3) == bytes([1, 2, 3])
        assert parser.pos == 3

    def test_remaining(self):
        """Test remaining bytes calculation."""
        data = bytes([1, 2, 3, 4, 5])
        parser = BsonParser(data)
        assert parser.remaining() == 5
        parser.read_bytes(2)
        assert parser.remaining() == 3

    def test_read_beyond_end(self):
        """Test that reading beyond end raises error."""
        data = bytes([1, 2])
        parser = BsonParser(data)
        with pytest.raises(ValueError):
            parser.read_bytes(10)

    def test_simple_document(self):
        """Test parsing a simple BSON document."""
        # Minimal document with one int32 field
        # { "x": 1 }
        doc = bytearray()
        # Document size (will be filled in)
        doc.extend([0, 0, 0, 0])
        # Type: int32 (0x10)
        doc.append(0x10)
        # Field name "x" + null
        doc.extend(b'x\x00')
        # Value: 1 (little-endian)
        doc.extend([0x01, 0x00, 0x00, 0x00])
        # Document terminator
        doc.append(0x00)
        # Fill in document size
        doc[0:4] = len(doc).to_bytes(4, 'little')
        
        parser = BsonParser(bytes(doc))
        result = parser.parse()
        assert result == {'x': 1}

    def test_boolean_values(self):
        """Test parsing boolean values."""
        doc = bytearray()
        doc.extend([0, 0, 0, 0])  # Size placeholder
        doc.append(0x08)  # Type: boolean
        doc.extend(b'flag\x00')
        doc.append(0x01)  # True
        doc.append(0x00)  # Terminator
        doc[0:4] = len(doc).to_bytes(4, 'little')
        
        parser = BsonParser(bytes(doc))
        result = parser.parse()
        assert result == {'flag': True}

    def test_null_value(self):
        """Test parsing null value."""
        doc = bytearray()
        doc.extend([0, 0, 0, 0])
        doc.append(0x0A)  # Type: null
        doc.extend(b'empty\x00')
        doc.append(0x00)
        doc[0:4] = len(doc).to_bytes(4, 'little')
        
        parser = BsonParser(bytes(doc))
        result = parser.parse()
        assert result == {'empty': None}
