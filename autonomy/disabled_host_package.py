"""Deterministic disabled-host package construction; no OS/service API.

Approved hashes come from the formal publisher, never the input files themselves.
Synthetic test artifacts establish packaging behavior, not installability.
"""
import hashlib
import json
import re
from pathlib import Path, PurePosixPath

SCHEMA = 'rokt.disabled-host-package.v1'
INVENTORY = '1784775229336'
SERVICE = 'RoktU1Bridge'
ACCOUNT = r'NT SERVICE\RoktU1Bridge'
CODE_ROOT = r'C:\Program Files\RoktU1Bridge\v1'
STATE_ROOT = r'C:\ProgramData\RoktU1Bridge'
REQUIRED = frozenset(('service/RoktU1Bridge.exe', 'runtime/dependencies.json',
                      'config/host.json'))
MAX_FILE = 256 * 1024 * 1024
MAX_TOTAL = 1024 * 1024 * 1024
RUNTIME_PATHS = {
    'clr':'Microsoft.NET/Framework64/v4.0.30319/clr.dll',
    'mscorlib':'Microsoft.NET/Framework64/v4.0.30319/mscorlib.dll',
    'System':'Microsoft.NET/Framework64/v4.0.30319/System.dll',
    'System.Core':'Microsoft.NET/Framework64/v4.0.30319/System.Core.dll',
    'System.ServiceProcess':'Microsoft.NET/Framework64/v4.0.30319/System.ServiceProcess.dll',
    'System.Web.Extensions':'Microsoft.NET/assembly/GAC_MSIL/System.Web.Extensions/v4.0_4.0.0.0__31bf3856ad364e35/System.Web.Extensions.dll',
}


class PackageError(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode('ascii')


def safe_name(name):
    if type(name) is not str or not name or '\\' in name or ':' in name:
        raise PackageError('INVALID_ARTIFACT_PATH')
    parts = PurePosixPath(name).parts
    reserved = {'CON','PRN','AUX','NUL'} | {x + str(i) for x in ('COM','LPT') for i in range(1,10)}
    if name != '/'.join(parts) or len(parts) < 2 or parts[0] not in ('service','runtime','config'):
        raise PackageError('INVALID_ARTIFACT_PATH')
    if any(not re.fullmatch(r'[A-Za-z0-9_.-]+', p) or p in ('.','..') or
           p.endswith(('.', ' ')) or p.split('.')[0].upper() in reserved for p in parts):
        raise PackageError('INVALID_ARTIFACT_PATH')
    return name


def validate_inputs(artifacts, approved_hashes, *, source_commit):
    if not re.fullmatch('[0-9a-f]{40}', source_commit or ''):
        raise PackageError('SOURCE_COMMIT_REQUIRED')
    if type(artifacts) is not dict or type(approved_hashes) is not dict or set(artifacts) != set(approved_hashes):
        raise PackageError('EXACT_APPROVED_DEPENDENCIES_REQUIRED')
    if not REQUIRED <= set(artifacts) or len(artifacts) > 256:
        raise PackageError('REQUIRED_DEPENDENCY_MISSING')
    seen=set(); total=0; rows=[]
    for name, data in sorted(artifacts.items()):
        safe_name(name)
        if name.casefold() in seen or any(name.casefold().startswith(x+'/') or x.startswith(name.casefold()+'/') for x in seen):
            raise PackageError('PATH_COLLISION')
        seen.add(name.casefold())
        if type(data) is not bytes or not data or len(data)>MAX_FILE:
            raise PackageError('INVALID_ARTIFACT_BYTES')
        total+=len(data)
        if total>MAX_TOTAL:raise PackageError('PACKAGE_TOO_LARGE')
        expected=approved_hashes[name]
        if type(expected) is not str or re.fullmatch('[0-9a-f]{64}',expected) is None:
            raise PackageError('APPROVED_HASH_REQUIRED')
        actual=hashlib.sha256(data).hexdigest()
        if actual!=expected:raise PackageError('ARTIFACT_HASH_MISMATCH')
        rows.append(dict(path=name,sha256=actual,size=len(data)))
    try: config=json.loads(artifacts['config/host.json'])
    except (UnicodeError, ValueError):raise PackageError('INVALID_HOST_CONFIG') from None
    expected=dict(schema='rokt.disabled-host-config.v1', inventory_id=INVENTORY,
                  service_name=SERVICE, allow_dispatch=False, allow_cancel_dispatch=False,
                  smtp_enabled=False, scheduler_created=False)
    if config != expected or any(type(config[k]) is not type(v) for k,v in expected.items()):
        raise PackageError('UNSAFE_HOST_CONFIG')
    for name in ('service/RoktU1Bridge.exe',):
        if not artifacts[name].startswith(b'MZ'):raise PackageError('PE_HEADER_REQUIRED')
    try: deps=json.loads(artifacts['runtime/dependencies.json'])
    except (UnicodeError,ValueError):raise PackageError('INVALID_RUNTIME_DEPENDENCY') from None
    if (type(deps) is not dict or set(deps)!= {'schema','files','framework'} or
        deps['schema']!='rokt.disabled-host-runtime.v1' or deps['framework']!='.NET Framework 4 x64' or
        type(deps['files']) is not dict or set(deps['files'])!=set(RUNTIME_PATHS)):
        raise PackageError('INVALID_RUNTIME_DEPENDENCY')
    for name,path in RUNTIME_PATHS.items():
        f=deps['files'][name]
        if (type(f) is not dict or set(f)!={'path','sha256','version'} or f['path']!=path or
            type(f['sha256']) is not str or re.fullmatch('[0-9a-f]{64}',f['sha256']) is None or
            type(f['version']) is not str or not 1<=len(f['version'])<=128):
            raise PackageError('INVALID_RUNTIME_DEPENDENCY')
    return dict(schema=SCHEMA,source_commit=source_commit,inventory_id=INVENTORY,
                service_name=SERVICE,account=ACCOUNT,start_type='Disabled',
                code_root=CODE_ROOT,state_root=STATE_ROOT,files=rows,
                allow_start=False,allow_dispatch=False,allow_cancel_dispatch=False,
                scheduler_created=False,rollback_preserves_state=True)


def build_package(destination, artifacts, approved_hashes, *, source_commit, script_root=None):
    """Create a new staging tree only, after all artifact validation succeeds.

    A matching hash establishes exact bytes, not provenance, compatibility,
    Authenticode trust, approval, executable validity or runtime completeness.
    """
    manifest=validate_inputs(artifacts,approved_hashes,source_commit=source_commit)
    scripts=Path(script_root or Path(__file__).with_name('windows'))
    script_bytes={n:(scripts/n).read_bytes() for n in ('Install-DisabledHost.ps1','Rollback-DisabledHost.ps1')}
    if any(not x for x in script_bytes.values()):raise PackageError('INSTALLER_MISSING')
    manifest['scripts']=[dict(path=n,sha256=hashlib.sha256(v).hexdigest(),size=len(v)) for n,v in sorted(script_bytes.items())]
    destination=Path(destination)
    destination.mkdir(parents=False,exist_ok=False)
    for name,data in dict(artifacts,**script_bytes).items():
        target=destination/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    raw=canonical(manifest);(destination/'manifest.json').write_bytes(raw)
    return dict(manifest_sha256=hashlib.sha256(raw).hexdigest(),manifest=manifest,
                allow_install=False,production_ready=False)
