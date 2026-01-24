"""Tests for the chunk parser."""

import struct
from datetime import datetime

import bson

from hytale_region_parser.chunk_parser import ChunkDataParser, _convert_bson_types


def create_block_section_hex(
    migration_version: int = 6,
    palette_type: int = 2,
    entries: list[tuple[int, str, int]] | None = None,
    block_indices: bytes = b""
) -> str:
    """
    Create a hex-encoded block section data string.

    Args:
        migration_version: Block migration version (4 bytes BE)
        palette_type: 0=Empty, 1=HalfByte, 2=Byte, 3=Short
        entries: List of (internal_id, name, count) tuples
        block_indices: Raw block index bytes to append

    Returns:
        Hex-encoded string
    """
    data = bytearray()

    # 4 bytes: migration version (BE)
    data.extend(struct.pack('>I', migration_version))

    # 1 byte: palette type
    data.append(palette_type)

    if palette_type == 0 or entries is None:
        return data.hex()

    # 2 bytes: palette count (BE)
    data.extend(struct.pack('>H', len(entries)))

    # Palette entries
    for internal_id, name, count in entries:
        data.append(internal_id)  # 1 byte: internal ID
        name_bytes = name.encode('utf-8')
        data.extend(struct.pack('>H', len(name_bytes)))  # 2 bytes: string length
        data.extend(name_bytes)  # N bytes: name
        data.extend(struct.pack('>h', count))  # 2 bytes: count (signed)

    # Block indices
    data.extend(block_indices)

    return data.hex()


class TestConvertBsonTypes:
    """Tests for _convert_bson_types function."""

    def test_convert_none(self):
        """Test converting None."""
        assert _convert_bson_types(None) is None

    def test_convert_dict(self):
        """Test converting nested dict."""
        obj = {"key": {"nested": b"\x01\x02"}}
        result = _convert_bson_types(obj)
        assert result == {"key": {"nested": "0102"}}

    def test_convert_list(self):
        """Test converting list with bytes."""
        obj = [b"\xff", b"\x00"]
        result = _convert_bson_types(obj)
        assert result == ["ff", "00"]

    def test_convert_bytes(self):
        """Test converting bytes to hex string."""
        assert _convert_bson_types(b"\xde\xad\xbe\xef") == "deadbeef"

    def test_convert_object_id(self):
        """Test converting bson.ObjectId to string."""
        oid = bson.ObjectId()
        result = _convert_bson_types(oid)
        assert isinstance(result, str)
        assert len(result) == 24  # ObjectId hex is 24 chars

    def test_convert_datetime(self):
        """Test converting datetime to isoformat."""
        dt = datetime(2025, 1, 24, 12, 30, 45)
        result = _convert_bson_types(dt)
        assert result == "2025-01-24T12:30:45"

    def test_convert_primitive(self):
        """Test that primitives pass through unchanged."""
        assert _convert_bson_types(42) == 42
        assert _convert_bson_types(3.14) == 3.14
        assert _convert_bson_types("hello") == "hello"
        assert _convert_bson_types(True) is True


class TestChunkDataParserInit:
    """Tests for ChunkDataParser initialization."""

    def test_init(self):
        """Test basic initialization."""
        data = b"test data"
        parser = ChunkDataParser(data)
        assert parser.data == data


class TestTryParseBson:
    """Tests for try_parse_bson method."""

    def test_parse_valid_bson(self):
        """Test parsing valid BSON data."""
        doc = {"Version": 6, "Components": {}}
        bson_bytes = bson.dumps(doc)
        parser = ChunkDataParser(bson_bytes)
        result = parser.try_parse_bson()
        assert result is not None
        assert result["Version"] == 6

    def test_parse_invalid_bson(self, capsys):
        """Test parsing invalid BSON returns None."""
        parser = ChunkDataParser(b"not valid bson")
        result = parser.try_parse_bson()
        assert result is None
        captured = capsys.readouterr()
        assert "Warning" in captured.out

    def test_parse_empty_document(self):
        """Test parsing empty BSON document."""
        bson_bytes = bson.dumps({})
        parser = ChunkDataParser(bson_bytes)
        result = parser.try_parse_bson()
        assert result == {}


