# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-01-21

### Added

- Initial release as a Python package
- `RegionFileParser` class for parsing `.region.bin` files
- Context manager support for file handling
- Iterator interface for chunk data (`iter_chunks()`)
- Summary generation with `get_summary()`
- Data models: `ParsedChunkData`, `ChunkSectionData`, `BlockComponent`, `ItemContainerData`
- BSON parser for Hytale's codec format
- IndexedStorageFile format support
- Zstandard decompression
- Command-line interface (`hytale-region-parser`)
- Type hints throughout
- Support for Python 3.8+

### Changed

- Restructured from single script to proper Python package
- Added `src/` layout for better packaging practices

[0.1.0]: https://github.com/yourusername/hytale-region-parser/releases/tag/v0.1.0
