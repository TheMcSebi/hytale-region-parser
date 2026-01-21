"""Tests for the command-line interface."""

import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from hytale_region_parser.cli import main, detect_folder_structure, get_output_filename_for_single_file
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
        assert 'input_path' in captured.out
        assert '--stdout' in captured.out

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

    def test_single_file_writes_json_to_cwd(self, tmp_path, capsys, monkeypatch):
        """Test that single file writes JSON to current working directory."""
        # Set up input file in a subdirectory
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        region_file = input_dir / "0.0.region.bin"
        region_file.write_bytes(b"")
        
        # Set cwd to a different directory
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        monkeypatch.chdir(output_dir)
        
        with patch('sys.argv', ['hytale-region-parser', str(region_file)]):
            with patch('hytale_region_parser.cli.parse_single_file') as mock_parse:
                mock_parse.return_value = {"1,2,3": {"name": "Container"}}
                result = main()
        
        assert result == 0
        # Output should be in cwd, not next to input file
        expected_output = output_dir / "0.0.region.json"
        assert expected_output.exists()
        assert not (input_dir / "0.0.region.json").exists()
        content = json.loads(expected_output.read_text())
        assert "1,2,3" in content

    def test_stdout_flag_outputs_to_stdout(self, tmp_path, capsys):
        """Test --stdout flag outputs to stdout instead of file."""
        region_file = tmp_path / "0.0.region.bin"
        region_file.write_bytes(b"")
        
        with patch('sys.argv', ['hytale-region-parser', str(region_file), '--stdout']):
            with patch('hytale_region_parser.cli.parse_single_file') as mock_parse:
                mock_parse.return_value = {"1,2,3": {"name": "Container"}}
                result = main()
        
        assert result == 0
        # JSON should be in stdout
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert "1,2,3" in parsed

    def test_output_flag_overrides_default(self, tmp_path):
        """Test --output flag overrides default naming."""
        region_file = tmp_path / "0.0.region.bin"
        region_file.write_bytes(b"")
        output_file = tmp_path / "custom_output.json"
        
        with patch('sys.argv', ['hytale-region-parser', str(region_file), '-o', str(output_file)]):
            with patch('hytale_region_parser.cli.parse_single_file') as mock_parse:
                mock_parse.return_value = {"test": "data"}
                result = main()
        
        assert result == 0
        assert output_file.exists()
        content = json.loads(output_file.read_text())
        assert content == {"test": "data"}

    def test_compact_flag(self, tmp_path, capsys):
        """Test --compact flag produces non-indented JSON."""
        region_file = tmp_path / "0.0.region.bin"
        region_file.write_bytes(b"")
        
        with patch('sys.argv', ['hytale-region-parser', str(region_file), '--stdout', '--compact']):
            with patch('hytale_region_parser.cli.parse_single_file') as mock_parse:
                mock_parse.return_value = {"key": "value"}
                main()
        
        captured = capsys.readouterr()
        # Compact JSON should not have newlines within the object
        assert captured.out.strip() == '{"key": "value"}'

    def test_quiet_flag_suppresses_messages(self, tmp_path, capsys, monkeypatch):
        """Test --quiet flag suppresses stderr messages."""
        region_file = tmp_path / "0.0.region.bin"
        region_file.write_bytes(b"")
        monkeypatch.chdir(tmp_path)
        
        with patch('sys.argv', ['hytale-region-parser', str(region_file), '-q']):
            with patch('hytale_region_parser.cli.parse_single_file') as mock_parse:
                mock_parse.return_value = {}
                main()
        
        captured = capsys.readouterr()
        assert "Output written" not in captured.err


class TestFolderStructureDetection:
    """Tests for folder structure detection."""
    
    def test_chunks_folder_detection(self, tmp_path):
        """Test detection of a 'chunks' folder."""
        world_folder = tmp_path / "default"
        chunks_folder = world_folder / "chunks"
        chunks_folder.mkdir(parents=True)
        (chunks_folder / "0.0.region.bin").write_bytes(b"")
        (chunks_folder / "1.0.region.bin").write_bytes(b"")
        
        structure_type, files_dict = detect_folder_structure(chunks_folder)
        
        assert structure_type == "chunks"
        assert "default" in files_dict
        assert len(files_dict["default"]) == 2
    
    def test_universe_folder_detection(self, tmp_path):
        """Test detection of universe structure with multiple worlds."""
        worlds_folder = tmp_path / "worlds"
        
        # Create two world folders with chunks
        for world_name in ["world1", "world2"]:
            chunks_folder = worlds_folder / world_name / "chunks"
            chunks_folder.mkdir(parents=True)
            (chunks_folder / "0.0.region.bin").write_bytes(b"")
        
        structure_type, files_dict = detect_folder_structure(worlds_folder)
        
        assert structure_type == "universe"
        assert "world1" in files_dict
        assert "world2" in files_dict
        assert len(files_dict["world1"]) == 1
        assert len(files_dict["world2"]) == 1
    
    def test_flat_folder_detection(self, tmp_path):
        """Test detection of flat folder with region files."""
        region_folder = tmp_path / "regions"
        region_folder.mkdir()
        (region_folder / "0.0.region.bin").write_bytes(b"")
        (region_folder / "1.1.region.bin").write_bytes(b"")
        
        structure_type, files_dict = detect_folder_structure(region_folder)
        
        assert structure_type == "flat"
        assert "" in files_dict
        assert len(files_dict[""]) == 2
    
    def test_empty_folder_detection(self, tmp_path):
        """Test detection of folder with no region files."""
        empty_folder = tmp_path / "empty"
        empty_folder.mkdir()
        
        structure_type, files_dict = detect_folder_structure(empty_folder)
        
        assert structure_type == "empty"


