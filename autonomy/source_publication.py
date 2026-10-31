"""Offline held-source publication attempt / 离线持有源身份的发布尝试合同。

On the tested Windows filesystem, held child handles without SHARE_DELETE block
the directory rename with error5. Keep this failure: do not close/reopen, weaken
sharing, copy or retry. This is not an installable publication implementation.
当前实测Windows在子文件句柄不共享删除时拒绝目录改名，保留阻塞，不降级重试。
"""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import re

from autonomy.directory_identity import DirectoryIdentityGuard
from autonomy.source_identity import SourceIdentityGuard


class _RenameInfo(ctypes.Structure):
    # FileRenameInfo (not Ex): union storage followed by HANDLE/DWORD/WCHAR.
    _fields_ = [('replace', wintypes.DWORD), ('root', wintypes.HANDLE),
                ('length', wintypes.DWORD), ('name', wintypes.WCHAR * 1)]


class _SourceDirectory(DirectoryIdentityGuard):
    def _open_handle(self, ancestor):
        if ancestor != self.path:
            return super()._open_handle(ancestor)
        # Own source handle has DELETE access; other opens still cannot delete it.
        return self._api.CreateFileW(str(ancestor), 0x10081, 3, None, 3, 0x02200000, None)


class _HeldSource(SourceIdentityGuard):
    _directory_class = _SourceDirectory


def _rename_handle(guard, target):
    api = guard._api
    api.SetFileInformationByHandle.argtypes = (wintypes.HANDLE, ctypes.c_int,
                                               ctypes.c_void_p, wintypes.DWORD)
    api.SetFileInformationByHandle.restype = wintypes.BOOL
    name = str(target).encode('utf-16-le')
    size = max(ctypes.sizeof(_RenameInfo), _RenameInfo.name.offset + len(name))
    buffer = ctypes.create_string_buffer(size)
    value = _RenameInfo.from_buffer(buffer)
    value.replace = 0  # Never replace an existing destination, including a directory.
    value.root = None
    value.length = len(name)
    ctypes.memmove(ctypes.addressof(buffer) + _RenameInfo.name.offset, name, len(name))
    if not api.SetFileInformationByHandle(guard._directory._handles[-1], 3, buffer, size):
        raise ctypes.WinError(ctypes.get_last_error())


def _verify_named_objects(guard, before):
    """Check destination names refer to retained identities, not just equal bytes."""
    for name, expected in [(None, before['directory']), *before['files'].items()]:
        path = guard.path if name is None else guard.path / name
        flags = 0x02200000 if name is None else 0x00200000
        handle = guard._api.CreateFileW(str(path), 0x80, 7, None, 3, flags, None)
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            if name is None:
                volume, identifier = guard._directory._identity(handle)
                actual = dict(volume=volume, file_id_128=identifier)
            else:
                actual = guard._info(handle)
            if actual != {k: expected[k] for k in actual}:
                raise ValueError('DESTINATION_IDENTITY_MISMATCH')
        finally:
            if not guard._api.CloseHandle(handle):
                raise ctypes.WinError(ctypes.get_last_error())


def attempt_source_publication_offline(staging, destination, manifest, *, offline_only=False):
    """One attempt only, no cleanup/retry or release-and-path-rename fallback.

    Caller journals intent before calling; any exception leaves status-only
    reconciliation, never a retry authorization. Success is unverified on the
    current filesystem because no-delete child sharing blocks the rename.
    调用方先落意图；异常后仅对账，不授权重放。当前实机成功路径未通过。
    """
    if offline_only is not True or os.name != 'nt':
        raise ValueError('WINDOWS_OFFLINE_ONLY')
    source, target = Path(staging), Path(destination)
    if (not source.is_absolute() or not target.is_absolute() or
            source.parent != target.parent or source == target or
            '..' in source.parts or '..' in target.parts or
            not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,100}', target.name) or
            target.name.endswith('.') or
            re.fullmatch(r'(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])', target.name.split('.')[0])):
        raise ValueError('DISTINCT_ORDINARY_ABSOLUTE_SIBLINGS_REQUIRED')
    # Constructor validates the target's drive/ancestor spelling without opening it.
    DirectoryIdentityGuard(target, offline_only=True)
    with _HeldSource(source, manifest, offline_only=True) as guard:
        if os.path.lexists(target):
            raise FileExistsError('DESTINATION_MUST_BE_ABSENT')
        before = guard.revalidate()
        _rename_handle(guard, target)
        guard.path = target
        after = guard.revalidate()
        if after != before:
            raise ValueError('RETAINED_SOURCE_IDENTITY_MISMATCH')
        _verify_named_objects(guard, before)
    return dict(observed='HELD_SOURCE_RENAME_AND_READBACK_OFFLINE',
                allow_install=False, allow_dispatch=False, production_execution=False,
                production_installer_integrated=False, trusted_handle_verified=False,
                power_loss_durability='UNKNOWN')