class TestParseBlockSectionData:
    """Tests for parse_block_section_data static method."""

    def test_parse_empty_hex(self):
        """Test parsing empty hex string."""
        section = ChunkDataParser.parse_block_section_data("", section_y=5)
        assert section.section_y == 5
        assert section.block_palette == []
        assert section.block_counts == {}

    def test_parse_invalid_hex(self):
        """Test parsing invalid hex string."""
        section = ChunkDataParser.parse_block_section_data("not_hex")
        assert section.block_palette == []

    def test_parse_too_short(self):
        """Test parsing data that's too short."""
        section = ChunkDataParser.parse_block_section_data("0102")  # Only 2 bytes
        assert section.block_palette == []

    def test_parse_empty_palette_type(self):
        """Test parsing section with empty palette type (0)."""
        hex_data = create_block_section_hex(palette_type=0)
        section = ChunkDataParser.parse_block_section_data(hex_data)
        assert section.palette_type == 0
        assert section.block_palette == []

    def test_parse_single_block(self):
        """Test parsing section with single block type."""
        hex_data = create_block_section_hex(
            palette_type=2,
            entries=[(0, "Stone", 100)]
        )
        section = ChunkDataParser.parse_block_section_data(hex_data, section_y=3)

        assert section.section_y == 3
        assert section.palette_type == 2
        assert len(section.block_palette) == 1
        assert section.block_palette[0].name == "Stone"
        assert section.block_palette[0].count == 100
        assert section.block_counts == {"Stone": 100}

    def test_parse_multiple_blocks(self):
        """Test parsing section with multiple block types."""
        hex_data = create_block_section_hex(
            palette_type=2,
            entries=[
                (0, "Empty", 500),
                (1, "Stone", 200),
                (2, "Dirt", 150),
                (3, "Ore_Iron", 50)
            ]
        )
        section = ChunkDataParser.parse_block_section_data(hex_data)

        assert len(section.block_palette) == 4
        # Empty should not be in block_counts
        assert "Empty" not in section.block_counts
        assert section.block_counts["Stone"] == 200
        assert section.block_counts["Dirt"] == 150
        assert section.block_counts["Ore_Iron"] == 50

    def test_parse_negative_count(self):
        """Test that negative counts are clamped to 0 in block_counts."""
        hex_data = create_block_section_hex(
            palette_type=2,
            entries=[(0, "TestBlock", -50)]
        )
        section = ChunkDataParser.parse_block_section_data(hex_data)

        # Palette should have the raw count
        assert section.block_palette[0].count == -50
        # But block_counts should clamp to 0
        assert section.block_counts.get("TestBlock", 0) == 0

    def test_parse_with_block_indices(self):
        """Test parsing section preserves remaining block indices."""
        block_indices = bytes([0, 1, 0, 1, 2, 2])
        hex_data = create_block_section_hex(
            palette_type=2,
            entries=[(0, "Air", 2), (1, "Stone", 2), (2, "Dirt", 2)],
            block_indices=block_indices
        )
        section = ChunkDataParser.parse_block_section_data(hex_data)

        assert section.block_indices == block_indices

    def test_parse_unicode_block_name(self):
        """Test parsing block with unicode characters in name."""
        hex_data = create_block_section_hex(
            palette_type=2,
            entries=[(0, "Blöck_Nàme_日本語", 10)]
        )
        section = ChunkDataParser.parse_block_section_data(hex_data)

        assert section.block_palette[0].name == "Blöck_Nàme_日本語"

    def test_parse_duplicate_block_names(self):
        """Test that duplicate block names are aggregated."""
        hex_data = create_block_section_hex(
            palette_type=2,
            entries=[
                (0, "Stone", 100),
                (1, "Stone", 50),  # Same name, different internal ID
            ]
        )
        section = ChunkDataParser.parse_block_section_data(hex_data)

        # Both entries in palette
        assert len(section.block_palette) == 2
        # But counts are aggregated
        assert section.block_counts["Stone"] == 150


