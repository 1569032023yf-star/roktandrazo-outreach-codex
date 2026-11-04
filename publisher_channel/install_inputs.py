"""Pinned installer inputs for the trusted publisher / 发布器受信安装输入固定。

No command execution, installation grant, credentials, DB discovery or endpoint.
All expected digests must originate from an independently approved sealed record.
"""
import ctypes as c
from ctypes import wintypes as w
import hashlib
import os
from pathlib import Path
import re

from autonomy.directory_identity import FileIdentity,AttributeTag
from autonomy.disabled_host_package import RUNTIME_PATHS
from autonomy.host_file_transaction import name
from publisher_channel.install_verifier import parse,sha


def reject(reason):raise ValueError('STOP_AND_PRESERVE_INPUT_'+reason)


def pin_python_runtime(pins, manifest_path, expected, python):
    """Pin the complete external runtime before installation admission.

    This is a reference contract, not a runtime installation grant.
    """
    exe=pins.path(python);root=exe.parent;manifest=pins.path(manifest_path)
    if exe.name!='python.exe' or manifest!=root/'U1_RUNTIME_CONTENT.json':reject('PYTHON_RUNTIME_PATH')
    data=parse(pins.add(manifest,expected,limit=2*1024*1024))
    if (type(data) is not dict or set(data)!={'schema','python','files'} or
        data['schema']!='rokt.u1-runtime-content.v1' or data['python']!='python.exe' or
        type(data['files']) is not dict or not 1<=len(data['files'])<=8192 or
        'python.exe' not in data['files']):reject('PYTHON_RUNTIME_MANIFEST')
    seen=set();total=0
    reserved={'CON','PRN','AUX','NUL'}|{a+str(i) for a in ('COM','LPT') for i in range(1,10)}
    for path,digest in data['files'].items():
        if (type(path) is not str or not re.fullmatch('[A-Za-z0-9_./-]+',path) or
            path.casefold()=='u1_runtime_content.json' or
            any(p in ('','.','..') or p.endswith('.') or p.split('.')[0].upper() in reserved for p in path.split('/')) or
            path.casefold() in seen):reject('PYTHON_RUNTIME_ENTRY')
        seen.add(path.casefold());total+=len(pins.add(root/path,digest))
        if total>1024*1024*1024:reject('PYTHON_RUNTIME_SIZE')
    actual=set()
    for path in root.rglob('*'):
        if path.is_symlink() or path.stat().st_file_attributes&0x400:reject('PYTHON_RUNTIME_REPARSE')
        if path.is_file():actual.add(path.relative_to(root).as_posix().casefold())
    if actual!=seen|{'u1_runtime_content.json'}:reject('PYTHON_RUNTIME_UNMANAGED')
    return data


class FileInformation(c.Structure):
    _fields_=[('attributes',w.DWORD),('created',w.FILETIME),('accessed',w.FILETIME),('written',w.FILETIME),
              ('volume',w.DWORD),('size_high',w.DWORD),('size_low',w.DWORD),('links',w.DWORD),
              ('index_high',w.DWORD),('index_low',w.DWORD)]


