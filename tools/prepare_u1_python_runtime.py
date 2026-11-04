"""Prepare a hash-pinned local CPython runtime; never install or activate U1.

准备固定摘要的本地 CPython；不安装或激活 U1。
No network access and no dependency on the builder's site-packages.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import struct
import subprocess
import zipfile


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def prepare(archive, expected_sha256, output):
    archive, output = Path(archive).resolve(), Path(output).absolute()
    if not re.fullmatch('[0-9a-f]{64}', expected_sha256):
        raise ValueError('EXPECTED_SHA256_REQUIRED')
    raw = archive.read_bytes()
    if sha(raw) != expected_sha256:
        raise ValueError('ARCHIVE_HASH_MISMATCH')
    # A failed preparation is retained for inspection, never resumed/overwritten.
    if output.exists() or output.is_symlink():
        raise ValueError('NEW_OUTPUT_REQUIRED')
    for parent in output.parents:
        if parent.exists() and (parent.is_symlink() or
                getattr(parent.stat(), 'st_file_attributes', 0) & 0x400):
            raise ValueError('REPARSE_OUTPUT_PARENT')
    with zipfile.ZipFile(archive) as z:
        members = z.infolist()
        if len(members) > 20000 or sum(x.file_size for x in members) > 512*1024*1024:
            raise ValueError('ARCHIVE_LIMIT')
        seen = set()
        for item in members:
            name = item.filename.rstrip('/')
            p = PurePosixPath(name)
            parts = name.split('/')
            if (not name or p.is_absolute() or '\\' in item.orig_filename or
                    '\x00' in item.orig_filename or ':' in name or
                    any(x in ('', '.', '..') or x.endswith((' ', '.')) for x in parts) or
                    any(x.split('.')[0].upper() in {'CON','PRN','AUX','NUL'} |
                        {f'{a}{i}' for a in ('COM','LPT') for i in range(1,10)} for x in parts) or
                    (item.external_attr >> 16) & 0o170000 == 0o120000):
                raise ValueError('ARCHIVE_PATH')
            key = name.casefold()
            if key in seen:
                raise ValueError('ARCHIVE_COLLISION')
            seen.add(key)
        # Extraction is confined to a new workspace directory; no installer runs.
        output.mkdir(parents=True)
        z.extractall(output)
    candidates = list(output.rglob('python.exe'))
    if len(candidates) != 1:
        raise ValueError('EXACTLY_ONE_PYTHON_REQUIRED')
    exe = candidates[0]
    pe = exe.read_bytes()
    offset = struct.unpack_from('<I', pe, 0x3c)[0]
    if pe[:2] != b'MZ' or pe[offset:offset+4] != b'PE\0\0' or struct.unpack_from('<H', pe, offset+4)[0] != 0x8664:
        raise ValueError('AMD64_PYTHON_REQUIRED')
    probe = ('import sys,sqlite3,ssl,ctypes,multiprocessing,zoneinfo,json,hashlib;'
             'print(json.dumps(dict(version=sys.version,executable=sys.executable,'
             'prefix=sys.prefix,path=sys.path,sqlite=sqlite3.sqlite_version,ssl=ssl.OPENSSL_VERSION)))')
    env = {k:v for k,v in os.environ.items() if not k.upper().startswith('PYTHON')}
    result = subprocess.run([str(exe), '-I', '-B', '-c', probe], cwd=output,
                            env=env, capture_output=True, text=True, timeout=30, check=True)
    observed = json.loads(result.stdout)
    root = str(output.resolve()).casefold()
    if any(not str(Path(p).resolve()).casefold().startswith(root + os.sep)
           and str(Path(p).resolve()).casefold() != root for p in observed['path']):
        raise ValueError('EXTERNAL_IMPORT_PATH')
    files = {p.relative_to(output).as_posix(): sha(p.read_bytes())
             for p in sorted(output.rglob('*')) if p.is_file()}
    manifest = dict(schema='rokt.u1-cpython-input.v1', archive_sha256=expected_sha256,
                    python=exe.relative_to(output).as_posix(), architecture='AMD64',
                    files=files, probe=observed, third_party_dependencies_complete=False,
                    provider_contract='CONTRACT_MISSING', production_ready=False,
                    allow_install=False, allow_dispatch=False, allow_cancel_dispatch=False,
                    smtp_enabled=False)
    (output/'RUNTIME_MANIFEST.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = prepare(args.archive, args.sha256, args.output)
    print(json.dumps({k:v for k,v in result.items() if k not in ('files','probe')}))
