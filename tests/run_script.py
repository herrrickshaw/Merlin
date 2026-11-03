"""Run a top-level script deterministically in a temp dir; used by the golden tests.

Usage: python run_script.py <script.py> <workdir>. Seeds ``random``/``numpy``, stubs
``yfinance`` (imported but unused by the scripts), then executes the script as ``__main__``.
Prints a JSON object with normalised stdout and every file the script wrote.
"""
import contextlib
import io
import json
import os
import random
import re
import runpy
import sys
import types
from pathlib import Path

DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}(\.\d+)?)?")


def main(script: str, workdir: str) -> dict:
    sys.modules.setdefault("yfinance", types.ModuleType("yfinance"))
    random.seed(7)
    import numpy as np
    np.random.seed(7)
    os.chdir(workdir)
    sys.path.insert(0, str(Path(script).resolve().parent))
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        runpy.run_path(script, run_name="__main__")
    files = {p.name: DATE_RE.sub("<DATE>", p.read_text()) for p in sorted(Path(workdir).iterdir())}
    return {"stdout": DATE_RE.sub("<DATE>", buf.getvalue()), "files": files}


if __name__ == "__main__":
    print(json.dumps(main(sys.argv[1], sys.argv[2]), sort_keys=True))
