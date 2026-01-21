"""Tests for the command-line interface."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from hytale_region_parser.cli import main
from hytale_region_parser.models import ItemContainerData, ParsedChunkData


class TestCLI:
    """Tests for CLI functionality."""

    def test_help_flag(self, capsys):
        """Test --help flag."""
        with pytest.raises(SystemExit) as exc_info:
            with patch('sys.argv', ['hytale-region-parser', '--help']):
                main()
        
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert 'region_file' in captured.out
        assert '--summary' in captured.out

    def test_version_flag(self, capsys):
        """Test --version flag."""
        with pytest.raises(SystemExit) as exc_info:
            with patch('sys.argv', ['hytale-region-parser', '--version']):
                main()
        
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert '0.1.0' in captured.out

    def test_file_not_found(self, capsys):
        """Test error when file doesn't exist."""
        with patch('sys.argv', ['hytale-region-parser', 'nonexistent.bin']):
            result = main()
        
        assert result == 1
        captured = capsys.readouterr()
        assert 'Error' in captured.err
        assert 'not found' in captured.err

    def test_json_output_default(self, tmp_path, capsys):
        """Test that JSON is output by default."""
        region_file = tmp_path / "0.0.region.bin"
        region_file.write_bytes(b"")
        
        # Mock the parser to return test data
        mock_chunk = ParsedChunkData(chunk_x=0, chunk_z=0)
        mock_chunk.containers.append(
            ItemContainerData(position=(1, 2, 3), capacity=18)
        )
        
        with patch('sys.argv', ['hytale-region-parser', str(region_file)]):
            with patch('hytale_region_parser.cli.RegionFileParser') as MockParser:
                instance = MockParser.return_value
                instance.__enter__ = MagicMock(return_value=instance)
                instance.__exit__ = MagicMock(return_value=False)
                instance.to_json = MagicMock(return_value='{"1,2,3": {"name": "Container"}}')
                
                result = main()
        
        assert result == 0
        captured = capsys.readouterr()
        # Should be valid JSON in stdout
        parsed = json.loads(captured.out)
        assert "1,2,3" in parsed

    def test_output_to_file(self, tmp_path):
        """Test --output flag writes to file."""
        region_file = tmp_path / "0.0.region.bin"
        region_file.write_bytes(b"")
        output_file = tmp_path / "output.json"
        
        with patch('sys.argv', ['hytale-region-parser', str(region_file), '-o', str(output_file)]):
            with patch('hytale_region_parser.cli.RegionFileParser') as MockParser:
                instance = MockParser.return_value
                instance.__enter__ = MagicMock(return_value=instance)
                instance.__exit__ = MagicMock(return_value=False)
                instance.to_json = MagicMock(return_value='{"test": "data"}')
                
                result = main()
        
        assert result == 0
        assert output_file.exists()
        content = output_file.read_text()
        assert json.loads(content) == {"test": "data"}

    def test_compact_flag(self, tmp_path, capsys):
        """Test --compact flag produces non-indented JSON."""
        region_file = tmp_path / "0.0.region.bin"
        region_file.write_bytes(b"")
        
        with patch('sys.argv', ['hytale-region-parser', str(region_file), '--compact']):
            with patch('hytale_region_parser.cli.RegionFileParser') as MockParser:
                instance = MockParser.return_value
                instance.__enter__ = MagicMock(return_value=instance)
                instance.__exit__ = MagicMock(return_value=False)
                # Check that to_json is called with indent=None
                instance.to_json = MagicMock(return_value='{}')
                
                main()
                
                instance.to_json.assert_called_once_with(indent=None)

    def test_summary_flag(self, tmp_path, capsys):
        """Test --summary flag uses legacy output."""
        region_file = tmp_path / "0.0.region.bin"
        region_file.write_bytes(b"")
        
        with patch('sys.argv', ['hytale-region-parser', str(region_file), '--summary']):
            with patch('hytale_region_parser.cli.RegionFileParser') as MockParser:
                instance = MockParser.return_value
                instance.parse_summary = MagicMock()
                
                main()
                
                instance.parse_summary.assert_called_once()

    def test_detailed_flag(self, tmp_path, capsys):
        """Test --detailed flag uses legacy output."""
        region_file = tmp_path / "0.0.region.bin"
        region_file.write_bytes(b"")
        
        with patch('sys.argv', ['hytale-region-parser', str(region_file), '--detailed']):
            with patch('hytale_region_parser.cli.RegionFileParser') as MockParser:
                instance = MockParser.return_value
                instance.parse_detailed = MagicMock()
                
                main()
                
                instance.parse_detailed.assert_called_once_with(max_chunks=5, verbose=True)

    def test_detailed_with_max_chunks(self, tmp_path, capsys):
        """Test --detailed with --max-chunks flag."""
        region_file = tmp_path / "0.0.region.bin"
        region_file.write_bytes(b"")
        
        with patch('sys.argv', ['hytale-region-parser', str(region_file), '--detailed', '--max-chunks', '10']):
            with patch('hytale_region_parser.cli.RegionFileParser') as MockParser:
                instance = MockParser.return_value
                instance.parse_detailed = MagicMock()
                
                main()
                
                instance.parse_detailed.assert_called_once_with(max_chunks=10, verbose=True)

    def test_quiet_flag_with_output(self, tmp_path, capsys):
        """Test --quiet flag suppresses stderr messages."""
        region_file = tmp_path / "0.0.region.bin"
        region_file.write_bytes(b"")
        output_file = tmp_path / "output.json"
        
        with patch('sys.argv', ['hytale-region-parser', str(region_file), '-o', str(output_file), '-q']):
            with patch('hytale_region_parser.cli.RegionFileParser') as MockParser:
                instance = MockParser.return_value
                instance.__enter__ = MagicMock(return_value=instance)
                instance.__exit__ = MagicMock(return_value=False)
                instance.to_json = MagicMock(return_value='{}')
                
                main()
        
        captured = capsys.readouterr()
        # Should not print "Output written to..." message
        assert "Output written" not in captured.err