class InstallInputPins:
    """Single-use local Windows handles: directories deny rename, files deny write/delete."""
    def __init__(self):
        if os.name!='nt':reject('WINDOWS_REQUIRED')
        self.api=c.WinDLL('kernel32',use_last_error=True)
        self.api.CreateFileW.argtypes=[w.LPCWSTR,w.DWORD,w.DWORD,c.c_void_p,w.DWORD,w.DWORD,w.HANDLE]
        self.api.CreateFileW.restype=w.HANDLE
        self.api.GetFileInformationByHandle.argtypes=[w.HANDLE,c.POINTER(FileInformation)]
        self.api.GetFileInformationByHandle.restype=w.BOOL
        self.api.GetFileInformationByHandleEx.argtypes=[w.HANDLE,c.c_int,c.c_void_p,w.DWORD]
        self.api.GetFileInformationByHandleEx.restype=w.BOOL
        self.api.ReadFile.argtypes=[w.HANDLE,c.c_void_p,w.DWORD,c.POINTER(w.DWORD),c.c_void_p]
        self.api.ReadFile.restype=w.BOOL
        self.api.SetFilePointerEx.argtypes=[w.HANDLE,c.c_longlong,c.POINTER(c.c_longlong),w.DWORD]
        self.api.SetFilePointerEx.restype=w.BOOL
        self.api.CloseHandle.argtypes=[w.HANDLE];self.api.CloseHandle.restype=w.BOOL
        self.handles=[];self.directories={};self.files={};self.references={};self.active=False;self.used=False

    @staticmethod
    def path(value):
        path=Path(value)
        if (not path.is_absolute() or not re.fullmatch('[A-Za-z]:',path.drive) or
            str(path)!=str(value) or any(p in ('.','..') or ':' in p or p.endswith(('.', ' ')) for p in path.parts[1:])):reject('ORDINARY_LOCAL_PATH_REQUIRED')
        return path

    def _checked(self,result):
        if not result:raise c.WinError(c.get_last_error())
        return result

    def _identity(self,handle,directory):
        tag=AttributeTag();ident=FileIdentity()
        self._checked(self.api.GetFileInformationByHandleEx(handle,9,c.byref(tag),c.sizeof(tag)))
        self._checked(self.api.GetFileInformationByHandleEx(handle,18,c.byref(ident),c.sizeof(ident)))
        if tag.attributes&0x400 or bool(tag.attributes&0x10)!=directory:reject('REPARSE_OR_TYPE')
        return ident.volume,bytes(ident.identifier).hex()

    def _open(self,path,directory):
        handle=self.api.CreateFileW(str(path),0x81 if directory else 0x80000000,
                                   3 if directory else 1,None,3,0x02200000 if directory else 0x00200000,None)
        if handle==c.c_void_p(-1).value:raise c.WinError(c.get_last_error())
        self.handles.append(handle)
        return handle,self._identity(handle,directory)

    def _parents(self,path):
        for parent in (*reversed(path.parent.parents),path.parent):
            key=str(parent).casefold()
            if key not in self.directories:self.directories[key]=self._open(parent,True)

    def _read(self,handle,limit,system_component=False):
        info=FileInformation();self._checked(self.api.GetFileInformationByHandle(handle,c.byref(info)))
        size=(info.size_high<<32)|info.size_low
        if info.links<1 or (not system_component and info.links!=1) or size>limit:reject('LINKS_OR_SIZE')
        self._checked(self.api.SetFilePointerEx(handle,0,None,0));pieces=[];total=0
        while True:
            chunk=c.create_string_buffer(65536);count=w.DWORD()
            self._checked(self.api.ReadFile(handle,chunk,len(chunk),c.byref(count),None))
            if not count.value:break
            total+=count.value
            if total>limit:reject('SIZE_LIMIT')
            pieces.append(chunk.raw[:count.value])
        raw=b''.join(pieces)
        if len(raw)!=size:reject('SIZE_CHANGED')
        return raw

    def add(self,path,expected,*,limit=256*1024*1024):
        return self._add(path,expected,limit=limit,system_component=False)

    def add_mutable_reference(self,path):
        """Hold only identity: allow original DB writes, deny replacement/deletion.

        Never read, hash, copy, open SQLite or migrate the referenced database.
        """
        if not self.active:reject('PINS_NOT_ACTIVE')
        path=self.path(path);key=str(path).casefold()
        if key in self.files:reject('CONFLICTING_PIN')
        if key not in self.references:
            self._parents(path)
            # Attribute-only handles do not reliably exclude Windows deletion.
            # Request read access but never ReadFile; share both read and write.
            handle=self.api.CreateFileW(str(path),0x80000000,3,None,3,0x00200000,None)
            if handle==c.c_void_p(-1).value:raise c.WinError(c.get_last_error())
            self.handles.append(handle)
            identity=self._identity(handle,False)
            self.references[key]=(handle,identity)
        handle,identity=self.references[key]
        info=FileInformation();self._checked(self.api.GetFileInformationByHandle(handle,c.byref(info)))
        if info.links!=1 or self._identity(handle,False)!=identity:reject('MUTABLE_REFERENCE_CHANGED')
        return identity

    def add_system_component(self,path,expected):
        # Windows servicing legitimately hardlinks these exact seven components.
        # This is read-only input admission, never an installation target list.
        self.api.GetWindowsDirectoryW.argtypes=[w.LPWSTR,w.UINT];self.api.GetWindowsDirectoryW.restype=w.UINT
        buffer=c.create_unicode_buffer(32768);size=self.api.GetWindowsDirectoryW(buffer,len(buffer))
        if not 0<size<len(buffer):reject('WINDOWS_DIRECTORY')
        root=Path(buffer.value)
        allowed={str(root/p).casefold() for p in RUNTIME_PATHS.values()}|{str(root/'System32/WindowsPowerShell/v1.0/powershell.exe').casefold()}
        if str(self.path(path)).casefold() not in allowed:reject('FIXED_SYSTEM_COMPONENT_REQUIRED')
        return self._add(path,expected,limit=256*1024*1024,system_component=True)

    def _add(self,path,expected,*,limit,system_component):
        if not self.active or not sha(expected) or type(limit) is not int or not 0<limit<=256*1024*1024:reject('PIN_CONTRACT')
        path=self.path(path);key=str(path).casefold()
        if key in self.references:reject('CONFLICTING_PIN')
        if key in self.files:
            handle,identity,digest,old_limit,old_system=self.files[key]
            if digest!=expected or old_limit!=limit or old_system!=system_component:reject('CONFLICTING_PIN')
        else:
            self._parents(path);handle,identity=self._open(path,False)
            self.files[key]=(handle,identity,expected,limit,system_component)
        raw=self._read(handle,limit,system_component)
        if hashlib.sha256(raw).hexdigest()!=expected:reject('DIGEST_MISMATCH')
        return raw

    def revalidate(self):
        if not self.active:reject('PINS_NOT_ACTIVE')
        for handle,identity in self.directories.values():
            if self._identity(handle,True)!=identity:reject('DIRECTORY_IDENTITY_CHANGED')
        for handle,identity,expected,limit,system_component in self.files.values():
            if self._identity(handle,False)!=identity or hashlib.sha256(self._read(handle,limit,system_component)).hexdigest()!=expected:reject('FILE_CHANGED')
        for path in self.references:
            self.add_mutable_reference(path)
        return True

    def __enter__(self):
        if self.used:reject('PINS_SINGLE_USE')
        self.used=True;self.active=True;return self

    def __exit__(self,*_):
        self.active=False;failed=[]
        for handle in reversed(self.handles):
            if not self.api.CloseHandle(handle):failed.append(handle)
        self.handles=failed
        if failed:reject('HANDLE_CLOSE_UNVERIFIED')


