#!/usr/bin/env python3
"""Directory canary entry point; uses the existing gated capture/import runner."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_brand_capture import main

if __name__ == "__main__":
    raise SystemExit(main(directory=True))
