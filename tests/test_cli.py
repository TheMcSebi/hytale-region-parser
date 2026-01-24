"""Tests for the command-line interface."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from hytale_region_parser.cli import (
    main, detect_folder_structure, matches_filter, 
    filter_block_summary, filter_blocks_data
)


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
        assert "0.1.2" in captured.out

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
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        region_file = input_dir / "0.0.region.bin"
        region_file.write_bytes(b"")

        output_dir = tmp_path / "output"
        output_dir.mkdir()
        monkeypatch.chdir(output_dir)

        with patch('sys.argv', ['hytale-region-parser', str(region_file)]):
            with patch('hytale_region_parser.cli.parse_files') as mock_parse:
                mock_parse.return_value = {"1,2,3": {"name": "Container"}}
                result = main()

        assert result == 0
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
            with patch('hytale_region_parser.cli.parse_files') as mock_parse:
                mock_parse.return_value = {"1,2,3": {"name": "Container"}}
                result = main()

        assert result == 0
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert "1,2,3" in parsed

    def test_output_flag_overrides_default(self, tmp_path):
        """Test --output flag overrides default naming."""
        region_file = tmp_path / "0.0.region.bin"
        region_file.write_bytes(b"")
        output_file = tmp_path / "custom_output.json"

        with patch('sys.argv', ['hytale-region-parser', str(region_file), '-o', str(output_file)]):
            with patch('hytale_region_parser.cli.parse_files') as mock_parse:
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
            with patch('hytale_region_parser.cli.parse_files') as mock_parse:
                mock_parse.return_value = {"key": "value"}
                main()

        captured = capsys.readouterr()
        assert captured.out.strip() == '{"key": "value"}'

    def test_quiet_flag_suppresses_messages(self, tmp_path, capsys, monkeypatch):
        """Test --quiet flag suppresses stderr messages."""
        region_file = tmp_path / "0.0.region.bin"
        region_file.write_bytes(b"")
        monkeypatch.chdir(tmp_path)

        with patch('sys.argv', ['hytale-region-parser', str(region_file), '-q']):
            with patch('hytale_region_parser.cli.parse_files') as mock_parse:
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


class TestFolderProcessing:
    """Tests for folder processing modes."""

    def test_flat_folder_creates_json_in_cwd(self, tmp_path, monkeypatch):
        """Test that flat folder creates regions.json in cwd."""
        region_folder = tmp_path / "myregions"
        region_folder.mkdir()
        (region_folder / "0.0.region.bin").write_bytes(b"")

        output_dir = tmp_path / "output"
        output_dir.mkdir()
        monkeypatch.chdir(output_dir)

        with patch('sys.argv', ['hytale-region-parser', str(region_folder)]):
            with patch('hytale_region_parser.cli.parse_files') as mock_parse:
                mock_parse.return_value = {"data": "test"}
                result = main()

        assert result == 0
        output_file = output_dir / "regions.json"
        assert output_file.exists()
        assert not (region_folder / "regions.json").exists()

    def test_chunks_folder_creates_world_json_in_cwd(self, tmp_path, monkeypatch):
        """Test that chunks folder creates <worldname>.json in cwd."""
        world_folder = tmp_path / "myworld"
        chunks_folder = world_folder / "chunks"
        chunks_folder.mkdir(parents=True)
        (chunks_folder / "0.0.region.bin").write_bytes(b"")

        output_dir = tmp_path / "output"
        output_dir.mkdir()
        monkeypatch.chdir(output_dir)

        with patch('sys.argv', ['hytale-region-parser', str(chunks_folder)]):
            with patch('hytale_region_parser.cli.parse_files') as mock_parse:
                mock_parse.return_value = {"data": "test"}
                result = main()

        assert result == 0
        output_file = output_dir / "myworld.json"
        assert output_file.exists()
        assert not (world_folder / "myworld.json").exists()

    def test_universe_folder_creates_per_world_json_in_cwd(self, tmp_path, monkeypatch):
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
            with patch('hytale_region_parser.cli.parse_files') as mock_parse:
                mock_parse.return_value = {"data": "test"}
                result = main()

        assert result == 0
        assert (output_dir / "alpha.json").exists()
        assert (output_dir / "beta.json").exists()
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

    def test_folder_stdout_mode(self, tmp_path, monkeypatch, capsys):
        """Test that --stdout works with folder input."""
        region_folder = tmp_path / "regions"
        region_folder.mkdir()
        (region_folder / "0.0.region.bin").write_bytes(b"")

        output_dir = tmp_path / "output"
        output_dir.mkdir()
        monkeypatch.chdir(output_dir)

        with patch('sys.argv', ['hytale-region-parser', str(region_folder), '--stdout']):
            with patch('hytale_region_parser.cli.parse_files') as mock_parse:
                mock_parse.return_value = {"folder": "data"}
                result = main()

        assert result == 0
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed == {"folder": "data"}
        assert not (output_dir / "regions.json").exists()


class TestBlockFilter:
    """Tests for block filter functionality."""

    def test_matches_filter_wildcard(self):
        """Test wildcard matching."""
        assert matches_filter("Ore_Iron", "Ore_*") is True
        assert matches_filter("Ore_Gold", "Ore_*") is True
        assert matches_filter("Stone_Block", "Ore_*") is False
        assert matches_filter("Iron_Ore", "*_Ore") is True

    def test_matches_filter_question_mark(self):
        """Test single character wildcard matching."""
        assert matches_filter("Ore_A", "Ore_?") is True
        assert matches_filter("Ore_AB", "Ore_?") is False
        assert matches_filter("Ore_AB", "Ore_??") is True

    def test_matches_filter_exact(self):
        """Test exact name matching."""
        assert matches_filter("Stone", "Stone") is True
        assert matches_filter("Stone_Block", "Stone") is False

    def test_filter_block_summary(self):
        """Test filtering block summary dictionary."""
        summary = {
            "Ore_Iron": 100,
            "Ore_Gold": 50,
            "Stone": 1000,
            "Dirt": 500
        }
        filtered = filter_block_summary(summary, "Ore_*")
        assert filtered == {"Ore_Iron": 100, "Ore_Gold": 50}

    def test_filter_blocks_data(self):
        """Test filtering full blocks data."""
        data = {
            "metadata": {
                "block_summary": {
                    "Ore_Iron": 2,
                    "Stone": 3
                }
            },
            "blocks": {
                "0,0,0": {"name": "Ore_Iron"},
                "1,1,1": {"name": "Stone"},
                "2,2,2": {"name": "Ore_Gold"},
            }
        }
        filtered = filter_blocks_data(data, "Ore_*")
        assert filtered["metadata"]["block_summary"] == {"Ore_Iron": 2}
        assert len(filtered["blocks"]) == 2
        assert "0,0,0" in filtered["blocks"]
        assert "2,2,2" in filtered["blocks"]
        assert "1,1,1" not in filtered["blocks"]

    def test_filter_flag_in_help(self, capsys):
        """Test that --filter flag appears in help."""
        with pytest.raises(SystemExit):
            with patch('sys.argv', ['hytale-region-parser', '--help']):
                main()

        captured = capsys.readouterr()
        assert '--filter' in captured.out
        assert '-f' in captured.out
        assert 'PATTERN' in captured.out
