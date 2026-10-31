"""Offline source handles and hashes / 离线源对象句柄与哈希，不赋安装权限。

This guard intentionally prevents renaming its source directory. It is not yet
joined to publication: closing handles then renaming would reopen a race.
只读持有源目录及文件；未接发布，不能关闭句柄后假称竞态已经解决。
"""
import ctypes
from ctypes import wintypes
import hashlib
from pathlib import Path
import re

from autonomy.directory_identity import AttributeTag, DirectoryIdentityGuard, FileIdentity


class StandardInfo(ctypes.Structure):
    _fields_ = [('allocation', ctypes.c_longlong), ('end', ctypes.c_longlong),
                ('links', wintypes.DWORD), ('delete_pending', ctypes.c_ubyte),
                ('directory', ctypes.c_ubyte)]


class SourceIdentityGuard:
    """Single-use read-only guard for caller-owned isolated flat directories.

    Shares read only, excluding ordinary write/delete opens while held. ACL,
    pre-existing writable mappings, filesystem trust, durability and leases are
    unproven. Rehashing observes content; it is not universal immutability proof.
    共享只读，拒普通写入/删除打开；ACL、已有可写映射、文件系统与租约未验收。
    """
    MAX_FILE_BYTES = 16 * 1024 * 1024
    MAX_TOTAL_BYTES = 64 * 1024 * 1024

    def __init__(self, directory, manifest, *, offline_only=False):
        self._directory = DirectoryIdentityGuard(directory, offline_only=offline_only)
        if type(manifest) is not dict or not 1 <= len(manifest) <= 64:
            raise ValueError('EXACT_MANIFEST_REQUIRED')
        names = set()
        for name, digest in manifest.items():
            if (type(name) is not str or
                    not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,100}', name) or
                    name.endswith('.') or name.casefold() in names or
                    re.fullmatch(r'(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])', name.split('.')[0]) or
                    type(digest) is not str or not re.fullmatch('[0-9a-f]{64}', digest)):
                raise ValueError('EXACT_ORDINARY_MANIFEST_REQUIRED')
            names.add(name.casefold())
        self.path = Path(directory)
        self.expected = dict(manifest)
        self._api = self._directory._api
        self._api.ReadFile.argtypes = (wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                                       ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p)
        self._api.ReadFile.restype = wintypes.BOOL
        self._api.SetFilePointerEx.argtypes = (wintypes.HANDLE, ctypes.c_longlong,
                                              ctypes.c_void_p, wintypes.DWORD)
        self._api.SetFilePointerEx.restype = wintypes.BOOL
        self._handles = {}
        self._identities = {}
        self._entered = False
        self._active = False

    def _info(self, handle):
        attrs, identity, standard = AttributeTag(), FileIdentity(), StandardInfo()
        for kind, buffer in ((9, attrs), (18, identity), (1, standard)):
            if not self._api.GetFileInformationByHandleEx(
                    handle, kind, ctypes.byref(buffer), ctypes.sizeof(buffer)):
                raise ctypes.WinError(ctypes.get_last_error())
        if attrs.attributes & (0x10 | 0x400) or standard.directory or standard.delete_pending:
            raise ValueError('ORDINARY_FILE_HANDLE_REQUIRED')
        if standard.links != 1:
            raise ValueError('HARDLINK_REJECTED')
        if not 0 <= standard.end <= self.MAX_FILE_BYTES:
            raise ValueError('FILE_SIZE_LIMIT')
        return dict(volume=identity.volume, file_id_128=bytes(identity.identifier).hex(),
                    bytes=standard.end)

    def _hash(self, handle, size):
        if not self._api.SetFilePointerEx(handle, 0, None, 0):
            raise ctypes.WinError(ctypes.get_last_error())
        digest = hashlib.sha256()
        buffer = ctypes.create_string_buffer(65536)
        total = 0
        while True:
            count = wintypes.DWORD()
            if not self._api.ReadFile(handle, buffer, len(buffer), ctypes.byref(count), None):
                raise ctypes.WinError(ctypes.get_last_error())
            if not count.value:
                break
            total += count.value
            if total > size:
                raise ValueError('OPEN_FILE_SIZE_CHANGED')
            digest.update(buffer.raw[:count.value])
        if total != size:
            raise ValueError('OPEN_FILE_SIZE_CHANGED')
        return digest.hexdigest()

    def _exact_names(self):
        if set(p.name for p in self.path.iterdir()) != set(self.expected):
            raise ValueError('EXACT_FILE_SET_REQUIRED')

    def __enter__(self):
        if self._entered:
            raise ValueError('GUARD_SINGLE_USE')
        self._entered = True
        try:
            self._directory.__enter__()
            self._exact_names()
            total = 0
            for name in sorted(self.expected):
                # GENERIC_READ, SHARE_READ only, OPEN_EXISTING,
                # OPEN_REPARSE_POINT. Do not follow a leaf reparse point.
                handle = self._api.CreateFileW(str(self.path / name), 0x80000000,
                                               1, None, 3, 0x00200000, None)
                if handle == ctypes.c_void_p(-1).value:
                    raise ctypes.WinError(ctypes.get_last_error())
                self._handles[name] = handle
                self._identities[name] = self._info(handle)
                total += self._identities[name]['bytes']
                if total > self.MAX_TOTAL_BYTES:
                    raise ValueError('TOTAL_SIZE_LIMIT')
            self._active = True
            self.revalidate()
            return self
        except BaseException:
            self.close()
            raise

    def revalidate(self):
        if not self._active:
            raise ValueError('NO_ACTIVE_SOURCE_HANDLES')
        directory = self._directory.revalidate()
        self._exact_names()
        files = {}
        for name, handle in self._handles.items():
            info = self._info(handle)
            if info != self._identities[name]:
                raise ValueError('OPEN_FILE_IDENTITY_CHANGED')
            digest = self._hash(handle, info['bytes'])
            if digest != self.expected[name]:
                raise ValueError('OPEN_FILE_HASH_MISMATCH')
            if self._info(handle) != info:
                raise ValueError('OPEN_FILE_IDENTITY_CHANGED')
            files[name] = dict(info, sha256=digest)
        self._exact_names()
        self._directory.revalidate()
        return dict(directory=directory, files=files, allow_install=False,
                    allow_dispatch=False, production_execution=False,
                    publication_integrated=False, acl_trust_verified=False,
                    preexisting_writable_mappings_verified=False)

    def close(self):
        self._active = False
        failed = {}
        error = None
        for name, handle in self._handles.items():
            if not self._api.CloseHandle(handle):
                failed[name] = handle
                error = ctypes.get_last_error()
        self._handles = failed
        try:
            self._directory.close()
        finally:
            if error is not None:
                raise ctypes.WinError(error)

    def __exit__(self, *_):
        self.close()
