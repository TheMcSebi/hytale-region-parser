# Hytale Region Parser - Tests

This directory contains tests for the hytale-region-parser package.

## Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run with coverage
pytest --cov=hytale_region_parser

# Run specific test file
pytest tests/test_parser.py
```

## Test Structure

- `test_models.py` - Tests for data models
- `test_storage.py` - Tests for IndexedStorageFile parsing
- `test_chunk_parser.py` - Tests for chunk data parsing
- `test_region_parser.py` - Tests for high-level region parsing
- `test_cli.py` - Tests for command-line interface
