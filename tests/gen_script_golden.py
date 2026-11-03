"""Regenerate tests/golden/scripts/*.json from the scripts as they are now (run once, pre-refactor)."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ["alternative_screens_analysis", "forward_5year_stock_picks", "nbim_criteria_analysis",
           "options_portfolio_backtest", "currency_adjusted_backtest", "five_year_backtest",
           "advanced_analysis_demo"]


def run(repo: Path, name: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        out = subprocess.run([sys.executable, str(ROOT / "tests" / "run_script.py"),
                              str(repo / f"{name}.py"), tmp],
                             capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


if __name__ == "__main__":
    dest = ROOT / "tests" / "golden" / "scripts"
    dest.mkdir(parents=True, exist_ok=True)
    for n in SCRIPTS:
        (dest / f"{n}.json").write_text(json.dumps(run(ROOT, n), indent=1, sort_keys=True) + "\n")
