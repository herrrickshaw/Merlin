"""Pass-2 characterisation: stdout and written files of the seven analysis scripts are unchanged."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "tests" / "golden" / "scripts"
SCRIPTS = sorted(p.stem for p in GOLDEN.glob("*.json"))


@pytest.mark.parametrize("name", SCRIPTS)
def test_script_output_unchanged(name):
    with tempfile.TemporaryDirectory() as tmp:
        proc = subprocess.run([sys.executable, str(ROOT / "tests" / "run_script.py"),
                               str(ROOT / f"{name}.py"), tmp], capture_output=True, text=True, check=True)
    assert json.loads(proc.stdout) == json.loads((GOLDEN / f"{name}.json").read_text())


def test_all_seven_scripts_pinned():
    assert len(SCRIPTS) == 7
