"""Offline Windows ancestor handles; does not establish ACL/lease authority."""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import re


class FileIdentity(ctypes.Structure):
    _fields_ = [('volume', ctypes.c_ulonglong), ('identifier', ctypes.c_ubyte * 16)]


class AttributeTag(ctypes.Structure):
    _fields_ = [('attributes', wintypes.DWORD), ('tag', wintypes.DWORD)]


class DirectoryIdentityGuard:
    """Hold root-to-directory handles without FILE_SHARE_DELETE.

    This binds ancestor names during the context, not ACLs, children or source
    contents. Process exit releases handles; no persistence/authority is implied.
    """

    def __init__(self, path, *, offline_only=False):
        if os.name != 'nt' or offline_only is not True:
            raise ValueError('WINDOWS_OFFLINE_ONLY')
        self.path = Path(path)
        if (not self.path.is_absolute() or not re.fullmatch('[A-Za-z]:', self.path.drive)
                or any(p in ('.', '..') or ':' in p or p.endswith(('.', ' '))
                       for p in self.path.parts[1:])):
            raise ValueError('LOCAL_ABSOLUTE_ORDINARY_PATH_REQUIRED')
        self._api = ctypes.WinDLL('kernel32', use_last_error=True)
        self._api.CreateFileW.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
            ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
        self._api.CreateFileW.restype = wintypes.HANDLE
        self._api.GetFileInformationByHandleEx.argtypes = (wintypes.HANDLE,
            ctypes.c_int, ctypes.c_void_p, wintypes.DWORD)
        self._api.GetFileInformationByHandleEx.restype = wintypes.BOOL
        self._api.CloseHandle.argtypes = (wintypes.HANDLE,)
        self._api.CloseHandle.restype = wintypes.BOOL
        self._handles = []
        self._identities = []
        self._entered = False

    def _identity(self, handle):
        attrs = AttributeTag()
        identity = FileIdentity()
        for kind, buffer in ((9, attrs), (18, identity)):
            if not self._api.GetFileInformationByHandleEx(handle, kind, ctypes.byref(buffer), ctypes.sizeof(buffer)):
                raise ctypes.WinError(ctypes.get_last_error())
        if not attrs.attributes & 0x10 or attrs.attributes & 0x400:
            raise ValueError('NON_DIRECTORY_OR_REPARSE_HANDLE')
        return (identity.volume, bytes(identity.identifier).hex())

    def __enter__(self):
        if self._entered:
            raise ValueError('GUARD_SINGLE_USE')
        self._entered = True
        try:
            for ancestor in (*reversed(self.path.parents), self.path):
                # LIST_DIRECTORY|READ_ATTRIBUTES, SHARE_READ|SHARE_WRITE (no SHARE_DELETE),
                # OPEN_EXISTING, BACKUP_SEMANTICS|OPEN_REPARSE_POINT.
                handle = self._api.CreateFileW(str(ancestor), 0x81, 3, None, 3, 0x02200000, None)
                if handle == ctypes.c_void_p(-1).value:
                    raise ctypes.WinError(ctypes.get_last_error())
                self._handles.append(handle)
                self._identities.append(self._identity(handle))
            return self
        except BaseException:
            self.close()
            raise

    def revalidate(self):
        if not self._handles:
            raise ValueError('NO_ACTIVE_DIRECTORY_HANDLES')
        if [self._identity(h) for h in self._handles] != self._identities:
            raise ValueError('DIRECTORY_IDENTITY_CHANGED')
        volume, identifier = self._identities[-1]
        return dict(volume=volume, file_id_128=identifier)

    def close(self):
        failed = []
        error = None
        while self._handles:
            handle = self._handles.pop()
            if not self._api.CloseHandle(handle):
                error = ctypes.get_last_error()
                failed.append(handle)
        self._handles = failed
        if error is not None:
            raise ctypes.WinError(error)

    def __exit__(self, *_):
        self.close()