class TestParse:
    """Tests for parse method."""

    def test_parse_empty_data(self):
        """Test parsing empty/invalid data."""
        parser = ChunkDataParser(bytes([0, 0, 0, 0]))
        result = parser.parse()
        assert result.version == 0
        assert result.block_names == set()
        assert result.sections == []
        assert result.containers == []

    def test_parse_with_version(self):
        """Test parsing extracts version."""
        doc = {"Version": 42, "Components": {}}
        parser = ChunkDataParser(bson.dumps(doc))
        result = parser.parse()
        assert result.version == 42

    def test_parse_entities(self):
        """Test parsing extracts entities."""
        doc = {
            "Version": 1,
            "Components": {
                "EntityChunk": {
                    "Entities": [
                        {"Type": "Mob", "Position": {"X": 10, "Y": 64, "Z": 20}},
                        {"Type": "Item", "Position": {"X": 5, "Y": 65, "Z": 15}}
                    ]
                }
            }
        }
        parser = ChunkDataParser(bson.dumps(doc))
        result = parser.parse()
        assert len(result.entities) == 2
        assert result.entities[0]["Type"] == "Mob"

    def test_parse_block_sections(self):
        """Test parsing extracts block sections from ChunkColumn."""
        section_hex = create_block_section_hex(
            palette_type=2,
            entries=[(0, "Stone", 100), (1, "Dirt", 50)]
        )
        doc = {
            "Version": 1,
            "Components": {
                "ChunkColumn": {
                    "Sections": [
                        {"Components": {"Block": {"Data": section_hex}}},
                        {"Components": {"Block": {"Data": section_hex}}}
                    ]
                }
            }
        }
        parser = ChunkDataParser(bson.dumps(doc))
        result = parser.parse()

        assert len(result.sections) == 2
        assert result.sections[0].section_y == 0
        assert result.sections[1].section_y == 1
        assert "Stone" in result.block_names
        assert "Dirt" in result.block_names

    def test_parse_container(self):
        """Test parsing extracts container data."""
        doc = {
            "Version": 1,
            "Components": {
                "BlockComponentChunk": {
                    "BlockComponents": {
                        "12345": {
                            "Components": {
                                "container": {
                                    "Position": {"X": 10, "Y": 64, "Z": 20},
                                    "ItemContainer": {
                                        "Capacity": 27,
                                        "Items": {"0": {"Name": "Sword"}}
                                    },
                                    "AllowViewing": True,
                                    "Custom_Name": "My Chest"
                                }
                            }
                        }
                    }
                }
            }
        }
        parser = ChunkDataParser(bson.dumps(doc))
        result = parser.parse()

        assert len(result.containers) == 1
        container = result.containers[0]
        assert container.position == (10, 64, 20)
        assert container.capacity == 27
        assert container.custom_name == "My Chest"
        assert len(container.items) == 1

    def test_parse_block_components(self):
        """Test parsing extracts block components."""
        doc = {
            "Version": 1,
            "Components": {
                "BlockComponentChunk": {
                    "BlockComponents": {
                        "1000": {
                            "Components": {
                                "sign": {"Text": "Hello World"},
                                "rotation": {"Angle": 90}
                            }
                        }
                    }
                }
            }
        }
        parser = ChunkDataParser(bson.dumps(doc))
        result = parser.parse()

        # Should have 2 block components (sign and rotation)
        assert len(result.block_components) == 2
        comp_types = {c.component_type for c in result.block_components}
        assert "sign" in comp_types
        assert "rotation" in comp_types

    def test_parse_raw_components_preserved(self):
        """Test that raw BSON document is preserved."""
        doc = {"Version": 1, "Components": {"Custom": "Data"}}
        parser = ChunkDataParser(bson.dumps(doc))
        result = parser.parse()

        assert result.raw_components == doc
