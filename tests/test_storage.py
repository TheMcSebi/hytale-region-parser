"""Tests for the IndexedStorageFile parser."""

import struct

import pytest
import zstandard as zstd

from hytale_region_parser.storage import IndexedStorageFile


def create_valid_header(version: int = 0, blob_count: int = 1024, segment_size: int = 4096) -> bytes:
    """Create a valid IndexedStorageFile header."""
    header = bytearray()
    header.extend(b"HytaleIndexedStorage")  # 20 bytes magic
    header.extend(struct.pack('>I', version))  # 4 bytes version
    header.extend(struct.pack('>I', blob_count))  # 4 bytes blob count
    header.extend(struct.pack('>I', segment_size))  # 4 bytes segment size
    return bytes(header)


def create_blob_indexes(count: int, indexes: list[int] | None = None) -> bytes:
    """Create blob index table. indexes[i] is the segment index for blob i."""
    if indexes is None:
        indexes = [0] * count  # All empty by default
    data = bytearray()
    for idx in indexes:
        data.extend(struct.pack('>I', idx))
    return bytes(data)


def create_blob_segment(data: bytes, segment_size: int = 4096) -> bytes:
    """Create a blob segment with header and zstd-compressed data."""
    # Compress data
    cctx = zstd.ZstdCompressor()
    compressed = cctx.compress(data)

    # Create blob header
    segment = bytearray()
    segment.extend(struct.pack('>I', len(data)))  # src_length
    segment.extend(struct.pack('>I', len(compressed)))  # compressed_length
    segment.extend(compressed)

    # Pad to segment size
    if len(segment) < segment_size:
        segment.extend(b'\x00' * (segment_size - len(segment)))

    return bytes(segment)


class TestIndexedStorageFileInit:
    """Tests for IndexedStorageFile initialization."""

    def test_init(self, tmp_path):
        """Test basic initialization."""
        filepath = tmp_path / "test.region.bin"
        filepath.write_bytes(b"")

        storage = IndexedStorageFile(filepath)

        assert storage.filepath == filepath
        assert storage.version is None
        assert storage.blob_count is None
        assert storage.segment_size is None
        assert storage.blob_indexes == []


class TestReadHeader:
    """Tests for header reading and validation."""

    def test_read_valid_header(self, tmp_path):
        """Test reading a valid header."""
        filepath = tmp_path / "test.region.bin"
        header = create_valid_header(version=0, blob_count=1024, segment_size=4096)
        filepath.write_bytes(header)

        storage = IndexedStorageFile(filepath)
        with open(filepath, 'rb') as f:
            result = storage.read_header(f, verbose=False)

        assert result is True
        assert storage.version == 0
        assert storage.blob_count == 1024
        assert storage.segment_size == 4096

    def test_read_header_version_1(self, tmp_path):
        """Test reading header with version 1."""
        filepath = tmp_path / "test.region.bin"
        header = create_valid_header(version=1, blob_count=512, segment_size=8192)
        filepath.write_bytes(header)

        storage = IndexedStorageFile(filepath)
        with open(filepath, 'rb') as f:
            result = storage.read_header(f, verbose=False)

        assert result is True
        assert storage.version == 1
        assert storage.blob_count == 512
        assert storage.segment_size == 8192

    def test_read_header_file_too_small(self, tmp_path):
        """Test reading header from a file that's too small."""
        filepath = tmp_path / "test.region.bin"
        filepath.write_bytes(b"short")

        storage = IndexedStorageFile(filepath)
        with open(filepath, 'rb') as f:
            result = storage.read_header(f, verbose=False)

        assert result is False

    def test_read_header_invalid_magic(self, tmp_path):
        """Test reading header with invalid magic string."""
        filepath = tmp_path / "test.region.bin"
        bad_header = b"InvalidMagicString!!" + b'\x00' * 12
        filepath.write_bytes(bad_header)

        storage = IndexedStorageFile(filepath)
        with open(filepath, 'rb') as f:
            result = storage.read_header(f, verbose=False)

        assert result is False

    def test_read_header_unsupported_version(self, tmp_path):
        """Test reading header with unsupported version."""
        filepath = tmp_path / "test.region.bin"
        header = create_valid_header(version=99)
        filepath.write_bytes(header)

        storage = IndexedStorageFile(filepath)
        with open(filepath, 'rb') as f:
            result = storage.read_header(f, verbose=False)

        assert result is False

    def test_read_header_verbose_output(self, tmp_path, capsys):
        """Test that verbose mode prints header info."""
        filepath = tmp_path / "test.region.bin"
        header = create_valid_header(version=0, blob_count=1024, segment_size=4096)
        filepath.write_bytes(header)

        storage = IndexedStorageFile(filepath)
        with open(filepath, 'rb') as f:
            storage.read_header(f, verbose=True)

        captured = capsys.readouterr()
        assert "Version: 0" in captured.out
        assert "Blob count: 1024" in captured.out
        assert "Segment size: 4096" in captured.out


