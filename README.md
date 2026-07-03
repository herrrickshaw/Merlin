# Merlin: LFS Data Analyzer & Uploader

A compact OCaml tool for analyzing Large File Storage (LFS) data and uploading results to Git repositories.

## Features

- **Fast CSV/JSON parsing** - Optimized for large datasets
- **Statistical analysis** - Mean, median, percentiles, stddev
- **Data aggregation** - Group and aggregate by fields
- **Git integration** - Direct commit and push to repo
- **Compact binary** - ~2MB single executable
- **Low memory footprint** - Stream processing for large files

## Build

```bash
make build
# or
dune build
```

## Install

```bash
make install
# Binary: ~/.opam/default/bin/merlin
```

## Quick Start

### Analyze CSV

```bash
merlin analyze-csv data.csv --key company --field revenue --agg sum
```

### Upload to Merlin Repo

```bash
merlin upload /path/to/Merlin-repo results.json data/results.json --push
```

### Statistics

```bash
merlin stats data.csv price
```

## Commands

### `analyze-csv <file> [OPTIONS]`

Analyze CSV data with aggregation.

```bash
merlin analyze-csv sales.csv --key region --field amount --agg sum --output summary.json
```

**Options:**
- `--key FIELD` - Grouping field (default: id)
- `--agg TYPE` - Aggregation type: sum, mean, count (default: sum)
- `--field FIELD` - Field to aggregate
- `--output FILE` - Output JSON file

### `analyze-json <file>`

Load and inspect JSON data.

```bash
merlin analyze-json data.json
```

### `upload <repo> <source> <dest> [OPTIONS]`

Upload file to Git repository.

```bash
merlin upload /path/to/repo local.csv data/upload.csv --message "New data" --push
```

**Options:**
- `--message MSG` - Commit message
- `--push` - Push to remote

### `stats <file> <field>`

Compute statistics on a field.

```bash
merlin stats data.csv price
# Output: count, mean, median, min, max, stddev
```

### `filter <file> <field> <op> <value>`

Filter records by condition.

```bash
merlin filter data.csv price gt 100 --output filtered.csv
```

## Example: Stock Market Analysis

```bash
# 1. Analyze NSE stock data
merlin analyze-csv nse_data.csv --key symbol --field close --agg mean --output avg_prices.json

# 2. Upload to Merlin
merlin upload ~/Merlin avg_prices.json analyses/nse_avg.json --push

# 3. Get statistics
merlin stats nse_data.csv volume
```

## Performance

- CSV parsing: ~100K records/sec
- JSON processing: ~50K records/sec
- Binary size: ~2MB
- Memory: Constant with streaming, linear with aggregation

## Architecture

```
bin/
  merlin.ml          - CLI interface
lib/
  data.ml           - CSV/JSON parsing & data ops
  analyze.ml        - Statistics & aggregation
  uploader.ml       - Git operations
```

## Development

```bash
make dev          # Watch mode
make test         # Run tests
make clean        # Clean build
```

## License

MIT
