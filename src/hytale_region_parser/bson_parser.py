"""
BSON Parser for Hytale's Codec Format

This module provides a parser for BSON documents used by Hytale's codec system.
Uses the bson library for parsing.
"""

import struct
from enum import IntEnum
from typing import Any, Dict, List, Tuple

import bson


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


def _convert_bson_types(obj: Any) -> Any:
    """
    Convert bson library types to standard Python types for JSON serialization.
    
    The bson library may return special types like ObjectId, datetime, etc.
    This function converts them to JSON-serializable types.
    """
    if obj is None:
        return None
    elif isinstance(obj, dict):
        return {k: _convert_bson_types(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_bson_types(item) for item in obj]
    elif isinstance(obj, bytes):
        # Return as hex string for JSON compatibility
        return obj.hex()
    elif isinstance(obj, bson.ObjectId):
        return str(obj)
    elif hasattr(obj, 'isoformat'):  # datetime
        return obj.isoformat()
    else:
        return obj


class BsonParser:
    """
    Parser for BSON documents used by Hytale's codec system.
    
    This class wraps the bson library and provides additional utility methods
    for reading raw bytes when needed.
    """

    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def remaining(self) -> int:
        """Return number of bytes remaining in the buffer"""
        return len(self.data) - self.pos

    def read_byte(self) -> int:
        """Read a single byte"""
        if self.pos >= len(self.data):
            raise ValueError("Unexpected end of data")
        value = self.data[self.pos]
        self.pos += 1
        return value

    def read_bytes(self, n: int) -> bytes:
        """Read n bytes from the buffer"""
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
        """Read BSON binary data, returns (subtype, data)"""
        length = self.read_int32()
        subtype = self.read_byte()
        data = self.read_bytes(length)
        return subtype, data

    def read_document(self) -> Dict[str, Any]:
        """Read a BSON document using the bson library"""
        # Get document size from current position
        if self.remaining() < 4:
            raise ValueError("Not enough data for BSON document")

        doc_size = struct.unpack('<i', self.data[self.pos:self.pos + 4])[0]

        if self.remaining() < doc_size:
            raise ValueError(f"Document size {doc_size} exceeds remaining data {self.remaining()}")

        # Extract the document bytes
        doc_bytes = self.data[self.pos:self.pos + doc_size]
        self.pos += doc_size

        # Parse using bson library
        result = bson.loads(doc_bytes)

        # Convert any special types to JSON-serializable types
        return _convert_bson_types(result)

    def read_array(self) -> List[Any]:
        """Read a BSON array"""
        doc = self.read_document()
        # BSON arrays are documents with string indices "0", "1", "2", ...
        if isinstance(doc, dict):
            return [doc[str(i)] for i in range(len(doc))]
        return doc

    def parse(self) -> Dict[str, Any]:
        """Parse the entire BSON document"""
        return self.read_document()