class TestOutputFilenaming:
    """Tests for output filename generation."""
    
    def test_single_file_output_in_cwd(self, tmp_path, monkeypatch):
        """Test output filename is in current working directory."""
        monkeypatch.chdir(tmp_path)
        input_path = Path("/some/other/path/-2.-3.region.bin")
        output_path = get_output_filename_for_single_file(input_path)
        
        assert output_path == tmp_path / "-2.-3.region.json"
    
    def test_positive_coords_output_name(self, tmp_path, monkeypatch):
        """Test output filename for positive coordinates."""
        monkeypatch.chdir(tmp_path)
        input_path = Path("/path/to/5.10.region.bin")
        output_path = get_output_filename_for_single_file(input_path)
        
        assert output_path == tmp_path / "5.10.region.json"


class TestFolderProcessing:
    """Tests for folder processing modes."""
    
    def test_flat_folder_creates_json_in_cwd(self, tmp_path, capsys, monkeypatch):
        """Test that flat folder creates regions.json in cwd."""
        region_folder = tmp_path / "myregions"
        region_folder.mkdir()
        (region_folder / "0.0.region.bin").write_bytes(b"")
        
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        monkeypatch.chdir(output_dir)
        
        with patch('sys.argv', ['hytale-region-parser', str(region_folder)]):
            with patch('hytale_region_parser.cli.parse_multiple_files') as mock_parse:
                mock_parse.return_value = {"data": "test"}
                result = main()
        
        assert result == 0
        output_file = output_dir / "regions.json"
        assert output_file.exists()
        # Should NOT be in the input folder
        assert not (region_folder / "regions.json").exists()
    
    def test_chunks_folder_creates_world_json_in_cwd(self, tmp_path, capsys, monkeypatch):
        """Test that chunks folder creates <worldname>.json in cwd."""
        world_folder = tmp_path / "myworld"
        chunks_folder = world_folder / "chunks"
        chunks_folder.mkdir(parents=True)
        (chunks_folder / "0.0.region.bin").write_bytes(b"")
        
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        monkeypatch.chdir(output_dir)
        
        with patch('sys.argv', ['hytale-region-parser', str(chunks_folder)]):
            with patch('hytale_region_parser.cli.parse_multiple_files') as mock_parse:
                mock_parse.return_value = {"data": "test"}
                result = main()
        
        assert result == 0
        output_file = output_dir / "myworld.json"
        assert output_file.exists()
        # Should NOT be in the world folder
        assert not (world_folder / "myworld.json").exists()
    
    def test_universe_folder_creates_per_world_json_in_cwd(self, tmp_path, capsys, monkeypatch):
        """Test that universe folder creates one JSON per world in cwd."""
        worlds_folder = tmp_path / "worlds"
        
        for world_name in ["alpha", "beta"]:
            chunks_folder = worlds_folder / world_name / "chunks"
            chunks_folder.mkdir(parents=True)
            (chunks_folder / "0.0.region.bin").write_bytes(b"")
        
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        monkeypatch.chdir(output_dir)
        
        with patch('sys.argv', ['hytale-region-parser', str(worlds_folder)]):
            with patch('hytale_region_parser.cli.parse_multiple_files') as mock_parse:
                mock_parse.return_value = {"data": "test"}
                result = main()
        
        assert result == 0
        assert (output_dir / "alpha.json").exists()
        assert (output_dir / "beta.json").exists()
        # Should NOT be in the input folder
        assert not (worlds_folder / "alpha.json").exists()
        assert not (worlds_folder / "beta.json").exists()
    
    def test_folder_with_no_region_files_errors(self, tmp_path, capsys):
        """Test that folder with no region files returns error."""
        empty_folder = tmp_path / "empty"
        empty_folder.mkdir()
        
        with patch('sys.argv', ['hytale-region-parser', str(empty_folder)]):
            result = main()
        
        assert result == 1
        captured = capsys.readouterr()
        assert "No .region.bin files found" in captured.err
    
    def test_folder_stdout_mode(self, tmp_path, capsys, monkeypatch):
        """Test that --stdout works with folder input."""
        region_folder = tmp_path / "regions"
        region_folder.mkdir()
        (region_folder / "0.0.region.bin").write_bytes(b"")
        
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        monkeypatch.chdir(output_dir)
        
        with patch('sys.argv', ['hytale-region-parser', str(region_folder), '--stdout']):
            with patch('hytale_region_parser.cli.parse_multiple_files') as mock_parse:
                mock_parse.return_value = {"folder": "data"}
                result = main()
        
        assert result == 0
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed == {"folder": "data"}
        # No JSON file should be created
        assert not (output_dir / "regions.json").exists()
