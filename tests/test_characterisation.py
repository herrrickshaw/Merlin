"""Pre-refactor behaviour of data_fetcher / batch_screener / screener_runner.

Golden files were generated from the original code on ``master`` (see
``tests/characterise.py``); no network, ``yfinance`` is stubbed.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from characterise import snapshot

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "tests" / "golden"


def test_module_snapshot_matches_golden():
    expected = json.loads((GOLDEN / "snapshot.json").read_text())
    assert snapshot(ROOT) == expected


def test_screener_runner_cli_output_unchanged():
    proc = subprocess.run(
        [sys.executable, "screener_runner.py", "examples/screener_test_data.csv"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    assert proc.stdout == (GOLDEN / "screener_runner_cli.txt").read_text()


def test_screener_runner_usage_exit_code():
    proc = subprocess.run([sys.executable, "screener_runner.py"], cwd=ROOT,
                          capture_output=True, text=True)
    assert proc.returncode == 1
    assert proc.stdout.startswith("Usage: python screener_runner.py")
