"""
BSON Parser for Hytale's Codec Format

This module provides a parser for BSON documents used by Hytale's codec system.
"""

import struct
from enum import IntEnum
from typing import Any, Dict, List, Tuple


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
        """Read a BSON element value based on type"""
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
