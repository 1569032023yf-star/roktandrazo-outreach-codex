"""Windows offline directory-publication primitive, outside the installer.

Caller-owned isolated paths only. This is not a trusted-handle implementation:
path/ACL races, original Inventory leases and production authorization remain
unresolved. Never wire this into production Execute based on test success.
"""
import hashlib
import os
from pathlib import Path
import re
import stat


def _ordinary(path, directory):
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
        raise ValueError('REPARSE_REJECTED')
    if (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)) is not True:
        raise ValueError('UNEXPECTED_FILE_TYPE')
    if not directory and info.st_nlink != 1:
        raise ValueError('HARDLINK_REJECTED')


def _verify(directory, expected):
    _ordinary(directory, True)
    if set(p.name for p in directory.iterdir()) != set(expected):
        raise ValueError('EXACT_FILE_SET_REQUIRED')
    for name, digest in expected.items():
        path = directory / name
        _ordinary(path, False)
        with path.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != digest:
                raise ValueError('FILE_HASH_MISMATCH')


def publish_first_directory_offline(staging, destination, manifest, *, offline_only=False):
    """Rename same-parent staged directory without replacing any destination.

    Windows os.rename rejects an existing target, including an empty directory;
    this function deliberately refuses POSIX rather than inheriting its replace
    semantics. After any exception caller must inspect, not automatically retry.
    An exception after rename preserves the published tree for reconciliation.
    No cleanup, copy fallback, replace, service operation or dispatch is provided.
    """
    if offline_only is not True or os.name != 'nt':
        raise ValueError('WINDOWS_OFFLINE_ONLY')
    if type(manifest) is not dict or not 1 <= len(manifest) <= 64:
        raise ValueError('EXACT_MANIFEST_REQUIRED')
    expected = dict(manifest)
    for name, digest in expected.items():
        if (type(name) is not str or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,100}', name)
                or type(digest) is not str or not re.fullmatch('[0-9a-f]{64}', digest)):
            raise ValueError('EXACT_MANIFEST_REQUIRED')
    source, target = Path(staging), Path(destination)
    if (not source.is_absolute() or not target.is_absolute()
            or '..' in source.parts or '..' in target.parts
            or source.parent != target.parent or source == target):
        raise ValueError('DISTINCT_ABSOLUTE_SIBLINGS_REQUIRED')
    for ancestor in (source.parent, *source.parent.parents):
        _ordinary(ancestor, True)
    if os.path.lexists(target):
        raise FileExistsError('DESTINATION_MUST_BE_ABSENT')
    _verify(source, expected)
    os.rename(source, target)
    _verify(target, expected)
    return dict(observed='RENAMED_AND_HASHES_MATCHED_OFFLINE',
                allow_install=False, allow_dispatch=False, production_execution=False,
                trusted_handle_verified=False, power_loss_durability='UNKNOWN')
