"""Backward-compatible wrapper: the GX logic now lives in scripts/gx_validation.py."""
import os
import sys
from pathlib import Path

PROJECT_DIR = Path(os.getenv("DSP_PROJECT_DIR", "/opt/airflow/project"))
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from scripts.gx_validation import run_validation  # noqa: E402,F401
