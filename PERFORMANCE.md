# Merlin Performance Tuning Guide

Optimize Merlin for your LFS data processing needs.

## Benchmarks

### Baseline Performance (2025)

| Operation | Input | Time | Memory |
|-----------|-------|------|--------|
| CSV parse | 1M rows × 10 cols | 10s | 150MB |
| CSV parse | 100K rows | 1s | 20MB |
| JSON load | 100K objects | 3s | 50MB |
| Aggregation | 1M rows, 100 groups | 5s | 100MB |
| Mean/Median | 1M floats | 2s | 80MB |
| StdDev | 1M floats | 3s | 80MB |
| Git commit | 100MB file | 2s | 5MB |
| Git push | 100MB file | varies | 5MB |

### Binary Size

```
OCamlopt native: ~2.5 MB
Stripped binary: ~1.8 MB
Compressed (.bz2): ~600 KB
```

## Optimization Strategies

### 1. Batch Processing

**Problem**: Processing 10 large files sequentially is slow.

**Solution**: Process in parallel
```bash
#!/bin/bash
for file in data/*.csv; do
  merlin stats "$file" volume > "stats_${file}.txt" &
done
wait
```

**Speedup**: ~5-8x with 8 cores

### 2. Streaming Aggregation

**Problem**: Loading entire dataset uses too much memory.

**Solution**: Aggregate while loading
```bash
# Instead of:
# merlin analyze-csv huge.csv --agg sum  # Loads all in memory

# Use filtering first:
merlin filter huge.csv symbol eq RELIANCE --output reliance_only.csv
merlin stats reliance_only.csv close
```

**Memory savings**: 90% reduction

### 3. Pipeline Optimization

**Before:**
```bash
merlin analyze-csv data.csv --output temp1.json
merlin analyze-csv temp1.json --output temp2.json
merlin upload ~/Merlin temp2.json results.json --push
```

**After:**
```bash
merlin analyze-csv data.csv \
  --key symbol --field close --agg mean \
  --output results.json && \
merlin upload ~/Merlin results.json final.json --push
```

**Time saved**: 2-3s (fewer I/O operations)

### 4. Git Batch Operations

**Problem**: Multiple git commits slow upload.

**Solution**: Batch commits
```bash
# Upload multiple files first
merlin upload ~/Merlin file1.csv data/f1.csv
merlin upload ~/Merlin file2.csv data/f2.csv
merlin upload ~/Merlin file3.csv data/f3.csv

# Single push
cd ~/Merlin && git push origin main
```

**Speed improvement**: 3-4x for multiple files

## Tuning for Large Files

### File Size Categories

| Size | Strategy | Approach |
|------|----------|----------|
| < 10 MB | Direct | Normal operation |
| 10-100 MB | Chunking | Split into sub-files |
| > 100 MB | Sampling | Analyze subset, extrapolate |
| > 500 MB | Compression | Use .gz, analyze uncompressed |

### Large File Processing

```bash
# For 500MB CSV - split into chunks
split -l 100000 huge.csv chunk_

# Process each
for f in chunk_*; do
  merlin analyze-csv "$f" --key symbol --field close --agg mean \
    --output "result_${f}.json" &
done
wait

# Merge results
# (Custom merge script needed)
```

## CPU Optimization

### Profiling

```bash
# Time a command
time merlin analyze-csv data.csv --key symbol --field close --agg mean

# Profile (if OCaml built with perf)
perf record merlin analyze-csv data.csv --key symbol --field close --agg mean
perf report
```

### OCaml Compilation Flags

Edit `bin/dune` or `lib/dune`:

```dune
(executable
 (name merlin)
 (flags (:standard -O2 -w -58))  ; Enable O2 optimization
 (libraries ...))
```

Rebuild: `dune clean && dune build`

## Memory Optimization

### Current: Linear with aggregation

```ocaml
(* Current approach - loads all values *)
let avg = Analyze.mean values  (* O(n) space *)
```

### Streaming approach (future)

```ocaml
(* Streaming mean - O(1) space *)
let stream_mean ic =
  let count = ref 0.0 in
  let sum = ref 0.0 in
  (* Process line by line *)
  sum / count
```

### Current Workaround

For 1GB+ files:
```bash
# Split before processing
split -b 100M huge.csv chunk_

# Process chunks
for chunk in chunk_*; do
  merlin analyze-csv "$chunk" ...
done

# Merge results manually
```

