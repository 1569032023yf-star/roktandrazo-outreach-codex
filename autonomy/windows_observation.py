"""Opt-in local Windows facts only; never signs evidence or authorizes production."""
import ctypes
import ntpath
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime

def system_powershell():
    buffer = ctypes.create_unicode_buffer(32768)
    size = ctypes.windll.kernel32.GetWindowsDirectoryW(buffer, len(buffer))
    root = buffer.value
    if not 0 < size < len(buffer) or not re.fullmatch(r'[A-Za-z]:\\[^\x00-\x1f]+', root):
        raise OSError('INVALID_SYSTEM_DIRECTORY')
    return ntpath.join(root, 'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe')
SCRIPT = r'''$ErrorActionPreference='Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$os = Get-CimInstance -ClassName Win32_OperatingSystem -Property LastBootUpTime
$sid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$session = [Diagnostics.Process]::GetCurrentProcess().SessionId
[ordered]@{sid=$sid;session_id=$session;boot_utc=$os.LastBootUpTime.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ');observed_utc=[DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')} | ConvertTo-Json -Compress
'''
ARGV = ('SYSTEM_POWERSHELL', '-NoLogo', '-NoProfile', '-NonInteractive', '-Command', SCRIPT)
MAX_OUTPUT_BYTES = 2048
TIMEOUT_SECONDS = 10


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate')
        result[key] = value
    return result


def collect_observation(*, enabled=False, runner=subprocess.run, platform=None, directory_resolver=system_powershell):
    """Explicit opt-in local observation. Injected runners are test dependencies.

    No caller-supplied command, path, network endpoint or signing key is accepted.
    Output limits are validation limits, not a hard subprocess memory sandbox.
    """
    denied = dict(reason='DISABLED', facts=None, production_ready=False, signed=False)
    if enabled is not True:
        return denied
    if (sys.platform if platform is None else platform) != 'win32':
        return dict(denied, reason='UNSUPPORTED_PLATFORM')
    try:
        executable = directory_resolver()
        completed = runner((executable,) + ARGV[1:], shell=False, capture_output=True, timeout=TIMEOUT_SECONDS,
                           check=False, creationflags=0x08000000)
    except subprocess.TimeoutExpired:
        return dict(denied, reason='OBSERVATION_TIMEOUT')
    except (OSError, subprocess.SubprocessError):
        return dict(denied, reason='OBSERVATION_PROCESS_FAILED')
    if (type(completed.stdout) is not bytes or type(completed.stderr) is not bytes or
            len(completed.stdout) > MAX_OUTPUT_BYTES or len(completed.stderr) > MAX_OUTPUT_BYTES):
        return dict(denied, reason='OUTPUT_LIMIT_OR_TYPE_REJECTED')
    if completed.returncode != 0 or completed.stderr:
        return dict(denied, reason='OBSERVATION_PROCESS_FAILED')
    try:
        p = json.loads(completed.stdout.decode('utf-8'), object_pairs_hook=_unique)
        if type(p) is not dict or set(p) != {'sid', 'session_id', 'boot_utc', 'observed_utc'}:
            raise ValueError('schema')
        if type(p['sid']) is not str or re.fullmatch(r'S-1-[0-9]{1,15}(?:-[0-9]{1,10}){1,15}', p['sid']) is None:
            raise ValueError('sid')
        if type(p['session_id']) is not int or not 0 <= p['session_id'] <= 0xffffffff:
            raise ValueError('session')
        stamps = []
        for field in ('boot_utc', 'observed_utc'):
            value = p[field]
            if type(value) is not str or re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ', value) is None:
                raise ValueError('time')
            stamps.append(datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ'))
        if stamps[0] > stamps[1]:
            raise ValueError('order')
    except (ValueError, TypeError, UnicodeError, RecursionError):
        return dict(denied, reason='INVALID_OBSERVATION')
    facts = dict(principal_opaque=hashlib.sha256(('rokt.local-windows-sid.v1:' + p['sid']).encode('ascii')).hexdigest(),
                 session_id=p['session_id'], boot_utc=p['boot_utc'], observed_utc=p['observed_utc'])
    return dict(denied, reason='LOCAL_FACTS_OBSERVED', facts=facts)
