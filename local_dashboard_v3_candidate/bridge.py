"""Read-only bridge adapter. Credentials remain in memory; no executor imports."""
import ctypes
from ctypes import wintypes
import json
import urllib.request
from .data import now

READS = {'health', 'runtime', 'city', 'provider-audit'}


def credential():
    class Credential(ctypes.Structure):
        _fields_ = [('flags', wintypes.DWORD), ('type', wintypes.DWORD), ('target', wintypes.LPWSTR),
                    ('comment', wintypes.LPWSTR), ('written', wintypes.FILETIME), ('size', wintypes.DWORD),
                    ('blob', ctypes.POINTER(ctypes.c_ubyte)), ('persist', wintypes.DWORD),
                    ('count', wintypes.DWORD), ('attributes', ctypes.c_void_p),
                    ('alias', wintypes.LPWSTR), ('username', wintypes.LPWSTR)]
    api = ctypes.WinDLL('advapi32', use_last_error=True)
    api.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.POINTER(Credential))]
    api.CredReadW.restype = wintypes.BOOL
    api.CredFree.argtypes = [ctypes.c_void_p]
    pointer = ctypes.POINTER(Credential)()
    if not api.CredReadW('rokt-deploy-channel:bridge-token', 1, 0, ctypes.byref(pointer)):
        raise RuntimeError('本机读取凭据不可用')
    try:
        blob = ctypes.string_at(pointer.contents.blob, pointer.contents.size)
        token = blob.decode('utf-16-le' if b'\x00' in blob else 'utf-8').strip('\x00').strip()
        if not token:
            raise RuntimeError('本机读取凭据为空')
        return token
    finally:
        api.CredFree(pointer)


def read(operation, city_id=None):
    if operation not in READS:
        raise ValueError('非只读操作被拒绝')
    body = {}
    if operation == 'runtime':
        body['limit'] = 20
    if operation == 'provider-audit':
        body['hours'] = 24
    if city_id is not None:
        if operation not in {'city', 'provider-audit'} or type(city_id) is not int or not 1 <= city_id <= 9999:
            raise ValueError('城市编号无效')
        body['city'] = city_id  # Official prodobs accepts stable numeric IDs.
    req = urllib.request.Request('http://127.0.0.1:8791/v1/' + operation,
        data=json.dumps(body).encode(), method='POST',
        headers={'Authorization': 'Bearer ' + credential(), 'Content-Type': 'application/json'})
    # Do not honor proxy environment variables for local credentials or follow redirects.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(req, timeout=12) as response:
        value = json.load(response)
        if not isinstance(value, dict) or value.get('error'):
            raise RuntimeError('只读接口返回异常')
    return {'data': value, 'observed_at': now(), 'source': '正式桥接 /v1/' + operation,
            'last_attempt_at': now(), 'error': None}
