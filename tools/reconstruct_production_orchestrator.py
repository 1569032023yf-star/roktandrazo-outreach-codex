"""Recover fixed Git bytes for offline diagnosis / 从固定Git对象恢复离线诊断源码。"""
import argparse
import hashlib
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
COMMIT = "df209f529ac1925da3689ebf0bc38c8b8ada8c0d"
SOURCE_SHA256 = "e7e619d3e40f415c1894aa3e1087978875c6f26570755254ab535b68e5580903"


def reconstruct():
    """Read only Git; never access production / 仅读Git，不访问生产。"""
    data = subprocess.check_output(
        ["git", "show", COMMIT + ":bd_orchestrator.py"], cwd=ROOT)
    if hashlib.sha256(data).hexdigest() != SOURCE_SHA256:
        raise ValueError("FIXED_SOURCE_SHA_MISMATCH")
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    # Fixed development-only destination; no arbitrary file/export input.
    destination = ROOT / "autonomy/runtime/bd_full_20261022/production_orchestrator_matched.py"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(reconstruct())
    print(SOURCE_SHA256, destination)


if __name__ == "__main__":
    main()