SCRIPTS=frozenset(('Install-DisabledHost.ps1','Rollback-DisabledHost.ps1','Acl-Transaction.ps1',
                  'Host-InstallTransaction.ps1','Maintenance-Authority.ps1','Observe-HostInstall.ps1',
                  'Host-PackagePreparation.ps1','Publisher-InstallHost.ps1','host_file_transaction.py'))


def pin_package(pins,root,manifest_sha256,source_commit):
    """Bind exact approved manifest bytes and every declared file; never self-approve hashes."""
    root=pins.path(root)
    if not re.fullmatch('[0-9a-f]{40}',source_commit or ''):reject('SOURCE_APPROVAL')
    manifest=parse(pins.add(root/'manifest.json',manifest_sha256,limit=1024*1024))
    if (type(manifest) is not dict or manifest.get('schema')!='rokt.disabled-host-package.v1' or
        manifest.get('source_commit')!=source_commit or manifest.get('installer_version')!='1.1.1' or
        manifest.get('inventory_id')!='1784775229336' or manifest.get('service_name')!='RoktU1Bridge' or
        manifest.get('account')!=r'NT SERVICE\RoktU1Bridge' or manifest.get('start_type')!='Disabled' or
        manifest.get('code_root')!=r'C:\Program Files\RoktU1Bridge\v1' or manifest.get('state_root')!=r'C:\ProgramData\RoktU1Bridge' or
        any(manifest.get(k) is not False for k in ('allow_start','allow_dispatch','allow_cancel_dispatch','scheduler_created','allow_install')) or
        manifest.get('rollback_preserves_state') is not True or type(manifest.get('files')) is not list or
        type(manifest.get('scripts')) is not list or not 0<len(manifest['files'])<=256):reject('MANIFEST_CONTRACT')
    if any(type(row) is not dict for row in manifest['scripts']+manifest['files']):reject('ENTRY_CONTRACT')
    if {row.get('path') for row in manifest['scripts']}!=SCRIPTS:reject('EXACT_SCRIPT_SET')
    entries=manifest['files']+manifest['scripts'];seen=[];total=0
    if not {'service/RoktU1Bridge.exe','runtime/dependencies.json','config/host.json'}<={r.get('path') for r in manifest['files']}:reject('REQUIRED_FILES')
    for row in entries:
        path=row['path'] if row in manifest['scripts'] else name(row['path']);lower=path.casefold()
        if (any(lower==s or lower.startswith(s+'/') or s.startswith(lower+'/') for s in seen) or
            type(row.get('size')) is not int or not 0<row['size']<=256*1024*1024 or not sha(row.get('sha256'))):reject('ENTRY_CONTRACT')
        if row in manifest['files'] and (path.split('/')[0] not in ('service','runtime','config') or lower in ('config/installation.json','config/runtime.json','config/supervisor.json') or any(p.endswith('.u1-new') for p in lower.split('/'))):reject('RESERVED_FILE')
        seen.append(lower);total+=row['size']
        if total>1024*1024*1024:reject('TOTAL_SIZE')
        raw=pins.add(root/path,row['sha256'])
        if len(raw)!=row['size']:reject('ENTRY_SIZE')
        if path=='config/host.json':
            expected=dict(schema='rokt.disabled-host-config.v1',inventory_id='1784775229336',service_name='RoktU1Bridge',
                          allow_dispatch=False,allow_cancel_dispatch=False,smtp_enabled=False,scheduler_created=False)
            actual=parse(raw)
            if actual!=expected or any(type(actual[k]) is not type(v) for k,v in expected.items()):reject('UNSAFE_HOST_CONFIG')
    pins.revalidate()
    return manifest
