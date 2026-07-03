#!/bin/bash

# Stock Analysis Workflow - Merlin LFS Integration
# Analyzes NSE/BSE stock data and uploads to Merlin repository

set -e

# Configuration
MERLIN_REPO="${MERLIN_REPO:-${HOME}/Merlin}"
DATA_DIR="${DATA_DIR:-./data}"
ANALYSIS_DIR="${ANALYSIS_DIR:-./analyses}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "=== Merlin Stock Analysis Workflow ==="
echo "Repo: $MERLIN_REPO"
echo "Timestamp: $TIMESTAMP"

# Build merlin if not exists
if [ ! -f "_build/bin/merlin" ]; then
    echo "Building Merlin..."
    chmod +x build.sh
    ./build.sh
fi

MERLIN="./_build/bin/merlin"

# Create output directories
mkdir -p "$DATA_DIR" "$ANALYSIS_DIR"

# Example 1: Analyze average prices
if [ -f "examples/nse_sample.csv" ]; then
    echo ""
    echo "1. Computing average prices..."
    $MERLIN analyze-csv examples/nse_sample.csv \
        --key symbol --field close --agg mean \
        --output "$ANALYSIS_DIR/avg_prices_${TIMESTAMP}.json"
    echo "   ✓ Saved to analyses/avg_prices_${TIMESTAMP}.json"
fi

# Example 2: Statistics on volume
if [ -f "examples/nse_sample.csv" ]; then
    echo ""
    echo "2. Computing volume statistics..."
    $MERLIN stats examples/nse_sample.csv volume | tee "$ANALYSIS_DIR/volume_stats_${TIMESTAMP}.txt"
fi

# Example 3: Upload to Merlin repo
if [ -d "$MERLIN_REPO/.git" ]; then
    echo ""
    echo "3. Uploading results to Merlin repository..."

    for file in "$ANALYSIS_DIR"/*_${TIMESTAMP}.*; do
        if [ -f "$file" ]; then
            filename=$(basename "$file")
            echo "   Uploading $filename..."
            $MERLIN upload "$MERLIN_REPO" "$file" "analyses/$filename" \
                --message "Automated stock analysis $TIMESTAMP" \
                --push || echo "   ! Upload failed (repo may not have remote)"
        fi
    done
fi

# Example 4: Generate summary report
echo ""
echo "4. Generating summary report..."
cat > "$ANALYSIS_DIR/summary_${TIMESTAMP}.txt" <<EOF
Merlin Stock Analysis Report
============================
Date: $(date)
Timestamp: $TIMESTAMP
Source: NSE Sample Data
Status: Analysis Complete

Analyses Generated:
EOF

ls -1 "$ANALYSIS_DIR"/*_${TIMESTAMP}.* >> "$ANALYSIS_DIR/summary_${TIMESTAMP}.txt" 2>/dev/null || true

echo ""
echo "=== Workflow Complete ==="
echo "Results in: $ANALYSIS_DIR/"
echo ""
echo "Next steps:"
echo "  1. Review results: ls -la $ANALYSIS_DIR/"
echo "  2. Check Merlin repo: cd $MERLIN_REPO && git log -5"
echo "  3. Deploy analysis: $MERLIN upload <repo> <file> <dest> --push"