class TestReadBlobIndexes:
    """Tests for reading blob index table."""

    def test_read_blob_indexes(self, tmp_path):
        """Test reading blob indexes."""
        filepath = tmp_path / "test.region.bin"
        header = create_valid_header(blob_count=4)
        indexes = create_blob_indexes(4, [0, 1, 0, 2])
        filepath.write_bytes(header + indexes)

        storage = IndexedStorageFile(filepath)
        with open(filepath, 'rb') as f:
            storage.read_header(f, verbose=False)
            storage.read_blob_indexes(f)

        assert storage.blob_indexes == [0, 1, 0, 2]

    def test_read_blob_indexes_all_empty(self, tmp_path):
        """Test reading blob indexes where all are empty (0)."""
        filepath = tmp_path / "test.region.bin"
        header = create_valid_header(blob_count=3)
        indexes = create_blob_indexes(3, [0, 0, 0])
        filepath.write_bytes(header + indexes)

        storage = IndexedStorageFile(filepath)
        with open(filepath, 'rb') as f:
            storage.read_header(f, verbose=False)
            storage.read_blob_indexes(f)

        assert storage.blob_indexes == [0, 0, 0]


class TestSegmentCalculations:
    """Tests for segment position calculations."""

    def test_segments_base(self, tmp_path):
        """Test calculation of segments base position."""
        filepath = tmp_path / "test.region.bin"
        header = create_valid_header(blob_count=1024)
        filepath.write_bytes(header)

        storage = IndexedStorageFile(filepath)
        with open(filepath, 'rb') as f:
            storage.read_header(f, verbose=False)

        # Header (32) + blob indexes (1024 * 4 = 4096) = 4128
        assert storage.segments_base() == 32 + 1024 * 4

    def test_segment_position(self, tmp_path):
        """Test calculation of segment position."""
        filepath = tmp_path / "test.region.bin"
        header = create_valid_header(blob_count=4, segment_size=4096)
        filepath.write_bytes(header)

        storage = IndexedStorageFile(filepath)
        with open(filepath, 'rb') as f:
            storage.read_header(f, verbose=False)

        base = storage.segments_base()
        # Segment 1 is at base + 0
        assert storage.segment_position(1) == base
        # Segment 2 is at base + 4096
        assert storage.segment_position(2) == base + 4096
        # Segment 3 is at base + 8192
        assert storage.segment_position(3) == base + 8192

    def test_segment_position_invalid_zero(self, tmp_path):
        """Test that segment index 0 raises ValueError."""
        filepath = tmp_path / "test.region.bin"
        header = create_valid_header(blob_count=4)
        filepath.write_bytes(header)

        storage = IndexedStorageFile(filepath)
        with open(filepath, 'rb') as f:
            storage.read_header(f, verbose=False)

        with pytest.raises(ValueError, match="Invalid segment index 0"):
            storage.segment_position(0)


class TestReadBlob:
    """Tests for reading and decompressing blobs."""

    def test_read_blob_success(self, tmp_path):
        """Test successfully reading and decompressing a blob."""
        filepath = tmp_path / "test.region.bin"

        # Create file with one blob
        header = create_valid_header(blob_count=2, segment_size=4096)
        indexes = create_blob_indexes(2, [0, 1])  # Blob 0 empty, blob 1 at segment 1

        test_data = b"Hello, Hytale World!"
        segment = create_blob_segment(test_data, segment_size=4096)

        filepath.write_bytes(header + indexes + segment)

        storage = IndexedStorageFile(filepath)
        with open(filepath, 'rb') as f:
            storage.read_header(f, verbose=False)
            storage.read_blob_indexes(f)
            result = storage.read_blob(f, 1)

        assert result == test_data

    def test_read_blob_empty(self, tmp_path):
        """Test reading a blob with no data (segment index 0)."""
        filepath = tmp_path / "test.region.bin"
        header = create_valid_header(blob_count=2)
        indexes = create_blob_indexes(2, [0, 0])
        filepath.write_bytes(header + indexes)

        storage = IndexedStorageFile(filepath)
        with open(filepath, 'rb') as f:
            storage.read_header(f, verbose=False)
            storage.read_blob_indexes(f)
            result = storage.read_blob(f, 0)

        assert result is None

    def test_read_blob_out_of_range(self, tmp_path):
        """Test reading blob with out of range index."""
        filepath = tmp_path / "test.region.bin"
        header = create_valid_header(blob_count=2)
        indexes = create_blob_indexes(2)
        filepath.write_bytes(header + indexes)

        storage = IndexedStorageFile(filepath)
        with open(filepath, 'rb') as f:
            storage.read_header(f, verbose=False)
            storage.read_blob_indexes(f)

            with pytest.raises(IndexError, match="out of range"):
                storage.read_blob(f, 5)

            with pytest.raises(IndexError, match="out of range"):
                storage.read_blob(f, -1)

    def test_read_blob_large_data(self, tmp_path):
        """Test reading a larger blob with real data."""
        filepath = tmp_path / "test.region.bin"

        # Create larger test data
        test_data = b"Block data: " + bytes(range(256)) * 100

        header = create_valid_header(blob_count=1, segment_size=32768)
        indexes = create_blob_indexes(1, [1])
        segment = create_blob_segment(test_data, segment_size=32768)

        filepath.write_bytes(header + indexes + segment)

        storage = IndexedStorageFile(filepath)
        with open(filepath, 'rb') as f:
            storage.read_header(f, verbose=False)
            storage.read_blob_indexes(f)
            result = storage.read_blob(f, 0)

        assert result == test_data


