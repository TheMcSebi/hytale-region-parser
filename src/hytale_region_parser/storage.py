"""
IndexedStorageFile Parser

Parser for IndexedStorageFile format used by Hytale for storing region data.
"""

import io
import struct
from pathlib import Path
from typing import List, Optional, Tuple

import zstandard as zstd


class IndexedStorageFile:
    """Parser for IndexedStorageFile format used by Hytale"""

    MAGIC_STRING = b"HytaleIndexedStorage"
    MAGIC_LENGTH = 20
    VERSION_OFFSET = 20
    BLOB_COUNT_OFFSET = 24
    SEGMENT_SIZE_OFFSET = 28
    HEADER_LENGTH = 32

    BLOB_HEADER_LENGTH = 8
    SRC_LENGTH_OFFSET = 0
    COMPRESSED_LENGTH_OFFSET = 4

    def __init__(self, filepath: Path):
        """
        Initialize the storage file parser.

        Args:
            filepath: Path to the .region.bin file
        """
        self.filepath = filepath
        self.version: Optional[int] = None
        self.blob_count: Optional[int] = None
        self.segment_size: Optional[int] = None
        self.blob_indexes: List[int] = []

    def read_header(self, f: io.BufferedReader, verbose: bool = True) -> bool:
        """
        Read and validate the file header.

        Args:
            f: Open file handle
            verbose: Whether to print header information

        Returns:
            True if header is valid, False otherwise
        """
        f.seek(0)
        header = f.read(self.HEADER_LENGTH)

        if len(header) < self.HEADER_LENGTH:
            if verbose:
                print(f"Error: File too small, expected at least {self.HEADER_LENGTH} bytes")
            return False

        # Check magic
        magic = header[:self.MAGIC_LENGTH]
        if magic != self.MAGIC_STRING:
            if verbose:
                print(f"Error: Invalid magic string. Expected {self.MAGIC_STRING!r}, got {magic!r}")
            return False

        # Read version
        self.version = struct.unpack('>I', header[self.VERSION_OFFSET:self.VERSION_OFFSET+4])[0]
        if self.version < 0 or self.version > 1:
            if verbose:
                print(f"Error: Unsupported version {self.version}")
            return False

        # Read blob count and segment size
        self.blob_count = struct.unpack('>I', header[self.BLOB_COUNT_OFFSET:self.BLOB_COUNT_OFFSET+4])[0]
        self.segment_size = struct.unpack('>I', header[self.SEGMENT_SIZE_OFFSET:self.SEGMENT_SIZE_OFFSET+4])[0]

        if verbose:
            print(f"File: {self.filepath.name}")
            print(f"  Version: {self.version}")
            print(f"  Blob count: {self.blob_count}")
            print(f"  Segment size: {self.segment_size}")

        return True

    def read_blob_indexes(self, f: io.BufferedReader) -> None:
        """
        Read the blob index table.

        Args:
            f: Open file handle
        """
        assert self.blob_count is not None, "read_header must be called first"
        f.seek(self.HEADER_LENGTH)
        index_data = f.read(self.blob_count * 4)

        self.blob_indexes = []
        for i in range(self.blob_count):
            offset = i * 4
            segment_index: int = struct.unpack('>I', index_data[offset:offset+4])[0]
            self.blob_indexes.append(segment_index)

    def segments_base(self) -> int:
        """Get the file position where segments start"""
        assert self.blob_count is not None, "read_header must be called first"
        return self.HEADER_LENGTH + self.blob_count * 4

    def segment_position(self, segment_index: int) -> int:
        """
        Convert segment index to file position.

        Args:
            segment_index: The segment index (1-based)

        Returns:
            File position of the segment

        Raises:
            ValueError: If segment_index is 0
        """
        assert self.segment_size is not None, "read_header must be called first"
        if segment_index == 0:
            raise ValueError("Invalid segment index 0")
        segment_offset = (segment_index - 1) * self.segment_size
        return segment_offset + self.segments_base()

    def read_blob(self, f: io.BufferedReader, blob_index: int) -> Optional[bytes]:
        """
        Read and decompress a blob.

        Args:
            f: Open file handle
            blob_index: Index of the blob to read

        Returns:
            Decompressed blob data, or None if no data or error

        Raises:
            IndexError: If blob_index is out of range
        """
        assert self.blob_count is not None, "read_header must be called first"
        if blob_index < 0 or blob_index >= self.blob_count:
            raise IndexError(f"Blob index {blob_index} out of range")

        first_segment_index = self.blob_indexes[blob_index]
        if first_segment_index == 0:
            return None  # No data for this blob

        # Read blob header
        pos = self.segment_position(first_segment_index)
        f.seek(pos)
        blob_header = f.read(self.BLOB_HEADER_LENGTH)

        src_length = struct.unpack('>I', blob_header[self.SRC_LENGTH_OFFSET:self.SRC_LENGTH_OFFSET+4])[0]
        compressed_length = struct.unpack('>I', blob_header[self.COMPRESSED_LENGTH_OFFSET:self.COMPRESSED_LENGTH_OFFSET+4])[0]

        # Read compressed data
        compressed_data = f.read(compressed_length)

        if len(compressed_data) != compressed_length:
            return None

        # Decompress
        try:
            dctx = zstd.ZstdDecompressor()
            decompressed = dctx.decompress(compressed_data, max_output_size=src_length)
            return decompressed
        except Exception:
            return None

    def get_chunk_coordinates(self, blob_index: int, region_x: int, region_z: int) -> Tuple[int, int]:
        """
        Convert blob index to chunk coordinates.

        Args:
            blob_index: Index of the blob within the region
            region_x: X coordinate of the region
            region_z: Z coordinate of the region

        Returns:
            Tuple of (chunk_x, chunk_z)
        """
        # Each region is 32x32 chunks (1024 total)
        local_x = blob_index % 32
        local_z = blob_index // 32

        chunk_x = (region_x << 5) | local_x
        chunk_z = (region_z << 5) | local_z

        return chunk_x, chunk_z
