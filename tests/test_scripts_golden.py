"""Pass-2 characterisation: stdout and written files of the seven analysis scripts are unchanged."""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "tests" / "golden" / "scripts"
SCRIPTS = sorted(p.stem for p in GOLDEN.glob("*.json"))


FLOAT_RE = re.compile(r"-?\d+\.\d+(?:[eE][+-]?\d+)?")


def _round_floats(obj):
    """Round every decimal in captured text to 12 significant digits.

    The last digit of a printed float differs between platforms (macOS capture vs Linux CI runner).
    """
    if isinstance(obj, dict):
        return {k: _round_floats(v) for k, v in obj.items()}
    if isinstance(obj, str):
        return FLOAT_RE.sub(lambda m: format(float(m.group()), ".12g"), obj)
    return obj


@pytest.mark.parametrize("name", SCRIPTS)
def test_script_output_unchanged(name):
    with tempfile.TemporaryDirectory() as tmp:
        proc = subprocess.run([sys.executable, str(ROOT / "tests" / "run_script.py"),
                               str(ROOT / f"{name}.py"), tmp], capture_output=True, text=True, check=True)
    assert _round_floats(json.loads(proc.stdout)) == _round_floats(json.loads((GOLDEN / f"{name}.json").read_text()))


def test_all_seven_scripts_pinned():
    assert len(SCRIPTS) == 7