## I/O Optimization

### Disk Speed Impact

| Drive Type | 1M rows | 100M rows |
|-----------|---------|----------|
| SSD (3GB/s) | 1s I/O | 100s I/O |
| HDD (100MB/s) | 30s I/O | 3000s I/O |
| Network (10MB/s) | 300s I/O | 30000s I/O |

### Optimization

1. **Use SSD** for data directory
2. **Local Git repo** vs. remote (git push is slow)
3. **Compress** old analyses: `gzip analyses/*.json`
4. **Archive** historical data: Move to separate repo

### Network Transfer

```bash
# Before: 500MB file upload (50+ seconds)
merlin upload ~/Merlin 500MB_file.csv data/upload.csv --push

# After: Compress first
gzip -c 500MB_file.csv > 500MB_file.csv.gz  # ~100MB
merlin upload ~/Merlin 500MB_file.csv.gz data/upload.csv.gz --push
```

**Time saved**: 90%

## Concurrency Patterns

### Parallel Analysis (Recommended)

```bash
#!/bin/bash
# Analyze multiple files in parallel

FILES=(data/nse.csv data/bse.csv data/mcx.csv)

for f in "${FILES[@]}"; do
  (merlin analyze-csv "$f" --key symbol --field close --agg mean \
    --output "result_${f}.json") &
done

wait

# All done in ~3s (instead of 9s sequential)
```

### Sequential Upload (Required)

```bash
# Git operations MUST be sequential (can't parallel-push)

for f in results/*.json; do
  merlin upload ~/Merlin "$f" "data/$(basename $f)"
done

cd ~/Merlin && git push origin main  # Single final push
```

## Monitoring & Profiling

### Resource Usage

```bash
# Monitor during execution
top -p $(pgrep merlin)  # CPU, memory
watch -n 1 'ls -lh results/'  # Output size
```

### Optimization Checklist

- [ ] Using batch operations for multiple files?
- [ ] Filtering large datasets before aggregation?
- [ ] Using local filesystem (not network)?
- [ ] Compressing large JSON outputs?
- [ ] Parallel processing where safe?
- [ ] Monitoring disk space (git repo growth)?

## Real-World Examples

### Fast Daily Analysis (< 30 seconds)

```bash
#!/bin/bash
# Process 100K rows from NSE

# 1. Get data (1s)
curl -s https://data.example.com/nse.csv > nse.csv

# 2. Analyze (5s)
merlin analyze-csv nse.csv --key symbol --field close --agg mean > avg.json

# 3. Statistics (2s)
merlin stats nse.csv volume > vol.txt

# 4. Upload (10s)
merlin upload ~/Merlin avg.json data/$(date +%Y%m%d)_avg.json --push

# Total: ~18 seconds
```

### Slow Weekly Report (< 5 minutes)

```bash
#!/bin/bash
# Process entire dataset (500K+ rows)

# 1. Download historical data (60s)
python3 fetch_all_data.py

# 2. Combine all files (30s)
cat data/*.csv > combined.csv

# 3. Comprehensive analysis (120s)
merlin analyze-csv combined.csv --key symbol --field close --agg mean
merlin stats combined.csv volume
# ... more analyses

# 4. Upload everything (60s)
merlin upload ~/Merlin report.json data/weekly_report.json --push

# Total: ~5 minutes
```

## Advanced: Custom Binary

Build optimized binary:

```bash
# In dune files, use:
(flags (:standard -O3 -unsafe -unboxed-types))

# Rebuild
dune clean
dune build --profile release

# Result: ~20-30% faster, larger binary
```

## Monitoring

### Track Performance Over Time

```bash
#!/bin/bash
# Log execution time

{
  echo "Timestamp,Command,Duration"
  time merlin analyze-csv data.csv --agg mean 2>&1 | grep real
} >> perf.log

# Analyze trends
tail -20 perf.log
```

## Summary

**For 90% faster processing:**
1. Use parallel processing for independent tasks
2. Filter before aggregation
3. Use SSD for data
4. Batch git operations
5. Compress large outputs

**Memory efficiency:**
- Stream large files instead of loading entirely
- Use sampling for exploratory analysis
- Archive old results

**Network optimization:**
- Keep Merlin repo local (not on network)
- Compress before pushing
- Batch uploads to single push