class TestGetChunkCoordinates:
    """Tests for chunk coordinate calculation."""

    def test_chunk_coordinates_origin(self, tmp_path):
        """Test chunk coordinates for region at origin."""
        filepath = tmp_path / "test.region.bin"
        filepath.write_bytes(b"")
        storage = IndexedStorageFile(filepath)

        # Region 0,0, blob 0 = chunk 0,0
        assert storage.get_chunk_coordinates(0, 0, 0) == (0, 0)

        # Region 0,0, blob 1 = chunk 1,0
        assert storage.get_chunk_coordinates(1, 0, 0) == (1, 0)

        # Region 0,0, blob 32 = chunk 0,1 (second row)
        assert storage.get_chunk_coordinates(32, 0, 0) == (0, 1)

        # Region 0,0, blob 33 = chunk 1,1
        assert storage.get_chunk_coordinates(33, 0, 0) == (1, 1)

    def test_chunk_coordinates_positive_region(self, tmp_path):
        """Test chunk coordinates for positive region coordinates."""
        filepath = tmp_path / "test.region.bin"
        filepath.write_bytes(b"")
        storage = IndexedStorageFile(filepath)

        # Region 1,0 -> chunks start at x=32
        assert storage.get_chunk_coordinates(0, 1, 0) == (32, 0)
        assert storage.get_chunk_coordinates(5, 1, 0) == (37, 0)

        # Region 0,1 -> chunks start at z=32
        assert storage.get_chunk_coordinates(0, 0, 1) == (0, 32)

        # Region 2,3 -> chunks start at x=64, z=96
        assert storage.get_chunk_coordinates(0, 2, 3) == (64, 96)
        assert storage.get_chunk_coordinates(31, 2, 3) == (95, 96)
        assert storage.get_chunk_coordinates(32, 2, 3) == (64, 97)

    def test_chunk_coordinates_negative_region(self, tmp_path):
        """Test chunk coordinates for negative region coordinates."""
        filepath = tmp_path / "test.region.bin"
        filepath.write_bytes(b"")
        storage = IndexedStorageFile(filepath)

        # Region -1,0 -> chunks in negative x range
        chunk_x, chunk_z = storage.get_chunk_coordinates(0, -1, 0)
        # -1 << 5 = -32, so chunk_x = -32 | 0 = -32
        assert chunk_x == -32
        assert chunk_z == 0

        # Region -1,-1 -> chunks in negative x and z
        chunk_x, chunk_z = storage.get_chunk_coordinates(0, -1, -1)
        assert chunk_x == -32
        assert chunk_z == -32

    def test_chunk_coordinates_last_blob(self, tmp_path):
        """Test chunk coordinates for the last blob in a region (1023)."""
        filepath = tmp_path / "test.region.bin"
        filepath.write_bytes(b"")
        storage = IndexedStorageFile(filepath)

        # Blob 1023 = (31, 31) within region
        chunk_x, chunk_z = storage.get_chunk_coordinates(1023, 0, 0)
        assert chunk_x == 31
        assert chunk_z == 31

        # In region 1,1
        chunk_x, chunk_z = storage.get_chunk_coordinates(1023, 1, 1)
        assert chunk_x == 63  # 32 + 31
        assert chunk_z == 63  # 32 + 31


class TestAssertionErrors:
    """Tests for assertion errors when methods called out of order."""

    def test_read_blob_indexes_without_header(self, tmp_path):
        """Test that read_blob_indexes fails without reading header first."""
        filepath = tmp_path / "test.region.bin"
        filepath.write_bytes(b"")
        storage = IndexedStorageFile(filepath)

        with open(filepath, 'rb') as f, pytest.raises(AssertionError, match="read_header must be called first"):
            storage.read_blob_indexes(f)

    def test_segments_base_without_header(self, tmp_path):
        """Test that segments_base fails without reading header first."""
        filepath = tmp_path / "test.region.bin"
        filepath.write_bytes(b"")
        storage = IndexedStorageFile(filepath)

        with pytest.raises(AssertionError, match="read_header must be called first"):
            storage.segments_base()

    def test_segment_position_without_header(self, tmp_path):
        """Test that segment_position fails without reading header first."""
        filepath = tmp_path / "test.region.bin"
        filepath.write_bytes(b"")
        storage = IndexedStorageFile(filepath)

        with pytest.raises(AssertionError, match="read_header must be called first"):
            storage.segment_position(1)

    def test_read_blob_without_header(self, tmp_path):
        """Test that read_blob fails without reading header first."""
        filepath = tmp_path / "test.region.bin"
        filepath.write_bytes(b"")
        storage = IndexedStorageFile(filepath)

        with open(filepath, 'rb') as f, pytest.raises(AssertionError, match="read_header must be called first"):
            storage.read_blob(f, 0)
